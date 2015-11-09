#!/usr/bin/env python
import ConfigParser
import optparse
import os
import sys
import itertools
import mimetools
import mimetypes
import urllib
import urllib2
import traceback


_DEFAULT_CONFIG='/usr/local/etc/kattisrc'
_VERSION = 'Version: $Version: $'
_LANGUAGE_GUESS = { '.java' : 'Java', '.c' : 'C', '.cpp' : 'C++', '.h' : 'C++', '.cc' : 'C++', '.cxx' : 'C++', '.c++' : 'C++', '.py' : 'Python', '.cs': 'C#', '.c#': 'C#', '.go': 'Go', '.m' : 'Objective-C', '.hs' : 'Haskell', '.pl' : 'Prolog', '.js': 'JavaScript', '.php': 'PHP', '.rb' : 'Ruby' }
_GUESS_MAINCLASS  = set(['Java', 'Python'])

"""MultiPartForm based on code from
http://blog.doughellmann.com/2009/07/pymotw-urllib2-library-for-opening-urls.html

This since the default libraries still lack support for posting
multipart/form-data (which is required to post files in HTTP).
http://bugs.python.org/issue3244
"""
class MultiPartForm(object):
	"""Accumulate the data to be used when posting a form."""

	def __init__(self):
		self.form_fields = []
		self.files = []
		self.boundary = mimetools.choose_boundary()
		return

	def get_content_type(self):
		return 'multipart/form-data; boundary=%s' % self.boundary

	def escape_field_name(self, name):
		"""Should escape a field name escaped following RFC 2047 if needed.
		Skipped for now as we only call it with hard coded constants.
		"""
		return name

	def add_field(self, name, value):
		"""Add a simple field to the form data."""
		if(value==None):
			#Assume the field is empty
			value=""
		#ensure value is a string
		value=str(value)
		self.form_fields.append((name, value))
		return

	def add_file(self, fieldname, filename, fileHandle, mimetype=None):
		"""Add a file to be uploaded."""
		body = fileHandle.read()
		if mimetype is None:
			mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
		self.files.append((fieldname, filename, mimetype, body))
		return

	def add_to_request(self, request):
		body = str(self)
		request.add_header('Content-type', self.get_content_type())
		request.add_header('Content-length', len(body))
		request.add_data(body)

	def __str__(self):
		"""Return a string representing the form data, including attached files."""
		# Build a list of lists, each containing "lines" of the
		# request.  Each part is separated by a boundary string.
		# Once the list is built, return a string where each
		# line is separated by '\r\n'.  
		parts = []
		part_boundary = '--' + self.boundary

		# Add the form fields
		parts.extend(
			[ part_boundary,
			  'Content-Disposition: form-data; name="%s"' % self.escape_field_name(name),
			  '',
			  value,
			]
			for name, value in self.form_fields
			)

		# Add the files to upload
		parts.extend(
			[ part_boundary,
			  'Content-Disposition: file; name="%s"; filename="%s"' % \
				  (self.escape_field_name(field_name), filename),
				  # FIXME: filename should be escaped using RFC 2231
			  'Content-Type: %s' % content_type,
			  '',
			  body,
			]
			for field_name, filename, content_type, body in self.files
			)

		# Flatten the list and add closing boundary marker,
		# then return CR+LF separated data
		flattened = list(itertools.chain(*parts))
		flattened.append('--' + self.boundary + '--')
		flattened.append('')
		return '\r\n'.join(flattened)


_RC_HELP = \
'''I failed to read in a config file from your home directory or from the same directory
as this script. Please go to your Kattis installation to download a .kattisrc file.

The file should look something like:
[user]
username: yourusername
token: *********

[kattis]
loginurl: https://<kattis>/login
submissionurl: https://<kattis>/submit
'''


def get_url(cfg, option, default):
	if cfg.has_option('kattis', option):
		return cfg.get('kattis', option)
	else:
		return 'https://%s/%s' % (cfg.get('kattis', 'hostname'), default)

def confirm_or_die(problem, language, files, mainclass, tag):
	print 'Problem:', problem
	print 'Language:', language
	print 'Files:', ', '.join(files)
	if mainclass:
		print 'Mainclass:', mainclass
	if tag:
		print 'Tag:', tag
	print 'Submit (y/N)?'
	if sys.stdin.readline().upper()[:-1] != 'Y':
		print 'Cancelling'
		sys.exit(1)

