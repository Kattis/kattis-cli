#!/usr/bin/env python
from __future__ import print_function
import optparse
import os
import sys
import itertools
import mimetypes
import random
import string

# Python 2/3 compatibility
if sys.version_info[0] >= 3:
    import configparser
    import urllib.parse
    import urllib.request
    import urllib.error

    def form_body(form):
        return str(form).encode('utf-8')
else:
    # Python 2, import modules with Python 3 names
    import ConfigParser as configparser
    import urllib
    import urllib2
    urllib.request = urllib.error = urllib2
    urllib.parse = urllib

    def form_body(form):
        return str(form)

# End Python 2/3 compatibility

_DEFAULT_CONFIG = '/usr/local/etc/kattisrc'
_VERSION = 'Version: $Version: $'
_LANGUAGE_GUESS = {
    '.java': 'Java',
    '.c': 'C',
    '.cpp': 'C++',
    '.h': 'C++',
    '.cc': 'C++',
    '.cxx': 'C++',
    '.c++': 'C++',
    '.py': 'Python',
    '.cs': 'C#',
    '.c#': 'C#',
    '.go': 'Go',
    '.m': 'Objective-C',
    '.hs': 'Haskell',
    '.pl': 'Prolog',
    '.js': 'JavaScript',
    '.php': 'PHP',
    '.rb': 'Ruby'
}
_GUESS_MAINCLASS = set(['Java', 'Python'])


class MultiPartForm(object):
    """MultiPartForm based on code from
    http://blog.doughellmann.com/2009/07/pymotw-urllib2-library-for-opening-urls.html

    This since the default libraries still lack support for posting
    multipart/form-data (which is required to post files in HTTP).
    http://bugs.python.org/issue3244
    """

    def __init__(self):
        self.form_fields = []
        self.files = []
        self.boundary = ''.join(
            random.SystemRandom().choice(string.ascii_letters)
            for _ in range(50))
        return

    def get_content_type(self):
        return 'multipart/form-data; boundary=%s' % self.boundary

    @staticmethod
    def escape_field_name(name):
        """Should escape a field name escaped following RFC 2047 if needed.
        Skipped for now as we only call it with hard coded constants.
        """
        return name

    def add_field(self, name, value):
        """Add a simple field to the form data."""
        if value is None:
            # Assume the field is empty
            value = ""
        # ensure value is a string
        value = str(value)
        self.form_fields.append((name, value))
        return

    def add_file(self, fieldname, filename, file_handle, mimetype=None):
        """Add a file to be uploaded."""
        body = file_handle.read()
        if mimetype is None:
            mimetype = (mimetypes.guess_type(filename)[0] or
                        'application/octet-stream')
        self.files.append((fieldname, filename, mimetype, body))
        return

    def make_request(self, url):
        body = form_body(self)
        request = urllib.request.Request(url, data=body)
        request.add_header('Content-type', self.get_content_type())
        request.add_header('Content-length', len(body))
        return request

    def __str__(self):
        """Return a string representing the form data, including attached
        files."""
        # Build a list of lists, each containing "lines" of the
        # request.  Each part is separated by a boundary string.
        # Once the list is built, return a string where each
        # line is separated by '\r\n'.
        parts = []
        part_boundary = '--' + self.boundary

        # Add the form fields
        parts.extend([part_boundary,
                      ('Content-Disposition: form-data; name="%s"' %
                       self.escape_field_name(name)),
                      '',
                      value]
                     for name, value in self.form_fields)

        # Add the files to upload
        parts.extend([part_boundary,
                      ('Content-Disposition: file; name="%s"; filename="%s"' %
                       (self.escape_field_name(field_name), filename)),
                      # FIXME: filename should be escaped using RFC 2231
                      'Content-Type: %s' % content_type,
                      '',
                      body]
                     for field_name, filename, content_type, body in self.files
                     )

        # Flatten the list and add closing boundary marker,
        # then return CR+LF separated data
        flattened = list(itertools.chain(*parts))
        flattened.append('--' + self.boundary + '--')
        flattened.append('')
        return '\r\n'.join(flattened)


class ConfigError(Exception):
    pass


def get_url(cfg, option, default):
    if cfg.has_option('kattis', option):
        return cfg.get('kattis', option)
    else:
        return 'https://%s/%s' % (cfg.get('kattis', 'hostname'), default)


def get_config():
    """Returns a ConfigParser object for the .kattisrc file(s)
    """
    cfg = ConfigParser()
    if os.path.exists(_DEFAULT_CONFIG):
        cfg.read(_DEFAULT_CONFIG)

    if not cfg.read([os.path.join(os.getenv('HOME'), '.kattisrc'),
                     os.path.join(os.path.dirname(sys.argv[0]), '.kattisrc')]):
        raise ConfigError('''\
I failed to read in a config file from your home directory or from the
same directory as this script. Please go to your Kattis installation
to download a .kattisrc file.

The file should look something like this:
[user]
username: yourusername
token: *********

[kattis]
loginurl: https://<kattis>/login
submissionurl: https://<kattis>/submit''')
    return cfg


