#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.config import CONFIG
from trytond.transaction import Transaction
from trytond.exceptions import NotLogged


def login(dbname, loginname, password, cache=True):
    with Transaction().start(dbname, 0) as transaction:
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        user_obj = pool.get('res.user')
        password = password.decode('utf-8')
        user_id = user_obj.get_login(loginname, password)
        transaction.cursor.commit()
    if user_id:
        if not cache:
            return user_id
        with Transaction().start(dbname, user_id) as transaction:
            session_obj = pool.get('ir.session')
            session = session_obj.browse(session_obj.create({}))
            transaction.cursor.commit()
            return user_id, session.key
    return False


def logout(dbname, user, session):
    with Transaction().start(dbname, 0) as transaction:
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        session_obj = pool.get('ir.session')
        session_id, = session_obj.search([
                ('key', '=', session),
                ])
        session = session_obj.browse(session_id)
        name = session.create_uid.login
        session_obj.delete(session_id)
        transaction.cursor.commit()
    return name


def check_super(passwd):
    if passwd == CONFIG['admin_passwd']:
        return True
    else:
        raise Exception('AccessDenied')


def check(dbname, user, session):
    if user == 0:
        raise Exception('AccessDenied')
    if not user:
        raise NotLogged()
    with Transaction().start(dbname, user) as transaction:
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        session_obj = pool.get('ir.session')
        try:
            if not session_obj.check(user, session):
                raise NotLogged()
            else:
                return user
        finally:
            transaction.cursor.commit()
