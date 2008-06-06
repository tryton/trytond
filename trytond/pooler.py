from sql_db import db_connect
from netsvc import Logger, LOG_INFO

_DB = {}
_POOL = {}
_POOL_WIZARD = {}
_POOL_REPORT = {}

def get_db_and_pool(db_name, update_module=False, wizard=False, report=False,
        lang=None):
    if db_name in _DB:
        database = _DB[db_name]
    else:
        Logger().notify_channel('pooler', LOG_INFO,
                'Connecting to %s' % (db_name))
        database = db_connect(db_name)
        cursor = database.cursor()
        cursor.close()
        _DB[db_name] = database

    if db_name in _POOL:
        pool = _POOL[db_name]
        pool_wizard = _POOL_WIZARD[db_name]
        pool_report = _POOL_REPORT[db_name]
    else:
        Logger().notify_channel('pooler', LOG_INFO,
                'Instanciate pooler for %s' % (db_name))
        from osv.osv import OSVService
        pool = OSVService()
        _POOL[db_name] = pool

        from wizard import WizardService
        pool_wizard = WizardService()
        _POOL_WIZARD[db_name] = pool_wizard

        from report import ReportService
        pool_report = ReportService()
        _POOL_REPORT[db_name] = pool_report

        from module import load_modules
        load_modules(database, update_module, lang)

    if wizard:
        return database, pool_wizard
    if report:
        return database, pool_report
    return database, pool

def restart_pool(db_name, update_module=False, lang=None):
    del _POOL[db_name]
    del _POOL_WIZARD[db_name]
    del _POOL_REPORT[db_name]
    return get_db_and_pool(db_name, update_module=update_module, lang=lang)

def close_db(db_name):
    if db_name in _DB:
        _DB[db_name].close()
        del _DB[db_name]
    if db_name in _POOL:
        del _POOL[db_name]

def get_db_only(db_name):
    if db_name in _DB:
        database = _DB[db_name]
    else:
        Logger().notify_channel('pooler', LOG_INFO,
                'Connecting to %s' % (db_name))
        database = db_connect(db_name)
        _DB[db_name] = database
    return database

def get_db(db_name):
    return get_db_and_pool(db_name)[0]

def get_db_list():
    return _DB.keys()

def get_pool(db_name, update_module=False, lang=None):
    pool = get_db_and_pool(db_name, update_module, lang=lang)[1]
    return pool

def get_pool_wizard(db_name, update_module=False, lang=None):
    pool = get_db_and_pool(db_name, update_module, wizard=True,
            lang=lang)[1]
    return pool

def get_pool_report(db_name, update_module=False, lang=None):
    pool = get_db_and_pool(db_name, update_module, report=True, lang=lang)[1]
    return pool
