import psycopg
import re
import os
from mx import DateTime as mdt
import zipfile
import version
from config import CONFIG

RE_FROM = re.compile('.* from "?([a-zA-Z_0-9]+)"? .*$')
RE_INTO = re.compile('.* into "?([a-zA-Z_0-9]+)"? .*$')

class FakeCursor:
    nbr = 0
    _tables = {}
    sql_from_log = {}
    sql_into_log = {}
    sql_log = False
    count = 0

    def __init__(self, database, con, dbname):
        self.db = database
        self.obj = database.cursor()
        self.con = con
        self.dbname = dbname

    def execute(self, sql, params=None):
        if not params:
            params = ()

        def base_string(string):
            if isinstance(string, unicode):
                return string.encode('utf-8')
            return string

        para = [base_string(string) for string in params]
        if isinstance(sql, unicode):
            sql = sql.encode('utf-8')
        if self.sql_log:
            now = mdt.now()
        if para:
            res = self.obj.execute(sql, para)
        else:
            res = self.obj.execute(sql)
        if self.sql_log:
            self.count += 1
            res_from = RE_FROM.match(sql.lower())
            if res_from:
                self.sql_from_log.setdefault(res_from.group(1), [0, 0])
                self.sql_from_log[res_from.group(1)][0] += 1
                self.sql_from_log[res_from.group(1)][1] += mdt.now() - now
            res_into = RE_INTO.match(sql.lower())
            if res_into:
                self.sql_into_log.setdefault(res_into.group(1), [0, 0])
                self.sql_into_log[res_into.group(1)][0] += 1
                self.sql_into_log[res_into.group(1)][1] += mdt.now() - now
        return res

    def print_log(self, sql_type='from'):
        print "SQL LOG %s:" % (sql_type,)
        if sql_type == 'from':
            logs = self.sql_from_log.items()
        else:
            logs = self.sql_into_log.items()
        logs.sort(lambda x, y: cmp(x[1][1], y[1][1]))
        amount = 0
        for log in logs:
            print "table:", log[0], ":", str(log[1][1]), "/", log[1][0]
            amount += log[1][1]
        print "SUM:%s/%d"% (amount, self.count)

    def close(self):
        if self.sql_log:
            self.print_log('from')
            self.print_log('into')
        self.obj.close()

        # This force the cursor to be freed, and thus, available again. It is
        # important because otherwise we can overload the server very easily
        # because of a cursor shortage (because cursors are not garbage
        # collected as fast as they should). The problem is probably due in
        # part because browse records keep a reference to the cursor.
        del self.obj

    def __getattr__(self, name):
        return getattr(self.obj, name)

class FakeDB:

    def __init__(self, truedb, dbname):
        self.truedb = truedb
        self.dbname = dbname

    def cursor(self):
        return FakeCursor(self.truedb, {}, self.dbname)

def db_connect(db_name, serialize=0):
    host = CONFIG['db_host'] and "host=%s" % CONFIG['db_host'] or ''
    port = CONFIG['db_port'] and "port=%s" % CONFIG['db_port'] or ''
    name = "dbname=%s" % db_name
    user = CONFIG['db_user'] and "user=%s" % CONFIG['db_user'] or ''
    password = CONFIG['db_password'] \
            and "password=%s" % CONFIG['db_password'] or ''
    maxconn = int(CONFIG['db_maxconn']) or 64
    tdb = psycopg.connect('%s %s %s %s %s' % (host, port, name, user, password),
            serialize=serialize, maxconn=maxconn)
    fdb = FakeDB(tdb, db_name)
    return fdb

def init_db(cursor):
    sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
    for line in file(sql_file).read().split(';'):
        if (len(line)>0) and (not line.isspace()):
            cursor.execute(line)

    opj = os.path.join
    modules_path = os.path.join(os.path.dirname(__file__), 'modules')

    for i in (os.listdir(modules_path) + ['ir', 'workflow', 'res', 'webdav']):
        tryton_file = opj(modules_path, i, '__tryton__.py')
        mod_path = opj(modules_path, i)
        if i in ('ir', 'workflow', 'res', 'webdav'):
            root_path = os.path.dirname(__file__)
            tryton_file = opj(root_path, i, '__tryton__.py')
            mod_path = opj(root_path, i)
        info = {}
        if os.path.isfile(tryton_file) \
                and not os.path.isfile(opj(modules_path, i + '.zip')):
            info = eval(file(tryton_file).read())
        elif zipfile.is_zipfile(mod_path):
            zfile = zipfile.ZipFile(mod_path)
            i = os.path.splitext(i)[0]
            info = eval(zfile.read(opj(i, '__tryton__.py')))
        if info:
            categs = info.get('category', 'Uncategorized').split('/')
            p_id = None
            while categs:
                if p_id is not None:
                    cursor.execute('SELECT id ' \
                            'FROM ir_module_category ' \
                            'WHERE name = %s AND parent = %d',
                            (categs[0], p_id))
                else:
                    cursor.execute('SELECT id ' \
                            'FROM ir_module_category ' \
                            'WHERE name = %s AND parent is NULL',
                            (categs[0],))
                c_id = cursor.fetchone()
                if not c_id:
                    cursor.execute(
                            'SELECT NEXTVAL(\'ir_module_category_id_seq\')')
                    c_id = cursor.fetchone()[0]
                    cursor.execute('INSERT INTO ir_module_category ' \
                            '(id, name, parent) ' \
                            'VALUES (%d, %s, %d)', (c_id, categs[0], p_id))
                else:
                    c_id = c_id[0]
                p_id = c_id
                categs = categs[1:]

            active = info.get('active', False)
            installable = info.get('installable', True)
            if installable:
                if active:
                    state = 'to install'
                else:
                    state = 'uninstalled'
            else:
                state = 'uninstallable'
            cursor.execute('SELECT NEXTVAL(\'ir_module_module_id_seq\')')
            module_id = cursor.fetchone()[0]
            cursor.execute('INSERT INTO ir_module_module ' \
                    '(id, author, latest_version, website, name, shortdesc, ' \
                    'description, category_id, state) ' \
                    'VALUES (%d, %s, %s, %s, %s, %s, %s, %d, %s)',
                    (module_id, info.get('author', ''),
                version.VERSION.rsplit('.', 1)[0] + '.' + info.get('version', ''),
                info.get('website', ''), i, info.get('name', False),
                info.get('description', ''), p_id, state))
            dependencies = info.get('depends', [])
            for dependency in dependencies:
                cursor.execute('INSERT INTO ir_module_module_dependency ' \
                        '(module_id, name) VALUES (%s, %s)',
                        (module_id, dependency))

psycopg.register_type(psycopg.new_type((1082,), "date", lambda x:x))
psycopg.register_type(psycopg.new_type((1083,), "time", lambda x:x))
psycopg.register_type(psycopg.new_type((1114,), "datetime", lambda x:x))
