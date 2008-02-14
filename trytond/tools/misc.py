# -*- coding: utf8 -*-
"""
Miscelleanous tools used by tryton
"""
import os, time, sys
import inspect
from trytond.config import CONFIG
import socket
import zipfile

if sys.version_info[:2] < (2, 4):
    from threadinglocal import local
else:
    from threading import local

def find_in_path(name):
    if os.name == "nt":
        sep = ';'
    else:
        sep = ':'
    path = [directory for directory in os.environ['PATH'].split(sep)
            if os.path.isdir(directory)]
    for directory in path:
        val = os.path.join(directory, name)
        if os.path.isfile(val) or os.path.islink(val):
            return val
    return None

def find_pg_tool(name):
    if CONFIG['pg_path'] and CONFIG['pg_path'] != 'None':
        return os.path.join(CONFIG['pg_path'], name)
    else:
        return find_in_path(name)

def exec_pg_command(name, *args):
    prog = find_pg_tool(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    args2 = (os.path.basename(prog),) + args
    return os.spawnv(os.P_WAIT, prog, args2)

def exec_pg_command_pipe(name, *args):
    prog = find_pg_tool(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    if os.name == "nt":
        cmd = '"' + prog + '" ' + ' '.join(args)
    else:
        cmd = prog + ' ' + ' '.join(args)
    return os.popen2(cmd, 'b')

def exec_command_pipe(name, *args):
    prog = find_in_path(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    if os.name == "nt":
        cmd = '"'+prog+'" '+' '.join(args)
    else:
        cmd = prog+' '+' '.join(args)
    return os.popen2(cmd, 'b')

def file_open(name, mode="r", subdir='modules'):
    """Open a file from the root dir, using a subdir folder."""
    root_path = os.path.dirname(os.path.dirname(__file__))
    if subdir:
        if subdir == 'modules'\
                and (name.startswith('ir' + os.sep) \
                    or name.startswith('workflow' + os.sep) \
                    or name.startswith('res' + os.sep) \
                    or name.startswith('webdav' + os.sep)):
            name = os.path.join(root_path, name)
        else:
            name = os.path.join(root_path, subdir, name)
    else:
        name = os.path.join(root_path, name)

    # Check for a zipfile in the path
    head = name
    zipname = False
    name2 = False
    while True:
        head, tail = os.path.split(head)
        if not tail:
            break
        if zipname:
            zipname = os.path.join(tail, zipname)
        else:
            zipname = tail
        if zipfile.is_zipfile(head+'.zip'):
            import StringIO
            zfile = zipfile.ZipFile(head+'.zip')
            try:
                return StringIO.StringIO(zfile.read(os.path.join(
                    os.path.basename(head), zipname).replace(
                        os.sep, '/')))
            except:
                name2 = os.path.normpath(os.path.join(head + '.zip', zipname))
    for i in (name2, name):
        if i and os.path.isfile(i):
            return file(i, mode)

    raise IOError, 'File not found : '+str(name)

def email_send(email_from, email_to, subject, body, email_cc=None,
        email_bcc=None, reply_to=False, tinycrm=False):
    """Send an email."""
    if not email_cc:
        email_cc = []
    if not email_bcc:
        email_bcc = []
    import smtplib
    from email.MIMEText import MIMEText
    from email.Header import Header
    from email.Utils import formatdate, COMMASPACE

    msg = MIMEText(body or '', _charset='utf-8')
    msg['Subject'] = Header(subject.decode('utf8'), 'utf-8')
    msg['From'] = email_from
    del msg['Reply-To']
    if reply_to:
        msg['Reply-To'] = msg['From']+', '+reply_to
    msg['To'] = COMMASPACE.join(email_to)
    if email_cc:
        msg['Cc'] = COMMASPACE.join(email_cc)
    if email_bcc:
        msg['Bcc'] = COMMASPACE.join(email_bcc)
    msg['Date'] = formatdate(localtime=True)
    if tinycrm:
        msg['Message-Id'] = '<' + str(time.time()) + '-tinycrm-' + \
                str(tinycrm) + '@' + socket.gethostname() + '>'
    try:
        smtp = smtplib.SMTP()
        smtp.connect(CONFIG['smtp_server'])
        if CONFIG['smtp_user'] or CONFIG['smtp_password']:
            smtp.login(CONFIG['smtp_user'], CONFIG['smtp_password'])
        smtp.sendmail(email_from, email_to + email_cc + email_bcc,
                msg.as_string())
        smtp.quit()
    except Exception, exp:
        import logging
        logging.getLogger().info(str(exp))
    return True

def email_send_attach(email_from, email_to, subject, body, email_cc=None,
        email_bcc=None, reply_to=False, attach=None,
        tinycrm=False):
    """Send an email."""
    if not email_cc:
        email_cc = []
    if not email_bcc:
        email_bcc = []
    if not attach:
        attach = []
    import smtplib
    from email.MIMEText import MIMEText
    from email.MIMEBase import MIMEBase
    from email.MIMEMultipart import MIMEMultipart
    from email.Header import Header
    from email.Utils import formatdate, COMMASPACE
    from email import Encoders

    msg = MIMEMultipart()

    msg['Subject'] = Header(subject.decode('utf8'), 'utf-8')
    msg['From'] = email_from
    del msg['Reply-To']
    if reply_to:
        msg['Reply-To'] = reply_to
    msg['To'] = COMMASPACE.join(email_to)
    if email_cc:
        msg['Cc'] = COMMASPACE.join(email_cc)
    if email_bcc:
        msg['Bcc'] = COMMASPACE.join(email_bcc)
    if tinycrm:
        msg['Message-Id'] = '<' + str(time.time()) + '-tinycrm-' + \
                str(tinycrm) + '@' + socket.gethostname()+'>'
    msg['Date'] = formatdate(localtime=True)
    msg.attach( MIMEText(body or '', _charset='utf-8') )
    for (fname, fcontent) in attach:
        part = MIMEBase('application', "octet-stream")
        part.set_payload( fcontent )
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                'attachment; filename="%s"' % (fname,))
        msg.attach(part)
    try:
        smtp = smtplib.SMTP()
        smtp.connect(CONFIG['smtp_server'])
        if CONFIG['smtp_user'] or CONFIG['smtp_password']:
            smtp.login(CONFIG['smtp_user'], CONFIG['smtp_password'])
        smtp.sendmail(email_from, email_to + email_cc + email_bcc,
                msg.as_string())
        smtp.quit()
    except Exception, exp:
        import logging
        logging.getLogger().info(str(exp))
    return True

def sms_send(user, password, api_id, text, to):
    "text must be latin-1 encoded"
    import urllib
    params = urllib.urlencode({
        'user': user,
        'password': password,
        'api_id': api_id,
        'text': text,
        'to':to,
        })
    #urllib.urlopen("http://api.clickatell.com/http/sendmsg", params)
    urllib.urlopen("http://196.7.150.220/http/sendmsg", params)
    return True


class UpdateableStr(local):
    '''Stores an updateable str to use in wizards'''

    def __init__(self, string=''):
        super(UpdateableStr, self).__init__()
        self.string = string

    def __str__(self):
        return str(self.string)

    def __repr__(self):
        return str(self.string)

    def __nonzero__(self):
        return bool(self.string)


class UpdateableDict(local):
    '''Stores an updateable dict to use in wizards'''

    def __init__(self, value=None):
        super(UpdateableDict, self).__init__()
        if value is None:
            value = {}
        self.dict = value

    def __str__(self):
        return str(self.dict)

    def __repr__(self):
        return str(self.dict)

    def clear(self):
        return self.dict.clear()

    def keys(self):
        return self.dict.keys()

    def __setitem__(self, i, j):
        self.dict.__setitem__(i, j)

    def __getitem__(self, i):
        return self.dict.__getitem__(i)

    def copy(self):
        return self.dict.copy()

    def iteritems(self):
        return self.dict.iteritems()

    def iterkeys(self):
        return self.dict.iterkeys()

    def itervalues(self):
        return self.dict.itervalues()

    def pop(self, k, d=None):
        return self.dict.pop(k, d)

    def popitem(self):
        return self.dict.popitem()

    def setdefault(self, k, d=None):
        return self.dict.setdefault(k, d)

    def update(self, E, **F):
        return self.dict.update(E, F)

    def values(self):
        return self.dict.values()

    def get(self, k, d=None):
        return self.dict.get(k, d)

    def has_key(self, k):
        return self.dict.has_key(k)

    def items(self):
        return self.dict.items()

    def __cmp__(self, y):
        return self.dict.__cmp__(y)

    def __contains__(self, k):
        return self.dict.__contains__(k)

    def __delitem__(self, y):
        return self.dict.__delitem__(y)

    def __eq__(self, y):
        return self.dict.__eq__(y)

    def __ge__(self, y):
        return self.dict.__ge__(y)

    def __gt__(self, y):
        return self.dict.__gt__(y)

    def __hash__(self):
        return self.dict.__hash__()

    def __iter__(self):
        return self.dict.__iter__()

    def __le__(self, y):
        return self.dict.__le__(y)

    def __len__(self):
        return self.dict.__len__()

    def __lt__(self, y):
        return self.dict.__lt__(y)

    def __ne__(self, y):
        return self.dict.__ne__(y)


class Cache(object):
    """
    Use it as a decorator of the function you plan to cache
    Timeout: 0 = no timeout, otherwise in seconds
    """

    def __init__(self, timeout=10000):
        self.timeout = timeout
        self.cache = {}

    def __call__(self, function):
        arg_names = inspect.getargspec(function)[0][2:]

        def cached_result(self2, cursor=None, *args, **kwargs):
            if cursor is None:
                self.cache = {}
                return True

            # Update named arguments with positional argument values
            kwargs.update(dict(zip(arg_names, args)))
            kwargs = kwargs.items()
            kwargs.sort()

            # Work out key as a tuple of ('argname', value) pairs
            key = (('dbname', cursor.dbname), ('object', str(self2)),
                str(kwargs))

            # Check cache and return cached value if possible
            if key in self.cache:
                (value, last_time) = self.cache[key]
                mintime = time.time() - self.timeout
                if self.timeout <= 0 or mintime <= last_time:
                    return value

            # Work out new value, cache it and return it
            # Should copy() this value to avoid futur modf of the cacle ?
            result = function(self2, cursor, **dict(kwargs))

            self.cache[key] = (result, time.time())
            return result

        return cached_result

def get_languages():
    languages = {
        'zh_CN': 'Chinese (CN)',
        'zh_TW': 'Chinese (TW)',
        'cs_CZ': 'Czech',
        'de_DE': 'Deutsch',
        'es_AR': 'Español (Argentina)',
        'es_ES': 'Español (España)',
        'fr_FR': 'Français',
        'fr_CH': 'Français (Suisse)',
        'en_EN': 'English (default)',
        'hu_HU': 'Hungarian',
        'it_IT': 'Italiano',
        'pt_BR': 'Portugese (Brasil)',
        'pt_PT': 'Portugese (Portugal)',
        'nl_NL': 'Nederlands',
        'ro_RO': 'Romanian',
        'ru_RU': 'Russian',
        'sv_SE': 'Swedish',
    }
    return languages

def mod10r(number):
    """
    Input number : account or invoice number
    Output return: the same number completed with the recursive mod10
    key
    """
    codec = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
    report = 0
    result = ""
    for digit in number:
        result += digit
        if digit.isdigit():
            report = codec[ (int(digit) + report) % 10 ]
    return result + str((10 - report) % 10)
