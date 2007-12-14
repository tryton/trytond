# Copyright (c) 2004-2006 TINY SPRL. (http://tiny.be)
# Copyright (c) 2007 Cedric Krier.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contact a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

"""
%prog [options]
"""

import sys, os, signal
import netsvc
import time
import psycopg
import pooler
import sql_db
import config
from config import CONFIG
import web_service
import wkf_service
import report_service
from module import register_classes
import osv, security, tools, version


class TrytonServer(object):

    def __init__(self):
        netsvc.init_logger()
        self.logger = netsvc.Logger()

        if sys.platform == 'win32':
            import mx.DateTime
            mx.DateTime.strptime = lambda x, y: mx.DateTime.mktime(
                    time.strptime(x, y))

        self.logger.notify_channel("objects", netsvc.LOG_INFO,
                'initialising distributed objects services')

        self.dispatcher = netsvc.Dispatcher()
        self.dispatcher.monitor(signal.SIGINT)


        web_service.DB()
        web_service.Common()
        web_service.Object()
        web_service.Wizard()
        web_service.Report()

        wkf_service.WorkflowService()

        # TODO add report service

    def run(self):
        "Run the server and never return"

        db_name = CONFIG["db_name"]

        cursor = None
        try:
            if db_name:
                cursor = pooler.get_db_only(db_name).cursor()
        except psycopg.OperationalError:
            self.logger.notify_channel("init", netsvc.LOG_INFO,
                    "could not connect to database '%s'!" % db_name,)

        if cursor and CONFIG['init'] and CONFIG['init']['all']:
            cursor.execute("SELECT relname " \
                    "FROM pg_class " \
                    "WHERE relkind = 'r' AND relname in (" \
                    "'inherit', "
                    "'ir_values', "
                    "'ir_model', "
                    "'ir_model_fields', "
                    "'ir_actions', "
                    "'ir_act_window', "
                    "'ir_act_report', "
                    "'ir_act_wizard', "
                    "'ir_act_url', "
                    "'ir_ui_view', "
                    "'ir_ui_menu', "
                    "'res_users', "
                    "'res_groups', "
                    "'res_roles', "
                    "'res_roles_users_rel', "
                    "'res_groups_users_rel', "
                    "'wkf', "
                    "'wkf_activity', "
                    "'wkf_transition', "
                    "'wkf_instance', "
                    "'wkf_workitem', "
                    "'wkf_witm_trans', "
                    "'wkf_logs', "
                    "'ir_module_category', "
                    "'ir_module_module', "
                    "'ir_module_module_dependency'"
                    ")")
            if len(cursor.fetchall()) == 0:
                self.logger.notify_channel("init", netsvc.LOG_INFO, "init db")
                sql_db.init_db(cursor)
                if not CONFIG['without_demo']:
                    CONFIG["demo"]['all'] = 1
            cursor.commit()
            cursor.close()

        register_classes()

        if db_name:
            pooler.get_db_and_pool(db_name,
                    update_module=bool(CONFIG['init'] or CONFIG['update']))

        if CONFIG["stop_after_init"]:
            sys.exit(0)

        # Launch Server
        secure = CONFIG["secure"]
        if CONFIG['xmlrpc']:
            interface = CONFIG["interface"]
            try:
                port = int(CONFIG["port"])
            except:
                self.logger.notify_channel("init", netsvc.LOG_ERROR,
                        "invalid port '%s'!" % (CONFIG["port"],))
                sys.exit(1)

            httpd = netsvc.HttpDaemon(interface, port, secure)

            xml_gw = netsvc.XmlRpc.RpcGateway('web-services')
            httpd.attach("/xmlrpc", xml_gw )
            self.logger.notify_channel("web-services", netsvc.LOG_INFO,
                        "starting XML-RPC" + \
                                (CONFIG['secure'] and ' Secure' or '') + \
                                " services, port " + str(port))

        if CONFIG['netrpc']:
            netinterface = CONFIG["netinterface"]
            try:
                netport = int(CONFIG["netport"])
            except Exception:
                self.logger.notify_channel("init", netsvc.LOG_ERROR,
                        "invalid port '%s'!" % (CONFIG["netport"],))
                sys.exit(1)

            tinysocket = netsvc.TinySocketServerThread(netinterface, netport,
                    False)
            self.logger.notify_channel("web-services", netsvc.LOG_INFO,
                    "starting netrpc service, port " + str(netport))

        def handler(signum, frame):
            if CONFIG['netrpc']:
                tinysocket.stop()
            if CONFIG['xmlrpc']:
                httpd.stop()
            netsvc.Agent.quit()
            if CONFIG['pidfile']:
                os.unlink(CONFIG['pidfile'])
            sys.exit(0)

        if CONFIG['pidfile']:
            fd_pid = open(CONFIG['pidfile'], 'w')
            pidtext = "%d" % (os.getpid())
            fd_pid.write(pidtext)
            fd_pid.close()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

        self.logger.notify_channel("web-services", netsvc.LOG_INFO,
                'the server is running, waiting for connections...')
        if CONFIG['netrpc']:
            tinysocket.start()
        if CONFIG['xmlrpc']:
            httpd.start()
        #DISPATCHER.run()
        while True:
            time.sleep(1)

if __name__ == "__main__":
    SERVER = TrytonServer()
    SERVER.run()
