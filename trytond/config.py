#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import ConfigParser, os, sys


class ConfigManager(object):
    def __init__(self, fname=None):
        self.options = {
            'hostname': None,
            'interface': '',
            'netrpc': True,
            'netport': 8070,
            'xmlrpc': False,
            'xmlport': 8069,
            'jsonrpc': False,
            'jsonport': 8000,
            'jsondata_path': '/var/www/localhost/tryton',
            'webdav': False,
            'webdavport': 8080,
            'db_type': 'postgresql',
            'db_host': False,
            'db_port': False,
            'db_name': False,
            'db_user': False,
            'db_password': False,
            'db_minconn': 1,
            'db_maxconn': 64,
            'pg_path': None,
            'admin_passwd': 'admin',
            'verbose': False,
            'debug_mode': False,
            'pidfile': None,
            'logfile': None,
            'secure_netrpc': False,
            'secure_xmlrpc': False,
            'secure_jsonrpc': False,
            'secure_webdav': False,
            'privatekey': '/etc/ssl/trytond/server.key',
            'certificate': '/etc/ssl/trytond/server.pem',
            'smtp_server': 'localhost',
            'smtp_port': 25,
            'smtp_ssl': False,
            'smtp_tls': False,
            'smtp_user': False,
            'smtp_password': False,
            'data_path': '/var/lib/trytond',
            'max_thread': 40,
            'multi_server': False,
            'session_timeout': 600,
            'psyco': False,
            'auto_reload': True,
            'prevent_dblist': False,
            'init': {},
            'update': {},
            'cron': True,
        }
        self.configfile = None

    def update_cmdline(self, cmdline_options):
        self.options.update(cmdline_options)

        # Verify that we want to log or not, if not the output will go to stdout
        if self.options['logfile'] in ('None', 'False'):
            self.options['logfile'] = False
        # the same for the pidfile
        if self.options['pidfile'] in ('None', 'False'):
            self.options['pidfile'] = False
        if self.options['data_path'] in ('None', 'False'):
            self.options['data_path'] = False

    def update_etc(self, configfile=None):
        if configfile is None:
            prefixdir = os.path.abspath(os.path.normpath(os.path.join(
                os.path.dirname(sys.prefix), '..')))
            configfile = os.path.join(prefixdir, 'etc', 'trytond.conf')
            if not os.path.isfile(configfile):
                configdir = os.path.abspath(os.path.normpath(os.path.join(
                    os.path.dirname(__file__), '..')))
                configfile = os.path.join(configdir, 'etc', 'trytond.conf')
            if not os.path.isfile(configfile):
                configfile = None

        self.configfile = configfile
        if not self.configfile:
            return

        parser = ConfigParser.ConfigParser()
        with open(self.configfile) as fp:
            parser.readfp(fp)
        for (name, value) in parser.items('options'):
            if value == 'True' or value == 'true':
                value = True
            if value == 'False' or value == 'false':
                value = False
            if name in ('netport', 'xmlport', 'webdavport', 'jsonport'):
                value = int(value)
            self.options[name] = value

    def get(self, key, default=None):
        return self.options.get(key, default)

    def __setitem__(self, key, value):
        self.options[key] = value

    def __getitem__(self, key):
        return self.options[key]

CONFIG = ConfigManager()
