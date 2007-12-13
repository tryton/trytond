"Objects Services"

from orm import orm, except_orm
from trytond.netsvc import Service, LocalService, Logger, LOG_ERROR
from trytond import pooler
import copy
import sys
from psycopg import IntegrityError
from trytond.tools import UpdateableDict

MODULE_LIST = []
MODULE_CLASS_LIST = {}
CLASS_POOL = {}

class ExceptOSV(Exception):

    def __init__(self, name, value, exc_type='warning'):
        Exception.__init__(self)
        self.name = name
        self.exc_type = exc_type
        self.value = value
        self.args = (exc_type, name)

except_osv = ExceptOSV

class OSVService(Service):

    def __init__(self):
        self.object_name_pool = {}
        self.module_obj_list = {}
        self.created = []
        self._sql_error = {}
        Service.__init__(self, 'object_proxy')
        Service.join_group(self, 'web-services')
        Service.export_method(self, self.object_name_list)
        Service.export_method(self, self.exec_workflow)
        Service.export_method(self, self.execute)
        Service.export_method(self, self.execute_cr)

    def execute_cr(self, cursor, user, object_name, method, *args, **kargs):
        # TODO: check security level
        try:
            obj = pooler.get_pool(cursor.dbname).get(object_name)
            if not obj:
                self.abort_response('Object Error', 'warning',
                'Object %s doesn\'t exist' % str(object_name))
            if (not method in getattr(obj,'_protected')) and len(args) \
                    and args[0] and len(obj._inherits):
                types = {object_name: args[0]}
                cursor.execute('SELECT inst_type, inst_id, object_name_id ' \
                        'FROM inherit ' \
                        'WHERE object_name_type = %s '\
                            'AND  object_name_id in (' + \
                            ','.join([str(x) for x in args[0]]) + ')',
                            (object_name,))
                for inst_type, inst_id, object_name_id in cursor.fetchall():
                    if not inst_type in types:
                        types[inst_type] = []
                    types[inst_type].append(inst_id)
                    types[object_name].remove(object_name_id)
                for i, ids in types.items():
                    if len(ids):
                        obj_t = pooler.get_pool(cursor.dbname).get(i)
                        res = getattr(obj_t, method)(cursor, user, ids,
                                *args[1:], **kargs)
            else:
                res = getattr(obj, method)(cursor, user, *args, **kargs)
            return res
        except except_orm, inst:
            self.abort_response(inst.name, 'warning', inst.value)
        except ExceptOSV, inst:
            self.abort_response(inst.name, inst.exc_type, inst.value)
        except IntegrityError, inst:
            for key in self._sql_error.keys():
                if key in inst[0]:
                    self.abort_response('Constraint Error', 'warning',
                            self._sql_error[key])
            self.abort_response('Integrity Error', 'warning', inst[0])
        except:
            import traceback
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_traceback))
            logger = Logger()
            logger.notify_channel("web-services", LOG_ERROR,
                    'Exception in call: ' + tb_s)
            raise

    def execute(self, dbname, user, object_name, method, *args, **kargs):
        database, pool = pooler.get_db_and_pool(dbname)
        cursor = database.cursor()
        # TODO add retry when exception for concurency update
        try:
            try:
                res = pool.execute_cr(cursor, user, object_name, method,
                        *args, **kargs)
                cursor.commit()
            except Exception:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def exec_workflow_cr(self, cursor, user, object_name, method, *args):
        wf_service = LocalService("workflow")
        wf_service.trg_validate(user, object_name, args[0], method, cursor)
        return True

    def exec_workflow(self, dbname, user, object_name, method, *args):
        cursor = pooler.get_db(dbname).cursor()
        # TODO add retry when exception for concurency update
        try:
            try:
                res = self.exec_workflow_cr(cursor, user, object_name, method,
                        *args)
                cursor.commit()
            except Exception:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def object_name_list(self):
        return self.object_name_pool.keys()

    def add(self, name, object_name_inst):
        """
        adds a new obj instance to the obj pool.
        if it already existed, the instance is replaced
        """
        if self.object_name_pool.has_key(name):
            del self.object_name_pool[name]
        self.object_name_pool[name] = object_name_inst

        module = str(object_name_inst.__class__)[6:]
        module = module[:len(module)-1]
        module = module.split('.')[0][2:]
        self.module_obj_list.setdefault(module, []).append(object_name_inst)

    def get(self, name):
        return self.object_name_pool.get(name, None)

    def instanciate(self, module):
        res = []
        class_list = MODULE_CLASS_LIST.get(module, [])
        for klass in class_list:
            res.append(klass.create_instance(self, module))
        return res

osv_pool = OSVService


class OSV(orm):

    def __new__(cls):
        for module in cls.__module__.split('.'):
            if module != 'trytond' and module != 'addons':
                break
        if not hasattr(cls, '_module'):
            cls._module = module
        MODULE_CLASS_LIST.setdefault(cls._module, []).append(cls)
        CLASS_POOL[cls._name] = cls
        if module not in MODULE_LIST:
            MODULE_LIST.append(cls._module)
        return None

    def create_instance(cls, pool, module):
        """
        try to apply inheritancy at the instanciation level and
        put objs in the pool var
        """
        parent_name = hasattr(cls, '_inherit') and cls._inherit
        if parent_name:
            parent_class = pool.get(parent_name).__class__
            assert parent_class, "parent class %s does not exist !" % \
                    parent_name
            nattr = {}
            for i in (
                    '_columns',
                    '_defaults',
                    '_inherits',
                    '_constraints',
                    '_sql_constraints',
                    ):
                new = copy.copy(getattr(pool.get(parent_name), i))
                if hasattr(new, 'update'):
                    new.update(cls.__dict__.get(i, {}))
                else:
                    new.extend(cls.__dict__.get(i, []))
                nattr[i] = new
            name = hasattr(cls,'_name') and cls._name or cls._inherit
            cls = type(name, (cls, parent_class), nattr)

        obj = object.__new__(cls)
        obj.__init__(pool)
        return obj

    create_instance = classmethod(create_instance)

    def __init__(self, pool):
        pool.add(self._name, self)
        self.pool = pool
        orm.__init__(self)

osv = OSV


class Cacheable(object):

    _cache = UpdateableDict()

    def add(self, key, value):
        self._cache[key] = value

    def invalidate(self, key):
        del self._cache[key]

    def get(self, key):
        try:
            return self._cache[key]
        except KeyError:
            return None

    def clear(self):
        self._cache.clear()
