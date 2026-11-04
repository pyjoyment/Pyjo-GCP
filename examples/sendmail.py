import Pyjo.Exception
import Pyjo.GCP.Call
import Pyjo.GCP.Client
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.Chain
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.Impersonated
import Pyjo.GCP.Credentials.ServiceAccount
import Pyjo.GCP.Error
import Pyjo.IOLoop
import Pyjo.UserAgent

from Pyjo.Util import getenv

import email.parser
import email.utils
import re
import signal
import socket
import sys


# sendmail of the Gmail API: a message of the standard input, sent as the user of the credentials, with the options of
# sendmail that PHP, cron and the others give it, so that sendmail_path of php.ini can be:
# sendmail_path = "/usr/bin/python3 /opt/pyjo-gcp/examples/sendmail.py --subject noreply@example.com -t -i"
# or, with -bd of sendmail, an SMTP server of the Gmail API for the programs that send with SMTP

USAGE = """\
Usage: sendmail.py [--subject EMAIL] [--impersonate-service-account EMAIL] [-t] [-i] [-f SENDER] [-F NAME]
                   [RECIPIENT ...] < MESSAGE
       sendmail.py [--subject EMAIL] [--impersonate-service-account EMAIL] -bd [--listen ADDRESS:PORT]
"""

# The exit codes of sysexits.h, as sendmail has them, of which PHP and the others tell a message that is not sent; not
# EX_TEMPFAIL of a message that sendmail keeps to send it later, which PHP takes for a message that is sent, as the
# example keeps none
EX_USAGE = 64
EX_UNAVAILABLE = 69
EX_NOPERM = 77
EX_CONFIG = 78

# The token sends messages only, as the user of the credentials, or of the subject of a service account of the
# domain-wide delegation of Google Workspace
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def fail(code, message):
    print(f'sendmail.py: {message}', file=sys.stderr)
    sys.exit(code)


# The options of sendmail, by hand, as Pyjo.GetOpt would take -i for an abbreviation of a long option: -t and -i of
# PHP, -f and -F of the sender, with the value in the option or after it, the others of sendmail ignored, as -oi of
# -i, -odi and -v of cron, and the long options of the example, or their environment variables
def options(argv):
    opts = {
        'subject': getenv('GMAIL_SUBJECT'),
        'impersonate': getenv('CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT'),
        'headers': False,
        'dots': True,
        'sender': None,
        'name': None,
        'recipients': [],
        'daemon': False,
        'listen': '127.0.0.1:2525',
    }
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == '--':
            opts['recipients'] += args
            break
        if arg in ('-h', '--help'):
            sys.stdout.write(USAGE)
            sys.exit(0)
        if m := re.fullmatch(r'--(subject|impersonate-service-account|listen)(?:=(.*))?', arg):
            if (value := m[2]) is None:
                value = args.pop(0) if args else fail(EX_USAGE, f'{arg} needs a value')
            opts[{'impersonate-service-account': 'impersonate'}.get(m[1], m[1])] = value
        elif arg.startswith('--'):
            fail(EX_USAGE, f'unknown option {arg}\n{USAGE}')
        elif arg == '-bd':
            opts['daemon'] = True
        elif arg == '-t':
            opts['headers'] = True
        elif arg in ('-i', '-oi'):
            opts['dots'] = False
        elif arg[:2] in ('-f', '-F', '-r'):
            value = arg[2:] or (args.pop(0) if args else fail(EX_USAGE, f'{arg} needs a value'))
            opts['name' if arg[:2] == '-F' else 'sender'] = value
        elif arg.startswith('-'):
            continue
        else:
            opts['recipients'].append(arg)
    return opts


# The message of the standard input, which ends with a line of a dot without -i, as sendmail has it, with the line
# breaks of CRLF of RFC 5322, as PHP gives LF only
def read_message(dots):
    lines = []
    for line in sys.stdin.buffer:
        line = line.rstrip(b'\r\n')
        if dots and line == b'.':
            break
        lines.append(line)
    return b'\r\n'.join(lines) + b'\r\n'


