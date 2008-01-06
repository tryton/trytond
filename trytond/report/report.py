"Report"
from trytond.netsvc import Service, service_exist, Logger, LOG_ERROR
from trytond import pooler
import copy
from xml import dom
from trytond.osv import ExceptORM, ExceptOSV, OSV
import sys
import base64

MODULE_LIST = []
MODULE_CLASS_LIST = {}
CLASS_POOL = {}


class ReportService(Service):

    def __init__(self):
        self.object_name_pool = {}
        self.module_obj_list = {}
        Service.__init__(self, 'report_proxy')
        Service.join_group(self, 'web-services')
        Service.export_method(self, self.execute)

    def execute_cr(self, cursor, user, report_name, ids, datas, context=None):
        try:
            report = pooler.get_pool_report(cursor.dbname).get(report_name)
            if not report:
                self.abort_response('Report Error', 'warning',
                        'Report %s doesn\'t exist' % str(report_name))
            res = report.execute(cursor, user, ids, datas, context)
            return res
        except ExceptORM, inst:
            self.abort_response(inst.name, 'warning', inst.value)
        except ExceptOSV, inst:
            self.abort_response(inst.name, inst.exc_type, inst.value)
        except:
            import traceback
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_traceback))
            Logger().notify_channel("web-services", LOG_ERROR,
                    'Exception in call: ' + tb_s)
            raise

    def execute(self, dbname, user, report_name, ids, datas, context=None):
        cursor = pooler.get_db(dbname).cursor()
        pool = pooler.get_pool_report(dbname)
        try:
            try:
                res = pool.execute_cr(cursor, user, report_name, ids, datas, context)
                cursor.commit()
            except Exception:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

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

    def instanciate(self, module, pool_obj):
        res = []
        class_list = MODULE_CLASS_LIST.get(module, [])
        for klass in class_list:
            res.append(klass.create_instance(self, module, pool_obj))
        return res

class Report(object):
    _name = ""

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

    def create_instance(cls, pool, module, pool_obj):
        """
        try to apply inheritancy at the instanciation level and
        put objs in the pool var
        """
        if pool.get(cls._name):
            parent_class = pool.get(cls._name).__class__
            nattr = {}
            for i in (
                    '_context',
                    ):
                new = copy.copy(getattr(pool.get(cls._name), i))
                if hasattr(new, 'update'):
                    new.update(cls.__dict__.get(i, {}))
                else:
                    new.extend(cls.__dict__.get(i, []))
                nattr[i] = new
            cls = type(cls._name, (cls, parent_class), nattr)


        obj = object.__new__(cls)
        obj.__init__(pool, pool_obj)
        return obj

    create_instance = classmethod(create_instance)

    def __init__(self, pool, pool_obj):
        pool.add(self._name, self)
        self.pool = pool_obj
        super(Report, self).__init__()

    def execute(self, cursor, user, ids, datas, context=None):
        action_report_obj = self.pool.get('ir.actions.report')
        action_report_ids = action_report_obj.search(cursor, user, [
            ('report_name', '=', self._name)
            ], context=context)
        action_report = action_report_obj.browse(cursor, user,
                action_report_ids[0], context=context)
        #TODO add parser
        type, data = 'odt', action_report.report_content
        return (type, base64.encodestring(data))
