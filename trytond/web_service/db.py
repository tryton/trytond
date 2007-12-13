from trytond.netsvc import Service, Logger, LOG_ERROR, LOG_INFO, LOG_WARNING
import threading
from trytond import security
from trytond import sql_db
from trytond import pooler
from trytond import tools
import base64
import os


class DB(Service):

    def __init__(self, name="db"):
        super(DB, self).__init__(name)
        self.join_group("web-services")
        self.export_method(self.create)
        self.export_method(self.get_progress)
        self.export_method(self.drop)
        self.export_method(self.dump)
        self.export_method(self.restore)
        self.export_method(self.list)
        self.export_method(self.list_lang)
        self.export_method(self.change_admin_password)
        self.actions = {}
        self._id = 0
        self.id_protect = threading.Semaphore()

    def create(self, password, db_name, demo, lang):
        security.check_super(password)
        self.id_protect.acquire()
        self._id += 1
        db_id = self._id
        self.id_protect.release()

        self.actions[db_id] = {'clean': False}

        database = sql_db.db_connect('template1', serialize=1)
        database.truedb.autocommit()
        cursor = database.cursor()
        cursor.execute('CREATE DATABASE ' + db_name + ' ENCODING \'unicode\'')
        cursor.close()


        class DBInitialize(object):
            def __call__(self, service, db_id, db_name, demo, lang):
                try:
                    service.actions[db_id]['progress'] = 0
                    cursor = sql_db.db_connect(db_name).cursor()
                    sql_db.init_db(cursor)
                    cursor.commit()
                    cursor.close()
                    cursor = None
                    pooler.get_pool(db_name, demo, service.actions[db_id],
                            update_module=True)
                    if lang and lang != 'en_US':
                        filename = tools.CONFIG["root_path"] + "/i18n/" + \
                                lang + ".csv"
                        tools.trans_load(db_name, filename, lang)
                    service.actions[db_id]['clean'] = True
                    cursor = sql_db.db_connect(db_name).cursor()
                    cursor.execute('select login, password, name ' \
                            'from res_users ' \
                            'where login <> \'root\' order by login')
                    service.actions[db_id]['users'] = cursor.dictfetchall()
                    cursor.close()
                except Exception, exp:
                    service.actions[db_id]['clean'] = False
                    service.actions[db_id]['exception'] = exp
                    from StringIO import StringIO
                    import traceback
                    e_str = StringIO()
                    traceback.print_exc(file=e_str)
                    traceback_str = e_str.getvalue()
                    e_str.close()
                    service.actions[db_id]['traceback'] = traceback_str
                    if cursor:
                        cursor.close()

        logger = Logger()
        logger.notify_channel("web-services", LOG_INFO,
                'CREATE DB: %s' % (db_name))
        dbi = DBInitialize()
        create_thread = threading.Thread(target=dbi,
                args=(self, db_id, db_name, demo, lang))
        create_thread.start()
        self.actions[db_id]['thread'] = create_thread
        return db_id

    def get_progress(self, password, db_id):
        security.check_super(password)
        if self.actions[db_id]['thread'].isAlive():