def addresses(headers, *names):
    values = [value for name in names for value in headers.get_all(name, [])]
    return {address.lower() for _, address in email.utils.getaddresses(values) if address}


# The recipients of the headers of a message, To, Cc and Bcc
def recipients_of(message):
    head, _, _ = message.partition(b'\r\n\r\n')
    return addresses(email.parser.BytesHeaderParser().parsebytes(head + b'\r\n\r\n'), 'To', 'Cc', 'Bcc')


# The headers that the message needs, before the ones that it has: From of the sender without one, and Bcc of the
# recipients of the envelope, of the arguments or of RCPT TO, that its headers do not have, as Gmail sends to the
# recipients of the headers, To, Cc and Bcc, which it leaves out of the message, and not to an envelope of its own
def complete(message, sender=None, name=None, recipients=()):
    head, _, _ = message.partition(b'\r\n\r\n')
    headers = email.parser.BytesHeaderParser().parsebytes(head + b'\r\n\r\n')
    added = []
    if headers.get('From') is None and sender:
        added.append(f'From: {email.utils.formataddr((name or "", sender))}')
    known = addresses(headers, 'To', 'Cc', 'Bcc')
    if missing := [r for r in recipients if email.utils.parseaddr(r)[1].lower() not in known]:
        added.append(f'Bcc: {", ".join(missing)}')
    return ''.join(f'{header}\r\n' for header in added).encode() + message


# The credentials of the Gmail API: of the service account that the Application Default Credentials impersonate, with
# the subject of its domain-wide delegation, of signJwt, without a key; of the key of a service account of
# GOOGLE_APPLICATION_CREDENTIALS with the subject; or of the Application Default Credentials of a user that has the
# scope of Gmail of its login
def credentials(opts, ua):
    if target := opts['impersonate']:
        source = Pyjo.GCP.Credentials.Chain.new(ua=ua)
        return Pyjo.GCP.Credentials.Impersonated.new(
            source=source, target_principal=target, subject=opts['subject'], scopes=SCOPES, ua=ua
        )
    if not opts['subject']:
        return Pyjo.GCP.Credentials.Chain.new(scopes=SCOPES, ua=ua)
    config = Pyjo.GCP.Config.new()
    path = config.credentials_file or fail(
        EX_CONFIG, '--subject needs the key of a service account of GOOGLE_APPLICATION_CREDENTIALS, or'
        ' --impersonate-service-account'
    )  # fmt: skip
    provider = Pyjo.GCP.Credentials.File.new(path=path, config=config, scopes=SCOPES, ua=ua).provider_of(
        config.credentials_info(path), path
    )
    if not isinstance(provider, Pyjo.GCP.Credentials.ServiceAccount.object):
        fail(EX_CONFIG, f'--subject needs the key of a service account: {path}')
    provider.subject = opts['subject']
    return provider


# messages.send of the media upload, of the whole message of RFC 822 up to 35 MB, which the JSON of raw with base64
# would make larger, as the user of the token, "me"
class SendMessage(Pyjo.GCP.Call.object):
    def __init__(self, message):
        super().__init__('POST', '/upload/gmail/v1/users/me/messages/send', query={'uploadType': 'media'})
        self.message = message

    def build_tx(self, ua, url):
        url = Pyjo.GCP.Call.url_for(url, self.path, self.query)
        return ua.build_tx(self.method, url, {**self.headers, 'Content-Type': 'message/rfc822'}, self.message)


def exit_code(e):
    return EX_NOPERM if e.code in (401, 403) else EX_UNAVAILABLE


# The message of the standard input, of the recipients of the arguments, or of its headers with -t
def send(opts, gmail):
    message = read_message(opts['dots'])
    if not opts['headers'] and not opts['recipients']:
        fail(EX_USAGE, f'no recipients, of the arguments or of -t\n{USAGE}')
    if not opts['recipients'] and not recipients_of(message):
        fail(EX_USAGE, 'no recipients in the To, Cc and Bcc headers of the message')
    message = complete(message, opts['sender'], opts['name'], opts['recipients'])
    try:
        gmail.call(SendMessage(message))
    except Pyjo.GCP.Error.object as e:
        fail(exit_code(e), f'cannot send the message: {e.message}')
    except Pyjo.Exception.object as e:
        fail(EX_UNAVAILABLE, f'cannot send the message: {e.message}')


