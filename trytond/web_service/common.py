from trytond.netsvc import Service, Logger, LOG_INFO
from trytond import security
from trytond.version import VERSION
import time


class Common(Service):

    def __init__(self, name="common"):
        Service.__init__(self, name)
        Service.join_group(self, "web-services")
        Service.export_method(self, self.about)
        Service.export_method(self, self.login)
        Service.export_method(self, self.timezone_get)

    def login(self, database, login, password):
        res = security.login(database, login, password)
        logger = Logger()
        msg = res and 'successful login' or 'bad login or password'
        logger.notify_channel("web-service", LOG_INFO,
                "%s from '%s' using database '%s'" % (msg, login, database))
        return res or False

    def about(self):
        return '''
Tryton %s

The whole source code is distributed under the terms of the
GNU Public Licence v2.
''' % (VERSION,)

    def timezone_get(self):
        return time.tzname[0]
