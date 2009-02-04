#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE, cursor, AsIs
from psycopg2 import IntegrityError
import psycopg2
import re
import os
from mx import DateTime as mdt
import zipfile
import version
from config import CONFIG
import logging
from trytond.security import Session
from trytond.backend.postgresql import *

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
    sql_log = False
    IN_MAX = 1000

    def __init__(self, connpool, conn, dbname, cursor_factory):
        self._connpool = connpool
        self.conn = conn
        self.cursor_factory = cursor_factory
        self.cursor = conn.cursor(cursor_factory=self.cursor_factory)
        self.dbname = dbname
        self.sql_from_log = {}
        self.sql_into_log = {}
        self.count = {
            'from': 0,
            'into': 0,
        }

    def execute(self, sql, params=None):
        if not params:
            params = ()

        if self.sql_log:
            now = mdt.now()
        try:
            if params:
                res = self.cursor.execute(sql, params)
            else:
                res = self.cursor.execute(sql)
        except:
            logger = logging.getLogger('sql')
            logger.error('Wrong SQL: ' + sql % tuple("'%s'" % unicode(x)
                for x in params or []))
            raise
        if self.sql_log:
            res_from = RE_FROM.match(sql.lower())
            if res_from:
                self.sql_from_log.setdefault(res_from.group(1), [0, 0])
                self.sql_from_log[res_from.group(1)][0] += 1
                self.sql_from_log[res_from.group(1)][1] += mdt.now() - now
                self.count['from'] += 1
            res_into = RE_INTO.match(sql.lower())
            if res_into:
                self.sql_into_log.setdefault(res_into.group(1), [0, 0])
                self.sql_into_log[res_into.group(1)][0] += 1
                self.sql_into_log[res_into.group(1)][1] += mdt.now() - now
                self.count['into'] += 1
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
        print "SUM:%s/%d"% (amount, self.count[sql_type])

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

    def test(self):
        '''
        Test if it is a Tryton database.
        '''
        self.cursor.execute("SELECT relname " \
                "FROM pg_class " \
                "WHERE relkind = 'r' AND relname in (" \
                "'inherit', "
                "'ir_model', "
                "'ir_model_field', "
                "'ir_ui_view', "
                "'ir_ui_menu', "
                "'res_user', "
                "'res_group', "
                "'res_group_user_rel', "
                "'wkf', "
                "'wkf_activity', "
                "'wkf_transition', "
                "'wkf_instance', "
                "'wkf_workitem', "
                "'wkf_witm_trans', "
                "'ir_module_module', "
                "'ir_module_module_dependency, '"
                "'ir_translation, '"
                "'ir_lang'"
                ")")
        return len(self.cursor.fetchall()) != 0


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

    for i in ('ir', 'workflow', 'res', 'webdav'):
        root_path = os.path.dirname(__file__)
        tryton_file = os.path.join(root_path, i, '__tryton__.py')
        mod_path = os.path.join(root_path, i)
        info = eval(file(tryton_file).read())
        active = info.get('active', False)
        if active:
            state = 'to install'
        else:
            state = 'uninstalled'
        cursor.execute('SELECT NEXTVAL(\'ir_module_module_id_seq\')')
        module_id = cursor.fetchone()[0]
        cursor.execute('INSERT INTO ir_module_module ' \
                '(id, author, website, name, shortdesc, ' \
                'description, state) ' \
                'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (module_id, info.get('author', ''),
            info.get('website', ''), i, info.get('name', False),
            info.get('description', ''), state))
        dependencies = info.get('depends', [])
        for dependency in dependencies:
            cursor.execute('INSERT INTO ir_module_module_dependency ' \
                    '(module, name) VALUES (%s, %s)',
                    (module_id, dependency))

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_adapter(Session,
        psycopg2.extensions.AsIs)