# The size of a message of the media upload of messages.send, 35 MB, which SIZE of EHLO tells the client
MAX_SIZE = 35 * 1024 * 1024
MAX_RECIPIENTS = 100
HOSTNAME = socket.gethostname()


# An SMTP session of RFC 5321, of a client of -bd, whose messages go to the Gmail API: a reply for each command, a
# message of DATA that ends with a line of a dot, whose dots of the client before a line are left out, and the commands
# that the client sends before a reply, of PIPELINING, kept in the buffer until the message before them is sent, as the
# Gmail API answers in the event loop of the server; there is no AUTH, so the server listens on the loopback by default
class Session:
    def __init__(self, stream, gmail):
        self.stream = stream
        self.gmail = gmail
        self.buffer = b''
        self.busy = False
        self.closed = False
        self.reset()
        stream.timeout = 300
        stream.on('read', lambda stream, chunk: self.read(chunk))
        stream.on('close', lambda stream: setattr(self, 'closed', True))
        self.reply(220, f'{HOSTNAME} ESMTP sendmail.py of the Gmail API')

    def reset(self):
        self.sender = None
        self.recipients = []
        self.data = None
        self.size = 0

    def reply(self, code, *lines):
        if self.closed:
            return
        for i, line in enumerate(lines):
            self.stream.write(f'{code}{"-" if i < len(lines) - 1 else " "}{line}\r\n'.encode())

    def read(self, chunk):
        self.buffer += chunk
        self.process()

    def process(self):
        while not self.busy and not self.closed and (end := self.buffer.find(b'\n')) != -1:
            line, self.buffer = self.buffer[:end].rstrip(b'\r'), self.buffer[end + 1 :]
            if self.data is None:
                self.command(line.decode('utf-8', 'replace'))
            elif line == b'.':
                self.finish()
            else:
                self.size += len(line) + 2
                if self.size <= MAX_SIZE:
                    self.data.append(line[1:] if line.startswith(b'.') else line)
        if self.data is None and len(self.buffer) > 4096:
            self.buffer = b''
            self.reply(500, '5.5.6 Line too long')

    def command(self, line):
        verb, _, arg = line.partition(' ')
        verb = verb.upper()
        if verb == 'EHLO':
            self.reset()
            self.reply(250, HOSTNAME, f'SIZE {MAX_SIZE}', '8BITMIME', 'PIPELINING')
        elif verb == 'HELO':
            self.reset()
            self.reply(250, HOSTNAME)
        elif verb == 'MAIL':
            if not (m := re.fullmatch(r'(?i)FROM:\s*<([^>]*)>(.*)', arg)):
                return self.reply(501, '5.5.4 Syntax: MAIL FROM:<address>')
            if self.sender is not None:
                return self.reply(503, '5.5.1 Sender already given')
            if (size := re.search(r'(?i)\bSIZE=(\d+)', m[2])) and int(size[1]) > MAX_SIZE:
                return self.reply(552, '5.3.4 Message too big')
            self.sender = m[1]
            self.reply(250, '2.1.0 OK')
        elif verb == 'RCPT':
            if self.sender is None:
                return self.reply(503, '5.5.1 MAIL first')
            if not (m := re.fullmatch(r'(?i)TO:\s*<([^>]+)>.*', arg)):
                return self.reply(501, '5.5.4 Syntax: RCPT TO:<address>')
            if len(self.recipients) >= MAX_RECIPIENTS:
                return self.reply(452, '4.5.3 Too many recipients')
            self.recipients.append(m[1])
            self.reply(250, '2.1.5 OK')
        elif verb == 'DATA':
            if not self.recipients:
                return self.reply(503, '5.5.1 RCPT first')
            self.data = []
            self.reply(354, 'End data with <CR><LF>.<CR><LF>')
        elif verb == 'RSET':
            self.reset()
            self.reply(250, '2.0.0 OK')
        elif verb == 'NOOP':
            self.reply(250, '2.0.0 OK')
        elif verb == 'VRFY':
            self.reply(252, '2.1.5 Cannot VRFY user')
        elif verb == 'QUIT':
            self.reply(221, '2.0.0 Bye')
            self.stream.close_gracefully()
        elif verb in ('STARTTLS', 'AUTH'):
            self.reply(502, f'5.5.1 {verb} not implemented')
        else:
            self.reply(500, '5.5.2 Command not recognized')

    # The message to the Gmail API, with the From of MAIL FROM and the recipients of RCPT TO, whose reply waits for the
    # one of the API: a temporary error of 451, which the client tries again, and a permanent one of 550 or 554
    def finish(self):
        if self.size > MAX_SIZE:
            self.reset()
            return self.reply(552, '5.3.4 Message too big')
        message = complete(b'\r\n'.join(self.data or []) + b'\r\n', self.sender, None, self.recipients)
        self.busy = True

        def sent(result):
            self.reply(250, f'2.0.0 OK {result.get("id", "") if isinstance(result, dict) else ""}'.rstrip())

        def failed(e):
            if isinstance(e, Pyjo.GCP.Error.object) and e.code in (401, 403):
                self.reply(550, f'5.7.1 {e.message}')
            elif isinstance(e, Pyjo.GCP.Error.object) and e.code != 429 and e.code < 500:
                self.reply(554, f'5.6.0 {e.message}')
            else:
                self.reply(451, f'4.3.0 {getattr(e, "message", e)}')

        def done(*_):
            self.reset()
            self.busy = False
            self.process()

        self.gmail.call_p(SendMessage(message)).then(sent, failed).then(done, done)