#            return addons.init_progress[db_name]
            return (min(self.actions[db_id].get('progress', 0), 0.95), [])
        else:
            clean = self.actions[db_id]['clean']
            if clean:
                users = self.actions[db_id]['users']
                del self.actions[db_id]
                return (1.0, users)
            else:
                exp = self.actions[db_id]['exception']
                del self.actions[db_id]
                raise Exception, exp

    def drop(self, password, db_name):
        security.check_super(password)
        pooler.close_db(db_name)
        logger = Logger()

        database = sql_db.db_connect('template1', serialize=1)
        database.truedb.autocommit()
        cursor = database.cursor()
        try:
            try:
                cursor.execute('DROP DATABASE ' + db_name)
            except:
                logger.notify_channel("web-service", LOG_ERROR,
                    'DROP DB: %s failed' % (db_name,))
                raise
            else:
                logger.notify_channel("web-services", LOG_INFO,
                    'DROP DB: %s' % (db_name))
        finally:
            cursor.close()
        return True

    def dump(self, password, db_name):
        security.check_super(password)
        logger = Logger()

        if tools.CONFIG['db_password']:
            logger.notify_channel("web-service", LOG_ERROR,
                    'DUMP DB: %s doesn\'t work with password' % (db_name,))
            raise Exception, "Couldn't dump database with password"

        cmd = ['pg_dump', '--format=c']
        if tools.CONFIG['db_user']:
            cmd.append('--username=' + tools.CONFIG['db_user'])
        if tools.CONFIG['db_host']:
            cmd.append('--host=' + tools.CONFIG['db_host'])
        if tools.CONFIG['db_port']:
            cmd.append('--port=' + tools.CONFIG['db_port'])
        cmd.append(db_name)

        stdin, stdout = tools.exec_pg_command_pipe(*tuple(cmd))
        stdin.close()
        data = stdout.read()
        res = stdout.close()
        if res:
            logger.notify_channel("web-service", LOG_ERROR,
                    'DUMP DB: %s failed\n%s' % (db_name, data))
            raise Exception, "Couldn't dump database"
        logger.notify_channel("web-services", LOG_INFO,
                'DUMP DB: %s' % (db_name))
        return base64.encodestring(data)

    def restore(self, password, db_name, data):
        security.check_super(password)
        logger = Logger()

        if self.db_exist(db_name):
            logger.notify_channel("web-service", LOG_WARNING,
                    'RESTORE DB: %s already exists' % (db_name,))
            raise Exception, "Database already exists"

        if tools.CONFIG['db_password']:
            logger.notify_channel("web-service", LOG_ERROR,
                    'RESTORE DB: %s doesn\'t work with password' % (db_name,))
            raise Exception, "Couldn't restore database with password"

        database = sql_db.db_connect('template1', serialize=1)
        database.truedb.autocommit()
        cursor = database.cursor()
        cursor.execute('CREATE DATABASE ' + db_name + ' ENCODING \'unicode\'')
        cursor.close()

        cmd = ['pg_restore']
        if tools.CONFIG['db_user']:
            cmd.append('--username=' + tools.CONFIG['db_user'])
        if tools.CONFIG['db_host']:
            cmd.append('--host=' + tools.CONFIG['db_host'])
        if tools.CONFIG['db_port']:
            cmd.append('--port=' + tools.CONFIG['db_port'])
        cmd.append('--dbname=' + db_name)
        args2 = tuple(cmd)

        buf = base64.decodestring(data)
        if os.name == "nt":
            tmpfile = (os.environ['TMP'] or 'C:\\') + os.tmpnam()
            file(tmpfile, 'wb').write(buf)
            args2 = list(args2)
            args2.append(' ' + tmpfile)
            args2 = tuple(args2)
        stdin, stdout = tools.exec_pg_command_pipe(*args2)
        if not os.name == "nt":
            stdin.write(base64.decodestring(data))
        stdin.close()
        res = stdout.close()
        if res:
            raise Exception, "Couldn't restore database"
        logger.notify_channel("web-services", LOG_INFO,
                'RESTORE DB: %s' % (db_name))
        return True

    def db_exist(self, db_name):
        try:
            database = sql_db.db_connect(db_name)
            database.truedb.close()
            return True
        except:
            return False

    def list(self):
        database = sql_db.db_connect('template1')
        try:
            cursor = database.cursor()
            db_user = tools.CONFIG["db_user"]
            if not db_user and os.name == 'posix':
                import pwd
                db_user = pwd.getpwuid(os.getuid())[0]
            if not db_user:
                cursor.execute("SELECT usename " \
                        "FROM pg_user " \
                        "WHERE usesysid = (" \
                            "SELECT datdba " \
                            "FROM pg_database " \
                            "WHERE datname = %s)",
                            (tools.CONFIG["db_name"],))
                res = cursor.fetchone()
                db_user = res and res[0]
            if db_user:
                cursor.execute("SELECT datname " \
                        "FROM pg_database " \
                        "WHERE datdba = (" \
                            "SELECT usesysid " \
                            "FROM pg_user " \
                            "WHERE usename=%s) " \
                            "AND datname not in " \
                                "('template0', 'template1', 'postgres')",
                                (db_user,))
            else:
                cursor.execute("SELECT datname " \
                        "FROM pg_database " \
                        "WHERE datname not in " \
                            "('template0', 'template1','postgres')")
            res = [name for (name,) in cursor.fetchall()]
            cursor.close()
        except:
            res = []
        database.truedb.close()
        return res

    def change_admin_password(self, old_password, new_password):
        security.check_super(old_password)
        tools.CONFIG['admin_passwd'] = new_password
        tools.CONFIG.save()
        return True

    def list_lang(self):
        return tools.scan_languages()
