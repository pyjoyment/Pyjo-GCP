import Pyjo.Exception
import Pyjo.GCP.Call
import Pyjo.GCP.Client
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.Chain
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.Impersonated
import Pyjo.GCP.Credentials.ServiceAccount
import Pyjo.GCP.Error
import Pyjo.UserAgent

from Pyjo.Util import getenv

import email.parser
import email.utils
import re
import sys


# sendmail of the Gmail API: a message of the standard input, sent as the user of the credentials, with the options of
# sendmail that PHP, cron and the others give it, so that sendmail_path of php.ini can be:
# sendmail_path = "/usr/bin/python3 /opt/pyjo-gcp/examples/sendmail.py --subject noreply@example.com -t -i"

USAGE = """\
Usage: sendmail.py [--subject EMAIL] [--impersonate-service-account EMAIL] [-t] [-i] [-f SENDER] [-F NAME]
                   [RECIPIENT ...] < MESSAGE
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
        if m := re.fullmatch(r'--(subject|impersonate-service-account)(?:=(.*))?', arg):
            if (value := m[2]) is None:
                value = args.pop(0) if args else fail(EX_USAGE, f'{arg} needs a value')
            opts['subject' if m[1] == 'subject' else 'impersonate'] = value
        elif arg.startswith('--'):
            fail(EX_USAGE, f'unknown option {arg}\n{USAGE}')
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


# The headers that the message needs, before the ones that it has: From of -f and -F without one, and Bcc of the
# recipients of the arguments that its headers do not have, as Gmail sends to the recipients of the headers, To, Cc
# and Bcc, which it leaves out of the message, and not to an envelope of its own
def complete(message, opts):
    head, _, _ = message.partition(b'\r\n\r\n')
    headers = email.parser.BytesHeaderParser().parsebytes(head + b'\r\n\r\n')
    added = []
    if headers.get('From') is None and opts['sender']:
        added.append(f'From: {email.utils.formataddr((opts["name"] or "", opts["sender"]))}')
    known = addresses(headers, 'To', 'Cc', 'Bcc')
    if missing := [r for r in opts['recipients'] if email.utils.parseaddr(r)[1].lower() not in known]:
        added.append(f'Bcc: {", ".join(missing)}')
    if not opts['headers'] and not opts['recipients']:
        fail(EX_USAGE, f'no recipients, of the arguments or of -t\n{USAGE}')
    if not known and not opts['recipients']:
        fail(EX_USAGE, 'no recipients in the To, Cc and Bcc headers of the message')
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


def main():
    opts = options(sys.argv[1:])
    message = complete(read_message(opts['dots']), opts)
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
        try:
            gmail.call(SendMessage(message))
        except Pyjo.GCP.Error.object as e:
            fail(exit_code(e), f'cannot send the message: {e.message}')
        except Pyjo.Exception.object as e:
            fail(EX_UNAVAILABLE, f'cannot send the message: {e.message}')
    finally:
        ua.close()


if __name__ == '__main__':
    main()