def main():
	opt = optparse.OptionParser()
	opt.add_option('-p', '--problem', dest='problem', metavar='PROBLEM', help='Submit to problem PROBLEM. Overrides default guess (first part of first filename)', default=None)
	opt.add_option('-m', '--mainclass', dest='mainclass', metavar='CLASS', help='Sets mainclass to CLASS. Overrides default guess (first part of first filename)', default=None)
	opt.add_option('-l', '--language', dest='language', metavar='LANGUAGE', help='Sets language to LANGUAGE. Overrides default guess (based on suffix of first filename)', default=None)
	opt.add_option('-t', '--tag', dest='tag', metavar='TAG', help=optparse.SUPPRESS_HELP, default="")
	opt.add_option('-f', '--force', dest='force', help='Force, no confirmation prompt before submission', action="store_true", default=False)
	opt.add_option('-d', '--debug', dest='debug', help='Print debug info while running', action="store_true", default=False)

	opts, args = opt.parse_args()

	if len(args) == 0:
		opt.print_help()
		sys.exit(1)

	problem, ext = os.path.splitext(os.path.basename(args[0]))
	language = _LANGUAGE_GUESS.get(ext, None)
	mainclass = problem if language in _GUESS_MAINCLASS else None
	tag=opts.tag
	debug=opts.debug

	if opts.problem:
		problem = opts.problem
	if opts.mainclass is not None:
		mainclass = opts.mainclass
	if opts.language:
		language = opts.language

	if language == None:
		print 'No language specified, and I failed to guess language from filename extension "%s"' % (ext)
		sys.exit(1)

	seen = set()
	files = []
	for a in args:
		if a not in seen:
			files.append(a)
		seen.add(a)

	submit(problem, language, files, opts.force, mainclass, tag, debug=debug)

def submit(problem, language, files, force=True, mainclass=None, tag=None, username=None, password=None, token=None, debug=False):
	if(debug):
		print problem, language, files, force, mainclass, tag, username, password, token, debug
	cfg = ConfigParser.ConfigParser()
	if os.path.exists(_DEFAULT_CONFIG):
		cfg.read(_DEFAULT_CONFIG)

	if not cfg.read([os.path.join(os.getenv('HOME'), '.kattisrc'), os.path.join(os.path.dirname(sys.argv[0]), '.kattisrc')]):
		print _RC_HELP
		sys.exit(1)

	if(username==None):
		username = cfg.get('user', 'username')
	if(password==None):
		try:
			password = cfg.get('user', 'password')
		except:
			pass
	if(token==None):
		try:
			token = cfg.get('user', 'token')
		except:
			pass
	if(mainclass==None):
		mainclass=""
	if(tag==None):
		tag=""

	if password == None and token == None:
		print "Your .kattisrc file appears corrupted. It must provide a token (or a KATTIS password).\nPlease download a new .kattisrc file\n"
		sys.exit(1)
	
	opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
	urllib2.install_opener(opener)
	loginurl = get_url(cfg, 'loginurl', 'login')
	loginargs = { 'user' : username, 'script' : 'true' }
	if password:
		loginargs['password'] = password
	if token:
		loginargs['token'] = token
	try:
		urllib2.urlopen(loginurl, urllib.urlencode(loginargs))
	except urllib2.URLError, e:
		if hasattr(e, 'reason'):
			print 'Failed to connect to Kattis server.'
			print 'Reason: ', e.reason
		elif hasattr(e, 'code'):
			print 'Login failed.'
			if(e.code==403):
				print "Incorrect Username/Password"
			elif(e.code==404):
				print "Incorrect login URL (404)"
			else:
				print 'Error code: ', e.code
		sys.exit(1)
	if not force:
		confirm_or_die(problem, language, files, mainclass, tag)

	submission_url = get_url(cfg, 'submissionurl', 'judge_upload')
	form = MultiPartForm()
	form.add_field('submit', 'true')
	form.add_field('submit_ctr', '2')
	form.add_field('language', language)
	form.add_field('mainclass', mainclass)
	form.add_field('problem', problem)
	form.add_field('tag', tag)
	form.add_field('script', 'true')

	if(len(files)>0):
		for file in files:
			form.add_file('sub_file[]', os.path.basename(file), open(file))

	request = urllib2.Request(submission_url)
	form.add_to_request(request)
	try:
		print urllib2.urlopen(request).read().replace("<br />", "\n")
	except urllib2.URLError, e:
		if hasattr(e, 'reason'):
			print 'Failed to connect to Kattis server.'
			print 'Reason: ', e.reason
		elif hasattr(e, 'code'):
			print 'Login failed.'
			if(e.code==403):
				print "Access denied."
			elif(e.code==404):
				print "Incorrect submit URL (404)"
			else:
				print 'Error code: ', e.code
		sys.exit(1)

if __name__ == '__main__':
	main()
