#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE, cursor
from psycopg2 import IntegrityError
import psycopg2
import re
import os
from mx import DateTime as mdt
import zipfile
import version
from config import CONFIG

RE_FROM = re.compile('.* from "?([a-zA-Z_0-9]+)"?.*$')
RE_INTO = re.compile('.* into "?([a-zA-Z_0-9]+)"?.*$')

class tryton_cursor(cursor):

    def __build_dict(self, row):
        res = {}
        for i in range(len(self.description)):
            res[self.description[i][0]] = row[i]
        return res

    def dictfetchone(self):
        row = self.fetchone()
        if row:
            return self.__build_dict(row)
        else:
            return row

    def dictfetchmany(self, size):
        res = []
        rows = self.fetchmany(size)
        for row in rows:
            res.append(self.__build_dict(row))
        return res

    def dictfetchall(self):
        res = []
        rows = self.fetchall()
        for row in rows:
            res.append(self.__build_dict(row))
        return res


class FakeCursor(object):
    nbr = 0
    _tables = {}
    sql_from_log = {}
    sql_into_log = {}
    sql_log = False
    count = 0

    def __init__(self, connpool, conn, dbname, cursor_factory):
        self._connpool = connpool
        self.conn = conn
        self.cursor_factory = cursor_factory
        self.cursor = conn.cursor(cursor_factory=self.cursor_factory)
        self.dbname = dbname

    def execute(self, sql, params=None):
        if not params:
            params = ()

        if self.sql_log:
            now = mdt.now()
        if params:
            res = self.cursor.execute(sql, params)
        else:
            res = self.cursor.execute(sql)
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
        self.cursor.close()

        # This force the cursor to be freed, and thus, available again. It is
        # important because otherwise we can overload the server very easily
        # because of a cursor shortage (because cursors are not garbage
        # collected as fast as they should). The problem is probably due in
        # part because browse records keep a reference to the cursor.
        del self.cursor
        self._connpool.putconn(self.conn)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def __getattr__(self, name):
        return getattr(self.cursor, name)

class FakeDB:

    def __init__(self, connpool, dbname):
        self._connpool = connpool
        self.dbname = dbname

    def cursor(self, cursor_factory=tryton_cursor):
        conn = self._connpool.getconn()
        conn.set_isolation_level(ISOLATION_LEVEL_SERIALIZABLE)
        return FakeCursor(self._connpool, conn, self.dbname,
                cursor_factory=cursor_factory)

    def close(self):
        self._connpool.closeall()

def db_connect(db_name):
    host = CONFIG['db_host'] and "host=%s" % CONFIG['db_host'] or ''
    port = CONFIG['db_port'] and "port=%s" % CONFIG['db_port'] or ''
    name = "dbname=%s" % db_name
    user = CONFIG['db_user'] and "user=%s" % CONFIG['db_user'] or ''
    password = CONFIG['db_password'] \
            and "password=%s" % CONFIG['db_password'] or ''
    maxconn = int(CONFIG['db_maxconn']) or 64
    dsn = '%s %s %s %s %s' % (host, port, name, user, password)
    connpool = ThreadedConnectionPool(0, maxconn, dsn)
    return FakeDB(connpool, db_name)

def init_db(cursor):
    sql_file = os.path.join(os.path.dirname(__file__), 'init.sql')
    for line in file(sql_file).read().split(';'):
        if (len(line)>0) and (not line.isspace()):
            cursor.execute(line)

    opj = os.path.join
    modules_path = os.path.join(os.path.dirname(__file__), 'modules')
    modules = []
    if os.path.exists(modules_path) and os.path.isdir(modules_path):
        modules = os.listdir(modules_path)

    for i in (modules + ['ir', 'workflow', 'res', 'webdav']):
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
                            'WHERE name = %s AND parent = %s',
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
                            'VALUES (%s, %s, %s)', (c_id, categs[0], p_id))
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
                    '(id, author, website, name, shortdesc, ' \
                    'description, category, state) ' \
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (module_id, info.get('author', ''),
                info.get('website', ''), i, info.get('name', False),
                info.get('description', ''), p_id, state))
            dependencies = info.get('depends', [])
            for dependency in dependencies:
                cursor.execute('INSERT INTO ir_module_module_dependency ' \
                        '(module, name) VALUES (%s, %s)',
                        (module_id, dependency))

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
