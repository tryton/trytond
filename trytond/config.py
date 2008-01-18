import ConfigParser, optparse, os, sys
import logging
from version import VERSION
from netsvc import LOG_CRITICAL, LOG_ERROR, LOG_WARNING
from netsvc import LOG_INFO, LOG_DEBUG


class ConfigManager(object):
    def __init__(self, fname=None):
        self.options = {
            'verbose': False,
            'interface': '',
            'port': '8069',
            'netinterface': '',
            'netport': '8070',
            'db_host': False,
            'db_port': False,
            'db_name': False,
            'db_user': False,
            'db_password': False,
            'db_maxconn': 64,
            'reportgz': False,
            'netrpc': True,
            'xmlrpc': True,
            'soap': False,
            'pg_path': None,
            'admin_passwd': 'admin',
            'debug_mode': False,
            'pidfile': None,
            'logfile': None,
            'secure': False,
            'smtp_server': 'localhost',
            'smtp_user': False,
            'smtp_password': False,
            'stop_after_init': False,
            'price_accuracy': 2,
            'assert_exit_level': logging.WARNING,
        }

        assert_exit_levels = (
                LOG_CRITICAL,
                LOG_ERROR,
                LOG_WARNING,
                LOG_INFO,
                LOG_DEBUG,
                )

        parser = optparse.OptionParser(version=VERSION)

        parser.add_option("-c", "--config", dest="config",
                help="specify alternate config file")
        parser.add_option("-s", "--save", action="store_true", dest="save",
                default=False, help="save configuration to ~/.trytondrc")
        parser.add_option("-v", "--verbose", action="store_true",
                dest="verbose", default=False, help="enable debugging")
        parser.add_option("--pidfile", dest="pidfile",
                help="file where the server pid will be stored")
        parser.add_option("--logfile", dest="logfile",
                help="file where the server log will be stored")
        parser.add_option("-n", "--interface", dest="interface",
                help="specify the TCP IP address")
        parser.add_option("-p", "--port", dest="port",
                help="specify the TCP port")
        parser.add_option("--net_interface", dest="netinterface",
                help="specify the TCP IP address for netrpc")
        parser.add_option("--net_port", dest="netport",
                help="specify the TCP port for netrpc")
        parser.add_option("--no-netrpc", dest="netrpc", action="store_false",
                default=True, help="disable netrpc")
        parser.add_option("--no-xmlrpc", dest="xmlrpc", action="store_false",
                default=True, help="disable xmlrpc")
        parser.add_option("-i", "--init", dest="init",
                help="init a module (use \"all\" for all modules)")
        parser.add_option("--without-demo", dest="without_demo",
                help="load demo data for a module " \
                        "(use \"all\" for all modules)", default=False)
        parser.add_option("-u", "--update", dest="update",
                help="update a module (use \"all\" for all modules)")
        parser.add_option("--stop-after-init", action="store_true",
                dest="stop_after_init", default=False,
                help="stop the server after it initializes")
        parser.add_option('--debug', dest='debug_mode', action='store_true',
                default=False, help='enable debug mode')
        parser.add_option("--assert-exit-level", dest='assert_exit_level',
                help="specify the level at which a failed assertion will " \
                        "stop the server " + str(assert_exit_levels))
        parser.add_option("-S", "--secure", dest="secure", action="store_true",
                help="launch server over https instead of http", default=False)
        parser.add_option('--smtp', dest='smtp_server', default='',
                help='specify the SMTP server for sending email')
        parser.add_option('--smtp-user', dest='smtp_user', default='',
                help='specify the SMTP username for sending email')
        parser.add_option('--smtp-password', dest='smtp_password', default='',
                help='specify the SMTP password for sending email')
        parser.add_option('--price_accuracy', dest='price_accuracy',
                default='2', help='specify the price accuracy')

        group = optparse.OptionGroup(parser, "Modules related options")
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
        group.add_option("--db_maxconn", dest="db_maxconn", default='64',
                help="specify the the maximum number of physical " \
                        "connections to posgresql")
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

        for arg in (
                'interface',
                'port',
                'db_name',
                'db_user',
                'db_password',
                'db_host',
                'db_port',
                'logfile',
                'pidfile',
                'secure',
                'smtp_server',
                'smtp_user',
                'smtp_password',
                'price_accuracy',
                'netinterface',
                'netport',
                'db_maxconn',
                ):
            if getattr(opt, arg):
                self.options[arg] = getattr(opt, arg)

        for arg in (
                'verbose',
                'debug_mode',
                'stop_after_init',
                'without_demo',
                'netrpc',
                'xmlrpc',
                ):
            self.options[arg] = getattr(opt, arg)

        if opt.assert_exit_level:
            assert opt.assert_exit_level in assert_exit_levels, \
                    'ERROR: The assert-exit-level must be one ' \
                    'of those values: '+str(assert_exit_levels)
            self.options['assert_exit_level'] = getattr(logging,
                    opt.assert_exit_level.upper())

        init = {}
        if opt.init:
            for i in opt.init.split(','):
                init[i] = 1
        self.options['init'] = init
        self.options["demo"] = not opt.without_demo \
                and self.options['init'] or {}

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
