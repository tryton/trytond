import pooler
from config import CONFIG

_USER_CACHE = {}

def login(dbname, loginname, password):
    cursor = pooler.get_db(dbname).cursor()
    cursor.execute('SELECT id FROM res_user '
        'WHERE login = %s and password = %s and active',
        (loginname.encode('utf-8'), password.encode('utf-8')))
    res = cursor.fetchone()
    cursor.close()
    if res:
        return res[0]
    else:
        return False

def check_super(passwd):
    if passwd == CONFIG['admin_passwd']:
        return True
    else:
        raise Exception('AccessDenied')

def check(dbname, user, passwd):
    # FIXME: this should be db dependent
    if _USER_CACHE.has_key(user) and (_USER_CACHE[user]==passwd):
        return True
    cursor = pooler.get_db(dbname).cursor()
    cursor.execute('SELECT count(*) FROM res_user ' \
            'WHERE id = %s AND password = %s', (int(user), passwd))
    res = cursor.fetchone()[0]
    cursor.close()
    if not bool(res):
        raise Exception('AccessDenied')
    if res:
        _USER_CACHE[user] = passwd
    return bool(res)
