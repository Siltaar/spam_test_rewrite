#!/usr/bin/python2
# coding: utf-8
# author : Simon Descarpentries, 2017-03
# licence: GPLv3

from __future__ import print_function
from sys import stdin, stderr, version_info
from email.parser import Parser
from email.header import decode_header
from email.header import make_header
from email.utils import getaddresses, parseaddr, parsedate_tz, mktime_tz, formatdate  # noqa
from curses.ascii import isalpha
from datetime import datetime, timedelta
from calendar import timegm  # noqa


def spam_test(stdin_eml, debug=0):
	eml = Parser().parsestr(stdin_eml)
	score = 0
	debug and print("%s " % eml.get('Subject', ''), end='', file=stderr)
	subj_len, subj_alpha_len = email_alpha_len(eml.get('Subject', ''), header_txt)

	if subj_alpha_len == 0 or subj_len // subj_alpha_len > 1:
		score += 1  # If no more than 1 ascii char over 2 in subject, I can't read it
		debug and print("subj %i/%i " % (subj_alpha_len, subj_len), end='', file=stderr)

	body_len, body_alpha_len = (0, 0)
	ctype=''

	for part in eml.walk() :
		ctype = part.get_content_type()

		if 'text' in ctype or 'pgp-encrypted' in ctype:
			# debug and print('ctype %s ' % part.get_content_type(), end='', file=stderr)
			body_len, body_alpha_len = email_alpha_len(part,
				lambda b : b.get_payload(decode=True)[:256])
			break

	if body_alpha_len == 0 or body_len // body_alpha_len > 1:
		score += 1
		debug and print("body %i/%i " % (body_alpha_len, body_len), end='', file=stderr)

	# if score > 0:
	from_len, from_alpha_len = email_alpha_len(parseaddr(eml.get('From', ''))[0],header_txt)

	if from_len > 0 and (from_alpha_len == 0 or from_len // from_alpha_len > 1):
		score += 1
		debug and print("from %i/%i " % (from_alpha_len, from_len), end='', file=stderr)

	text_parts = []
	html_parts = []

	for part in eml.walk() :
		ctype = part.get_content_type()

		if 'html' in ctype:
			html_parts.append(part)

	for part in html_parts:
		html_src = part.get_payload(decode=True)[:128]

		if b'<' not in html_src:  # looks like malformed HTML
			debug and print("\033[1;33mbad HTML\033[0m ", end='', file=stderr)
			score += 1

	recipient_count = len(getaddresses(eml.get_all('To', []) + eml.get_all('Cc', [])))

	if recipient_count == 0 or recipient_count > 9:
		score += 1  # If there is no or more than 9 recipients, it may be a spam
		debug and print("recs %i " % (recipient_count), end='', file=stderr)

	recv_dt = datetime.utcfromtimestamp(mktime_tz(parsedate_tz(
		eml.get('Received', 'Sat, 01 Jan 9999 01:01:01 +0000')[-30:])))
	eml_dt = datetime.utcfromtimestamp(mktime_tz(parsedate_tz(
		eml.get('Date', 'Sat, 01 Jan 0001 01:01:01 +0000'))))

	if eml_dt < recv_dt - timedelta(hours=6) or eml_dt > recv_dt + timedelta(hours=2):
		debug and print("date %s recv %s " % (eml_dt, recv_dt), end='', file=stderr)
		score += 1

		if eml_dt < recv_dt - timedelta(days=15) or \
			eml_dt > recv_dt + timedelta(days=2):
			debug and print("\033[1;31mfar\033[0m ", end='', file=stderr)
			score += 1
		else:
			debug and print("\033[1;33mnear\033[0m ", end='', file=stderr)

	if (eml.get('X-Spam-Status', '').lower() == 'yes' or
		eml.get('X-Spam-Flag', '').lower() == 'yes' or
		len(eml.get('X-Spam-Level', '')) > 3):
		debug and print("X-Spam ", end='', file=stderr)
		score += 1

	debug and print('\033[1;31m%s\033[0m\n' % score, end='', file=stderr)
	print(str(score))


DEBUG=1
def test_spam_test(stdin_eml):
	"""
	>>> spam_test('From:Bb<b@b.tk>\\nTo:a@a.tk\\nSubject:eml ok\\nContent-Type: text/plain;\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200\\n'
	... 'Coucou\\n', DEBUG)
	0
	>>> spam_test('To:\\nSubject: Missing recipient should be scored 2\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	2
	>>> spam_test('Subject: No recp, 1 non-alpha =?utf-8?b?w6k=?= scored 2\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	2
	>>> spam_test('Subject: Enough ASCII should be 2 =?gb2312?B?vNLT0NChxau499bW1sa3/sC0==?=\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	2
	>>> spam_test('To:a@a.tk,b@b.tk,c@c.tk,d@d.tk,e@e.tk,f@f.tk,g@g.tk,'
	...	'h@h.tk,i@i.tk,j@j.tk\\nSubject: More than 9 recipients, scored 2\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	2
	>>> spam_test('To:a@a.tk\\nSubject:Not 1/2 ASCII =?utf-8?b?w6nDqcOpw6nDqcOpw6n=?=\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	2
	>>> spam_test('To:No subject scored 2 <a@a.tk>\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	2
	>>> spam_test('Subject: no To no ASCII:3 =?utf-8?b?w6nDqcOpw6nDqcOpw6nDqcOpw6n=?=\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	3
	>>> spam_test('Subject: =?gb2312?B?vNLT0NChxau499bW1sa3/sC009W78w==?=\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	3
	>>> spam_test('Subject: =?gb2312?B?Encoding error score 2 代 =?=\\n'
	... 'Date:Wed, 26 Apr 2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:21:14 +0200',DEBUG)
	3
	>>> spam_test('Subject: Near past +6 h \\nDate: Wed, 26 Apr 2017 16:20:14 +0200\\n'
	... 'Received:Wed, 26 Apr 2017 22:21:14 +0200', DEBUG)
	3
	>>> spam_test('Subject: Near futur -2 h\\nDate: Wed, 26 Apr 2017 16:20:14 +0200\\n'
	... 'Received:Wed, 26 Apr 2017 14:19:14 +0200', DEBUG)
	3
	>>> spam_test('Subject: Far past +15 d \\nDate: Tue, 11 Apr 2017 16:20:14 +0200\\n'
	... 'Received:Wed, 26 Apr 2016 14:21:14 +0200', DEBUG)
	4
	>>> spam_test('Subject: Far futur -2 d \\nDate: Wed, 26 Apr 2017 16:20:14 +0200\\n'
	... 'Received:Mon, 24 Apr 2016 16:19:14 +0200', DEBUG)
	4
	>>> spam_test('From: =?utf-8?b?5Luj?= <a@a.tk>\\nDate: Wed, 26 Apr '
	... '2017 16:20:14 +0200\\nReceived:Wed, 26 Apr 2017 16:25:14 +0200', DEBUG)
	4
	>>> spam_test('X-Spam-Status: Yes', DEBUG)
	6
	>>> spam_test('X-Spam-Level: ****', DEBUG)
	6
	>>> spam_test(open('test_email/20171010.eml').read(), DEBUG)  # chinese content
	2
	>>> spam_test(open('test_email/20171012.eml').read(), DEBUG)  # no text nor HTML part
	2
	>>> spam_test(open('test_email/20171107.eml').read(), DEBUG)  # longer chinese content
	2
	>>> spam_test(open('test_email/20171130.eml').read(), DEBUG)  # PGP ciphered email
	0
	>>> spam_test(open('test_email/20171219.eml').read(), DEBUG)  # chinese base64 body
	2
	>>> spam_test(open('test_email/20180130.eml').read(), DEBUG)  # no text, bad HTML
	1
	"""
	return spam_test(stdin_eml)


def email_alpha_len(t, f):
	try:
		refined_t = f(t)
	except Exception as e:
		print(str(e) + '\n', file=stderr)
		refined_t = ''
	return alpha_len(refined_t)


def alpha_len(s):
	s_len = len(s)

	if type(s) is not unicode:
		s = unicode(s, errors='ignore')

	ascii_s = s.encode('ascii', errors='ignore')
	s_alpha_len = len([c for c in ascii_s if isalpha(c)])
	return s_len, s_alpha_len


def header_txt(h):
	return unicode(make_header(decode_header(h)))


if version_info.major > 2:  # In Python 3: str is the new unicode
	unicode = str

if __name__ == "__main__":
	if version_info.major > 2:
		from io import TextIOWrapper
		spam_test(TextIOWrapper(stdin.buffer, errors='ignore').read())
	else:
		spam_test(stdin.read())
