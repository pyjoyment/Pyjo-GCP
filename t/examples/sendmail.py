import Pyjo.File
import Pyjo.IOLoop.Server
import Pyjo.UserAgent

from Pyjo.Test import *

import os
import smtplib
import socket
import subprocess
import sys
import time


# The example against the Gmail API of its own, of GMAIL_EMULATOR_HOST, in a process of its own, with the messages of
# the standard input and the options of sendmail, as PHP and cron give them

tmp = Pyjo.File.tempdir()
ROOT = Pyjo.File.curfile().dirname().dirname().dirname()
EXAMPLE = ROOT.child('examples', 'sendmail.py').to_str()

GMAIL = tmp.child('gmail.py').spew(r"""
from Pyjoyment.Lite import *

app.log.level = 'fatal'
MESSAGES = []


@post('/upload/gmail/v1/users/me/messages/send')
def send(c):
    message = c.req.body
    MESSAGES.append({
        'query': c.req.url.query.to_str(),
        'type': c.req.headers.content_type,
        'authorization': c.req.headers.authorization,
        'message': message.decode(),
    })
    for status, text in ((403, 'Forbidden'), (400, 'Invalid'), (503, 'Unavailable')):
        if f'Subject: {text}'.encode() in message:
            return c.render(json={'error': {'code': status, 'message': f'{text} message'}}, status=status)
    c.render(json={'id': f'm{len(MESSAGES)}', 'threadId': 't1', 'labelIds': ['SENT']})


@get('/messages')
def messages(c):
    c.render(json=MESSAGES)


app.start()
""")


def listen():
    port = Pyjo.IOLoop.Server.object.generate_port()
    return port, f'http://127.0.0.1:{port}'


def wait_for(process, port):
    deadline = time.monotonic() + 30
    while True:
        try:
            socket.create_connection(('127.0.0.1', port), timeout=1).close()
            return
        except OSError:
            if time.monotonic() > deadline or process.poll() is not None:
                raise
            time.sleep(0.1)


