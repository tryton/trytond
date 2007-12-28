"Wizard"
from trytond.netsvc import Service, service_exist, Logger, LOG_ERROR
from trytond import pooler
import copy
from xml import dom
from trytond.osv import ExceptORM, ExceptOSV
import sys

MODULE_LIST = []
MODULE_CLASS_LIST = {}
CLASS_POOL = {}


class ExceptWizard(Exception):
    def __init__(self, name, value):
        Exception.__init__(self)
        self.name = name
        self.value = value
        self.args = (name, value)

except_wizard = ExceptWizard

class WizardService(Service):

    def __init__(self):
        self.object_name_pool = {}
        self.module_obj_list = {}
        Service.__init__(self, 'wizard_proxy')
        Service.join_group(self, 'web-services')
        Service.export_method(self, self.execute)

    def execute_cr(self, cursor, user, wizard_name, data, state='init',
            context=None):
        try:
            wizard = pooler.get_pool_wizard(cursor.dbname).get(wizard_name)
            if not wizard:
                self.abort_response('Wizard Error', 'warning',
                        'Wizard %s doesn\'t exist' % str(wizard_name))
            res = wizard.execute(cursor, user, data, state, context)
            return res
        except ExceptORM, inst:
            self.abort_response(inst.name, 'warning', inst.value)
        except ExceptOSV, inst:
            self.abort_response(inst.name, inst.exc_type, inst.value)
        except ExceptWizard, inst:
            self.abort_response(inst.name, 'warning', inst.value)
        except:
            import traceback
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_traceback))
            Logger().notify_channel("web-services", LOG_ERROR,
                    'Exception in call: ' + tb_s)
            raise

    def execute(self, dbname, user, wizard_name, data, state='init',
            context=None):
        cursor = pooler.get_db(dbname).cursor()
        pool = pooler.get_pool_wizard(dbname)
        try:
            try:
                res = pool.execute_cr(cursor, user, wizard_name, data, state,
                        context)
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


class Wizard(object):
    _name = ""
    states = {}

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
            new_states = copy.copy(getattr(pool.get(cls._name), 'states'))
            for i in (
                    'actions',
                    'result',
                    ):
                new = copy.copy(getattr(new_states, i))
                if hasattr(new, 'update'):
                    new.update(cls.__dict__.get(i, {}))
                else:
                    new.extend(cls.__dict__.get(i, []))
                new_states[i] = new
            cls = type(cls._name, (cls, parent_class), {'states': new_states})

        obj = object.__new__(cls)
        obj.__init__(pool, pool_obj)
        return obj

    create_instance = classmethod(create_instance)

    def __init__(self, pool, pool_obj):
        pool.add(self._name, self)
        self.pool = pool_obj
        super(Wizard, self).__init__()

    def translate_view(self, cursor, node, state, lang):
        translation_obj = pooler.get_pool(cursor.dbname).get('ir.translation')
        if node.nodeType == node.ELEMENT_NODE:
            if node.hasAttribute('string') \
                    and node.getAttribute('string'):
                res_trans = translation_obj._get_source(cursor,
                        self._name + ',' + state, 'wizard_view', lang)
                if res_trans:
                    node.setAttribute('string', res_trans.decode('utf8'))
        for child_node in node.childNodes:
            self.translate_view(cursor, child_node, state, lang)

    def execute(self, cursor, user, data, state='init', context=None):
        if context is None:
            context = {}
        res = {}
        values_obj = self.pool.get('ir.values')
        translation_obj = self.pool.get('ir.translation')

        state_def = self.states[state]
        result_def = copy.copy(state_def.get('result', {}))

        # iterate through the list of actions defined for this state
        for action in state_def.get('actions', []):
            # execute them
            action_res = action(self, cursor, user, data, context)
            assert isinstance(action_res, dict), \
                    'The return value of wizard actions ' \
                    'should be a dictionary'
            result_def.update(action_res)

        res = copy.copy(result_def)
        res['datas'] = result_def.get('datas', {})

        lang = context.get('lang', 'en_US')
        if result_def['type'] == 'action':
            res['action'] = result_def['action'](self, cursor, user, data,
                    context)
        elif result_def['type'] == 'form':
            fields = copy.copy(result_def['fields'])
            arch = copy.copy(result_def['arch'])
            button_list = copy.copy(result_def['state'])

            defaults = values_obj.get(cursor, user, 'default',
                    False, [(self._name, False)])
            default_values = dict([(x[1], x[2]) for x in defaults])
            for val in fields.keys():
                if 'default' in fields[val]:
                    # execute default method for this field
                    if callable(fields[val]['default']):
                        fields[val]['value'] = fields[val]['default']\
                                (self, cursor, user, data, state, context)
                    else:
                        fields[val]['value'] = fields[val]['default']
                    del fields[val]['default']
                if val in default_values:
                    fields[val]['value'] = default_values[val]
                if 'selection' in fields[val]:
                    if callable(fields[val]['selection']):
                        fields[val] = copy.copy(fields[val])
                        fields[val]['selection'] = fields[val]['selection']\
                                (self, cursor, user, data, state, context)

            # translate fields
            for field in fields:
                res_trans = translation_obj._get_source(cursor, user,
                        self._name + ',' + state + ',' + field,
                        'wizard_field', lang)
                if res_trans:
                    fields[field]['string'] = res_trans

            # translate arch
            doc = dom.minidom.parseString(arch)
            self.translate_view(cursor, doc, state, lang)
            arch = doc.toxml()

            # translate buttons
            for i, button  in enumerate(button_list):
                button_name = button[0]
                res_trans = translation_obj._get_source(cursor, user,
                        self._name + ',' + state + ',' + button_name,
                        'wizard_button', lang)
                if res_trans:
                    button = list(button)
                    button[1] = res_trans
                    button_list[i] = tuple(button)

            res['fields'] = fields
            res['arch'] = arch
            res['state'] = button_list
        if result_def['type'] == 'choice':
            next_state = result_def['next_state'](self, cursor, user,
                    data, context)
            return self.execute(cursor, user, data, next_state, context)
        return res
