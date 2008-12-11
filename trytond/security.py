#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import pooler
from config import CONFIG
import sha
import time
import random


class Session(int):

    def __init__(self, x):
        super(Session, self).__init__(x)
        self.__data = {
            'session': str(random.random()),
            'timestamp': time.time(),
        }

    def __getattr__(self, name):
        return self.__data[name]

    def __getitem__(self, name):
        return self.__data[name]

    def reset_timestamp(self):
        self.__data['timestamp'] = time.time()

_USER_CACHE = {}

def login(dbname, loginname, password, cache=True):
    cursor = pooler.get_db(dbname).cursor()
    password_sha = sha.new(password).hexdigest()
    cursor.execute('SELECT id FROM res_user '
        'WHERE login = %s and password = %s and active',
        (loginname, password_sha))
    res = cursor.fetchone()
    cursor.close()
    if res:
        user_id = res[0]
        if user_id == 0:
            return False
        if cache:
            _USER_CACHE.setdefault(dbname, {})
            _USER_CACHE[dbname].setdefault(user_id, [])
            session = Session(user_id)
            _USER_CACHE[dbname][user_id].append(session)
            return (user_id, session.session)
        else:
            return user_id
    else:
        return False

def check_super(passwd):
    if passwd == CONFIG['admin_passwd']:
        return True
    else:
        raise Exception('AccessDenied')

def check(dbname, user, session, outdate_timeout=True):
    if user == 0:
        raise Exception('AccessDenied')
    result = False
    now = time.time()
    timeout = int(CONFIG['session_timeout'])
    if _USER_CACHE.get(dbname, {}).has_key(user):
        to_del = []
        for i, real_session \
                in enumerate(_USER_CACHE[dbname][user]):
            if abs(real_session.timestamp - now) < timeout:
                if real_session.session == session:
                    if outdate_timeout:
                        real_session.reset_timestamp()
                    result = real_session
            else:
                to_del.insert(0, i)
        for i in to_del:
            del _USER_CACHE[dbname][user][i]
    if result:
        return result
    raise Exception('NotLogged')