gmail_port, gmail_url = listen()
env = {
    name: value
    for name, value in os.environ.items()
    if not name.startswith(('GOOGLE_', 'GCLOUD_', 'CLOUDSDK_', 'GCE_', 'GMAIL_'))
}
env.update(CLOUDSDK_CONFIG=str(tmp.child('gcloud')), HOME=str(tmp), NO_GCE_CHECK='true', PYJO_LOG_LEVEL='fatal')
gmail = subprocess.Popen(
    [sys.executable, str(GMAIL), 'daemon', '-l', gmail_url],
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
env['GMAIL_EMULATOR_HOST'] = f'127.0.0.1:{gmail_port}'

ua = Pyjo.UserAgent.new(max_connections=0)


def sendmail(message, *args, **environment):
    done = subprocess.run(
        [sys.executable, EXAMPLE, *args],
        input=message.encode(),
        env={**env, **environment},
        capture_output=True,
        check=False,
    )
    return done.returncode, done.stderr.decode()


def last():
    return ua.get(f'{gmail_url}/messages').res.json()[-1]


MESSAGE = 'To: Alice <alice@example.com>\nCc: bob@example.com\nSubject: Hello\n\nHello,\n.\nthe dot above.\n'

try:
    wait_for(gmail, gmail_port)

    with subtest('Messages of PHP'):
        is_ok(sendmail(MESSAGE, '-t', '-i'), (0, ''), 'sent, with -t -i of PHP')
        sent = last()
        is_ok((sent['query'], sent['type']), ('uploadType=media', 'message/rfc822'), 'media upload of RFC 822')
        is_ok(sent['authorization'], None, 'no credentials for an emulator')
        is_ok(
            sent['message'],
            'To: Alice <alice@example.com>\r\nCc: bob@example.com\r\nSubject: Hello\r\n\r\nHello,\r\n.\r\nthe dot above.\r\n',
            'message as it is, with CRLF, and the line of a dot with -i',
        )

        is_ok(sendmail(MESSAGE, '-t', '-i', '-fnoreply@example.com', '-F', 'Example App'), (0, ''), 'sender of -f -F')
        like_ok(last()['message'], r'^From: Example App <noreply@example.com>\r\nTo: ', 'From of -f and -F')
        message = f'From: me@example.com\n{MESSAGE}'
        is_ok(sendmail(message, '-t', '-i', '-f', 'noreply@example.com'), (0, ''), 'sender of -f with From')
        like_ok(last()['message'], r'^From: me@example\.com\r\nTo: ', 'From of the message over -f')

        is_ok(sendmail(MESSAGE, '-t'), (0, ''), 'sent without -i')
        is_ok(last()['message'], 'To: Alice <alice@example.com>\r\nCc: bob@example.com\r\nSubject: Hello\r\n\r\nHello,\r\n',
              'message up to the line of a dot without -i')  # fmt: skip
        is_ok(sendmail(MESSAGE, '-t', '-oi', '-odi', '-v'), (0, ''), '-oi of -i, and the others of sendmail ignored')
        like_ok(last()['message'], r'the dot above', 'line of a dot with -oi')

    with subtest('Recipients of the arguments'):
        is_ok(sendmail(MESSAGE, '-i', 'alice@example.com', 'carol@example.com', 'Dave <dave@example.com>'), (0, ''),
              'recipients of the arguments')  # fmt: skip
        like_ok(last()['message'], r'^Bcc: carol@example\.com, Dave <dave@example\.com>\r\nTo: Alice ',
                'Bcc of the recipients that the headers do not have')  # fmt: skip
        is_ok(sendmail(MESSAGE, '-i', '--', 'BOB@example.com'), (0, ''), 'recipient after --')
        unlike_ok(last()['message'], r'Bcc:', 'recipient of the headers, of any case')

    with subtest('Errors'):
        code, error = sendmail(MESSAGE, '-i')
        is_ok(code, 64, 'no recipients without -t')
        like_ok(error, r'^sendmail\.py: no recipients, of the arguments or of -t', 'error of the recipients')
        is_ok(sendmail('Subject: Nobody\n\nHello\n', '-t')[0], 64, 'no recipients of the headers')
        is_ok(sendmail(MESSAGE, '--unknown')[0], 64, 'unknown option')
        is_ok(sendmail(MESSAGE, '-t', '-f')[0], 64, '-f without a value')

        errors = [('Forbidden', 77), ('Invalid', 69), ('Unavailable', 69)]
        for text, status in errors:
            code, error = sendmail(MESSAGE.replace('Subject: Hello', f'Subject: {text}'), '-t', '-i')
            is_ok(code, status, f'exit code of {text}')
            like_ok(error, rf'^sendmail\.py: cannot send the message: \d+: {text} message', f'error of {text}')

        code, error = sendmail(MESSAGE, '-t', '--subject', 'me@example.com', GMAIL_EMULATOR_HOST='')
        is_ok(code, 78, 'subject without the key of a service account')
        like_ok(error, r'--subject needs the key of a service account', 'error of the configuration')

        done = subprocess.run([sys.executable, EXAMPLE, '--help'], capture_output=True, check=False, env=env)
        like_ok(done.stdout.decode(), r'^Usage: sendmail\.py ', 'usage')

    with subtest('SMTP server'):
        smtp_port, _ = listen()
        stderr = tmp.child('stderr')
        with stderr.open('w') as log:
            daemon = subprocess.Popen(
                [sys.executable, EXAMPLE, '-bd', '--listen', f'127.0.0.1:{smtp_port}'],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=log,
            )
        try:
            wait_for(daemon, smtp_port)
            with smtplib.SMTP('127.0.0.1', smtp_port, timeout=10) as smtp:
                code, extensions = smtp.ehlo()
                is_ok(code, 250, 'EHLO')
                is_ok(extensions.decode().split('\n')[1:], ['SIZE 36700160', '8BITMIME', 'PIPELINING'],
                      'extensions of EHLO')  # fmt: skip
                message = b'To: alice@example.com\r\nSubject: Hello\r\n\r\nHello,\r\n.\r\n..two dots\r\n'
                is_ok(smtp.sendmail('app@example.com', ['alice@example.com', 'carol@example.com'], message), {},
                      'message of SMTP')  # fmt: skip
                is_ok(
                    last()['message'],
                    'From: app@example.com\r\nBcc: carol@example.com\r\nTo: alice@example.com\r\nSubject: Hello\r\n\r\n'
                    'Hello,\r\n.\r\n..two dots\r\n',
                    'message with the From of MAIL FROM, the Bcc of RCPT TO, and the dots of the client left out',
                )

                for text, status in (('Forbidden', 550), ('Invalid', 554), ('Unavailable', 451)):
                    try:
                        smtp.sendmail('app@example.com', ['alice@example.com'], f'Subject: {text}\r\n\r\nx\r\n')
                        fail(f'reply of {text}')
                    except smtplib.SMTPDataError as e:
                        is_ok(e.smtp_code, status, f'reply of {text}')

                is_ok(smtp.docmd('DATA')[0], 503, 'DATA without RCPT')
                is_ok(smtp.docmd('RCPT TO:<alice@example.com>')[0], 503, 'RCPT without MAIL')
                is_ok(smtp.docmd('MAIL FROM:<app@example.com> SIZE=99999999')[0], 552, 'SIZE over the limit')
                is_ok(smtp.docmd('MAIL FROM app@example.com')[0], 501, 'syntax of MAIL')
                is_ok(smtp.docmd('AUTH PLAIN AGFwcABzZWNyZXQ=')[0], 502, 'no AUTH')
                is_ok(smtp.docmd('STARTTLS')[0], 502, 'no STARTTLS')
                is_ok(smtp.docmd('VRFY alice')[0], 252, 'VRFY')
                is_ok(smtp.docmd('NOOP')[0], 250, 'NOOP')
                is_ok(smtp.docmd('BOGUS')[0], 500, 'unknown command')

            # The commands of PIPELINING, of a message and of the ones after it, which wait for the reply of the Gmail API
            with socket.create_connection(('127.0.0.1', smtp_port), timeout=10) as client:
                stream = client.makefile('rb')
                stream.readline()
                client.sendall(b'EHLO test\r\nMAIL FROM:<app@example.com>\r\nRCPT TO:<bob@example.com>\r\nDATA\r\n')
                replies = [stream.readline() for _ in range(7)]
                is_ok([reply[:4] for reply in replies[4:]], [b'250 ', b'250 ', b'354 '], 'replies of PIPELINING')
                client.sendall(b'Subject: Pipelined\r\n\r\nx\r\n.\r\nRSET\r\nNOOP\r\nQUIT\r\n')
                replies = [stream.readline() for _ in range(4)]
                like_ok(replies[0].decode(), r'^250 2\.0\.0 OK m\d+\r\n$', 'message sent before the commands after it')
                is_ok([reply[:4] for reply in replies[1:]], [b'250 ', b'250 ', b'221 '], 'commands after the message')
                is_ok(stream.read(), b'', 'connection closed after QUIT')
                like_ok(last()['message'], r'^From: app@example\.com\r\nBcc: bob@example\.com\r\nSubject: Pipelined\r\n',
                        'message of PIPELINING')  # fmt: skip
        finally:
            stop = time.monotonic()
            daemon.terminate()
            daemon.wait()
        is_ok(daemon.returncode, 0, 'server stopped of SIGTERM')
        ok(time.monotonic() - stop < 5, 'server without connections stopped at once, of the wakeup of the signal')
        is_ok(stderr.slurp().decode(), '', 'nothing on the standard error of the server')
finally:
    gmail.terminate()
    gmail.wait()

done_testing()