# The SMTP server of -bd on the loopback by default, until SIGINT or SIGTERM stops it
def daemon(opts, gmail):
    host, _, port = opts['listen'].rpartition(':')
    if not port.isdigit():
        fail(EX_USAGE, f'--listen of ADDRESS:PORT, not {opts["listen"]}')
    try:
        Pyjo.IOLoop.server(lambda loop, stream, id: Session(stream, gmail), address=host or '127.0.0.1', port=int(port))
    except OSError as e:
        fail(EX_CONFIG, f'cannot listen on {opts["listen"]}: {e.strerror or e}')
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, lambda *_: Pyjo.IOLoop.stop())

    # A socket pair that Python writes to on a signal wakes the event loop up, as Pyjo.Server.Daemon does: Python
    # repeats a select that a signal interrupts, so that a server without connections would not see its stop
    waker, wakee = socket.socketpair()
    waker.setblocking(False)
    wakee.setblocking(False)
    signal.set_wakeup_fd(waker.fileno())
    reactor = Pyjo.IOLoop.singleton.reactor
    reactor.io(wakee, lambda reactor, writable: wakee.recv(4096)).watch(wakee, True, False)
    try:
        Pyjo.IOLoop.start()
    finally:
        signal.set_wakeup_fd(-1)
        reactor.remove(wakee)
        waker.close()
        wakee.close()


def main():
    opts = options(sys.argv[1:])
    ua = Pyjo.UserAgent.new()
    gmail = Pyjo.GCP.Client.new(service='gmail', credentials=credentials(opts, ua), ua=ua)
    try:
        # The credentials first, of an error of the configuration, as a subject that the domain-wide delegation does not
        # have, where an error of the call may be of now only
        if not gmail.anonymous:
            try:
                gmail.credentials.credentials()
            except Pyjo.Exception.object as e:
                fail(EX_CONFIG, f'cannot get the credentials: {e.message}')
        if opts['daemon']:
            daemon(opts, gmail)
        else:
            send(opts, gmail)
    finally:
        ua.close()


if __name__ == '__main__':
    main()
