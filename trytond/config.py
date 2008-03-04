import ConfigParser, optparse, os, sys
import logging
from version import VERSION
from netsvc import LOG_CRITICAL, LOG_ERROR, LOG_WARNING
from netsvc import LOG_INFO, LOG_DEBUG


class ConfigManager(object):
    def __init__(self, fname=None):
        self.options = {
            'interface': '',
            'netrpc': True,
            'netport': '8070',
            'xmlrpc': False,
            'xmlport': '8069',
            'webdav': False,
            'webdavport': '8080',
            'soap': False,
            'db_host': False,
            'db_port': False,
            'db_name': False,
            'db_user': False,
            'db_password': False,
            'db_maxconn': 64,
            'pg_path': None,
            'admin_passwd': 'admin',
            'verbose': False,
            'debug_mode': False,
            'pidfile': None,
            'logfile': None,
            'secure': False,
            'privatekey': '/etc/ssl/trytond/server.key',
            'certificate': '/etc/ssl/trytond/server.pem',
            'smtp_server': 'localhost',
            'smtp_user': False,
            'smtp_password': False,
            'stop_after_init': False,
            'data_path': '/var/lib/trytond',
        }

        parser = optparse.OptionParser(version=VERSION)

        parser.add_option("-c", "--config", dest="config",
                help="specify alternate config file")
        parser.add_option("-s", "--save", action="store_true", dest="save",
                default=False, help="save configuration to ~/.trytondrc")
        parser.add_option("--pidfile", dest="pidfile",
                help="file where the server pid will be stored")
        parser.add_option("--logfile", dest="logfile",
                help="file where the server log will be stored")
        parser.add_option("--data-path", dest="data_path",
                help="path where the server will store attachment")
        parser.add_option('--debug', dest='debug_mode', action='store_true',
                help='enable debug mode')
        parser.add_option("-v", "--verbose", action="store_true",
                dest="verbose", help="enable debugging")

        group = optparse.OptionGroup(parser, "Services related options")
        group.add_option("--stop-after-init", action="store_true",
                dest="stop_after_init",
                help="stop the server after it initializes")
        group.add_option("-n", "--interface", dest="interface",
                help="specify the TCP IP address")
        group.add_option("--no-netrpc", dest="netrpc", action="store_false",
                help="disable netrpc")
        group.add_option("-p", "--net-port", dest="netport",
                help="specify the TCP port for netrpc")
        group.add_option("--xmlrpc", dest="xmlrpc", action="store_true",
                help="enable xmlrpc")
        group.add_option("--xml-port", dest="xmlport",
                help="specify the TCP port for xmlrpc")
        group.add_option("--webdav", dest="webdav", action="store_true",
                help="enable webdav")
        group.add_option("--webdav-port", dest="webdavport",
                help="specify the TCP port for webdav")
        parser.add_option_group(group)

        group = optparse.OptionGroup(parser, "SSL options")
        group.add_option("-S", "--secure", dest="secure", action="store_true",
                help="launch server over SSL")
        group.add_option("--privatekey", dest="privatekey",
                help="specify the file for the private key")
        group.add_option("--certificate", dest="certificate",
                help="specify the file for the certificate")
        parser.add_option_group(group)

        group = optparse.OptionGroup(parser, "Modules related options")
        group.add_option("-i", "--init", dest="init",
                help="init a module (use \"all\" for all modules)")
        group.add_option("-u", "--update", dest="update",
                help="update a module (use \"all\" for all modules)")
        parser.add_option_group(group)

        group = optparse.OptionGroup(parser, "Database related options")
        group.add_option("-d", "--database", dest="db_name",
                help="specify the database name")
        group.add_option("-r", "--db_user", dest="db_user",
                help="specify the database user name")
        group.add_option("-w", "--db_password", dest="db_password",
                help="specify the database password")
        group.add_option("--pg_path", dest="pg_path",
                help="specify the pg executable path")
        group.add_option("--db_host", dest="db_host",
                help="specify the database host")
        group.add_option("--db_port", dest="db_port",
                help="specify the database port")
        group.add_option("--db_maxconn", dest="db_maxconn",
                help="specify the the maximum number of physical " \
                        "connections to posgresql")
        parser.add_option_group(group)

        group = optparse.OptionGroup(parser, "SMTP related options")
        group.add_option('--smtp', dest='smtp_server',
                help='specify the SMTP server for sending email')
        group.add_option('--smtp-user', dest='smtp_user',
                help='specify the SMTP username for sending email')
        group.add_option('--smtp-password', dest='smtp_password',
                help='specify the SMTP password for sending email')
        parser.add_option_group(group)

        (opt, args) = parser.parse_args()

        # place/search the config file on Win32 near the server installation
        # (../etc from the server)
        # if the server is run by an unprivileged user,
        # he has to specify location of a config file 
        # where he has the rights to write,
        # else he won't be able to save the configurations,
        # or even to start the server...
        if os.name == 'nt':
            rcfilepath = os.path.join(os.path.abspath(
                os.path.dirname(sys.argv[0])), 'tryton-server.conf')
        else:
            rcfilepath = os.path.expanduser('~/.trytondrc')

        self.rcfile = fname or opt.config \
                or os.environ.get('TRYTOND') or rcfilepath
        self.load()

        # Verify that we want to log or not, if not the output will go to stdout
        if self.options['logfile'] in ('None', 'False'):
            self.options['logfile'] = False
        # the same for the pidfile
        if self.options['pidfile'] in ('None', 'False'):
            self.options['pidfile'] = False
        if self.options['data_path'] in ('None', 'False'):
            self.options['data_path'] = False

        for arg in (
                'interface',
                'xmlport',
                'webdavport',
                'db_name',
                'db_user',
                'db_password',
                'db_host',
                'db_port',
                'logfile',
                'pidfile',
                'secure',
                'privatekey',
                'certificate',
                'smtp_server',
                'smtp_user',
                'smtp_password',
                'netport',
                'db_maxconn',
                'data_path',
                'verbose',
                'debug_mode',
                'stop_after_init',
                'netrpc',
                'xmlrpc',
                'webdav',
                ):
            if getattr(opt, arg) != None:
                self.options[arg] = getattr(opt, arg)

        init = {}
        if opt.init:
            for i in opt.init.split(','):
                init[i] = 1
        self.options['init'] = init

        update = {}
        if opt.update:
            for i in opt.update.split(','):
                update[i] = 1
        self.options['update'] = update

        if opt.pg_path:
            self.options['pg_path'] = opt.pg_path

        if opt.save:
            self.save()

    def load(self):
        parser = ConfigParser.ConfigParser()
        try:
            parser.read([self.rcfile])
            for (name, value) in parser.items('options'):
                if value == 'True' or value == 'true':
                    value = True
                if value == 'False' or value == 'false':
                    value = False
                self.options[name] = value
        except IOError:
            pass
        except ConfigParser.NoSectionError:
            pass

    def save(self):
        parser = ConfigParser.ConfigParser()
        parser.add_section('options')
        for opt in [opt for opt in self.options.keys() \
                if opt not in (
                    'version',
                    'init',
                    'update',
                    )]:
            parser.set('options', opt, self.options[opt])

        # try to create the directories and write the file
        try:
            if not os.path.exists(os.path.dirname(self.rcfile)):
                os.makedirs(os.path.dirname(self.rcfile))
            try:
                parser.write(file(self.rcfile, 'w'))
            except IOError:
                sys.stderr.write("ERROR: couldn't write the config file\n")

        except OSError:
            # what to do if impossible?
            sys.stderr.write("ERROR: couldn't create the config directory\n")

    def get(self, key, default=None):
        return self.options.get(key, default)

    def __setitem__(self, key, value):
        self.options[key] = value

    def __getitem__(self, key):
        return self.options[key]

CONFIG = ConfigManager()
