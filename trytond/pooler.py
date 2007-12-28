from sql_db import db_connect
from netsvc import Logger, LOG_INFO

_DB = {}
_POOL = {}
_POOL_WIZARD = {}

def get_db_and_pool(db_name, force_demo=False, update_module=False,
        wizard=False):
    if db_name in _DB:
        database = _DB[db_name]
    else:
        Logger().notify_channel('pooler', LOG_INFO,
                'Connecting to %s' % (db_name))
        database = db_connect(db_name)
        _DB[db_name] = database

    if db_name in _POOL:
        pool = _POOL[db_name]
        pool_wizard = _POOL_WIZARD[db_name]
    else:
        Logger().notify_channel('pooler', LOG_INFO,
                'Instanciate pooler for %s' % (db_name))
        from osv.osv import OSVService
        pool = OSVService()
        _POOL[db_name] = pool

        from wizard import WizardService
        pool_wizard = WizardService()
        _POOL_WIZARD[db_name] = pool_wizard

        from module import load_modules
        load_modules(database, force_demo, update_module)

        if not update_module:
            import report
            #report.interface.register_all(database)
            pool.get('ir.cron').pool_jobs(database.dbname)
    if wizard:
        return database, pool_wizard
    return database, pool

def restart_pool(db_name, force_demo=False, update_module=False):
    del _POOL[db_name]
    return get_db_and_pool(db_name, force_demo, update_module=update_module)

def close_db(db_name):
    if db_name in _DB:
        _DB[db_name].truedb.close()
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

def get_pool(db_name, force_demo=False, update_module=False):
    pool = get_db_and_pool(db_name, force_demo, update_module)[1]
    return pool

def get_pool_wizard(db_name, force_demo=False, update_module=False):
    pool = get_db_and_pool(db_name, force_demo, update_module, wizard=True)[1]
    return pool