def login(login_url, username, password=None, token=None):
    """Log in to Kattis.

    At least one of password or token needs to be provided.

    Returns a urllib OpenerDirector object that can be used to access
    URLs while logged in.
    """
    login_args = {'user': username, 'script': 'true'}
    if password:
        login_args['password'] = password
    if token:
        login_args['token'] = token

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    opener.open(login_url, urllib.parse.urlencode(login_args).encode('ascii'))
    return opener


def login_from_config(cfg):
    """Log in to Kattis using the access information in a kattisrc file

    Returns a urllib OpenerDirector object that can be used to access
    URLs while logged in.
    """
    username = cfg.get('user', 'username')
    password = token = None
    try:
        password = cfg.get('user', 'password')
    except configparser.NoOptionError:
        pass
    try:
        token = cfg.get('user', 'token')
    except configparser.NoOptionError:
        pass
    if password is None and token is None:
        raise ConfigError('''\
Your .kattisrc file appears corrupted. It must provide a token (or a
KATTIS password).

Please download a new .kattisrc file''')

    loginurl = get_url(cfg, 'loginurl', 'login')
    return login(loginurl, username, password, token)


def submit(url_opener, submit_url, problem, language, files,
           mainclass=None, tag=None):
    """Make a submission.

    The url_opener argument is an OpenerDirector object to use (as
    returned by the login() function)
    """
    if mainclass is None:
        mainclass = ""
    if tag is None:
        tag = ""

    form = MultiPartForm()
    form.add_field('submit', 'true')
    form.add_field('submit_ctr', '2')
    form.add_field('language', language)
    form.add_field('mainclass', mainclass)
    form.add_field('problem', problem)
    form.add_field('tag', tag)
    form.add_field('script', 'true')

    if len(files) > 0:
        for filename in files:
            form.add_file('sub_file[]', os.path.basename(filename),
                          open(filename))

    request = form.make_request(submit_url)

    return url_opener.open(request).read().decode('utf-8').replace("<br />",
                                                                   "\n")


def confirm_or_die(problem, language, files, mainclass, tag):
    print('Problem:', problem)
    print('Language:', language)
    print('Files:', ', '.join(files))
    if mainclass:
        print('Mainclass:', mainclass)
    if tag:
        print('Tag:', tag)
    print('Submit (y/N)?')
    if sys.stdin.readline().upper()[:-1] != 'Y':
        print('Cancelling')
        sys.exit(1)


def main():
    opt = optparse.OptionParser()
    opt.add_option('-p', '--problem', dest='problem', metavar='PROBLEM',
                   help=''''Submit to problem PROBLEM.
Overrides default guess (first part of first filename)''', default=None)
    opt.add_option('-m', '--mainclass', dest='mainclass', metavar='CLASS',
                   help='''Sets mainclass to CLASS.
Overrides default guess (first part of first filename)''', default=None)
    opt.add_option('-l', '--language', dest='language', metavar='LANGUAGE',
                   help='''Sets language to LANGUAGE.
Overrides default guess (based on suffix of first filename)''', default=None)
    opt.add_option('-t', '--tag', dest='tag', metavar='TAG',
                   help=optparse.SUPPRESS_HELP, default="")
    opt.add_option('-f', '--force', dest='force',
                   help='Force, no confirmation prompt before submission',
                   action="store_true", default=False)

    opts, args = opt.parse_args()

    if len(args) == 0:
        opt.print_help()
        sys.exit(1)

    problem, ext = os.path.splitext(os.path.basename(args[0]))
    language = _LANGUAGE_GUESS.get(ext, None)
    mainclass = problem if language in _GUESS_MAINCLASS else None
    tag = opts.tag

    if opts.problem:
        problem = opts.problem
    if opts.mainclass is not None:
        mainclass = opts.mainclass
    if opts.language:
        language = opts.language

    if language is None:
        print('''\
No language specified, and I failed to guess language from filename
extension "%s"''' % (ext))
        sys.exit(1)

    seen = set()
    files = []
    for arg in args:
        if arg not in seen:
            files.append(arg)
        seen.add(arg)

    try:
        cfg = get_config()
        opener = login_from_config(cfg)
    except ConfigError as exc:
        print(exc)
        sys.exit(1)
    except urllib.error.URLError as exc:
        if hasattr(exc, 'code'):
            print('Login failed.')
            if exc.code == 403:
                print('Incorrect username or password/token (403)')
            elif exc.code == 404:
                print("Incorrect login URL (404)")
            else:
                print(exc)
        else:
            print('Failed to connect to Kattis server.')
            print('Reason: ', exc.reason)
        sys.exit(1)

    submit_url = get_url(cfg, 'submissionurl', 'submit')

    if not opts.force:
        confirm_or_die(problem, language, files, mainclass, tag)

    try:
        result = submit(opener, submit_url, problem, language, files, mainclass, tag)
    except urllib.error.URLError as exc:
        if hasattr(exc, 'code'):
            print('Submission failed.')
            if exc.code == 403:
                print('Access denied (403)')
            elif exc.code == 404:
                print('Incorrect submit URL (404)')
            else:
                print(exc)
        else:
            print('Failed to connect to Kattis server.')
            print('Reason: ', exc.reason)
        sys.exit(1)

    print(result)


if __name__ == '__main__':
    main()
