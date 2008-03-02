import pooler
from config import CONFIG
import sha

_USER_CACHE = {}

def login(dbname, loginname, password):
    loginname = loginname.encode('utf-8')
    password = password.encode('utf-8')
    cursor = pooler.get_db(dbname).cursor()
    password_sha = sha.new(password).hexdigest()
    cursor.execute('SELECT id FROM res_user '
        'WHERE login = %s and password = %s and active',
        (loginname, password_sha))
    res = cursor.fetchone()
    cursor.close()
    if res:
        _USER_CACHE.setdefault(dbname, {})
        _USER_CACHE[dbname][res[0]] = password_sha
        return res[0]
    else:
        return False

def check_super(passwd):
    if passwd == CONFIG['admin_passwd']:
        return True
    else:
        raise Exception('AccessDenied')

def check(dbname, user, password):
    password = password.encode('utf-8')
    password_sha = sha.new(password).hexdigest()
    if _USER_CACHE.get(dbname, {}).has_key(user) \
            and _USER_CACHE[dbname][user] == password_sha:
        return True
    cursor = pooler.get_db(dbname).cursor()
    cursor.execute('SELECT id FROM res_user '
        'WHERE id = %s and password = %s and active',
        (user, password_sha))
    res = cursor.fetchone()
    cursor.close()
    if res:
        _USER_CACHE.setdefault(dbname, {})
        _USER_CACHE[dbname][res[0]] = password_sha
        return True
    raise Exception('NotLogged')
