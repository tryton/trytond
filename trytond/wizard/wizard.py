"Wizard"
from trytond.netsvc import Service, service_exist, Logger, LOG_ERROR
from trytond import pooler
import copy
from xml import dom
from trytond.osv import ExceptORM, ExceptOSV
import sys

class ExceptWizard(Exception):
    def __init__(self, name, value):
        Exception.__init__(self)
        self.name = name
        self.value = value
        self.args = (name, value)

except_wizard = ExceptWizard

class WizardService(Service):
    states = {}
    name = ""

    def __init__(self):
        self.wiz_name = self.name
        assert not service_exist(self.wiz_name), \
                'The wizard "%s" already exists!' % self.name
        Service.__init__(self, self.wiz_name)
        Service.export_method(self, self.execute)

    def translate_view(self, cursor, node, state, lang):
        translation_obj = pooler.get_pool(cursor.dbname).get('ir.translation')
        if node.nodeType == node.ELEMENT_NODE:
            if node.hasAttribute('string') \
                    and node.getAttribute('string'):
                res_trans = translation_obj._get_source(cursor,
                        self.wiz_name + ',' + state, 'wizard_view', lang)
                if res_trans:
                    node.setAttribute('string', res_trans.decode('utf8'))
        for child_node in node.childNodes:
            self.translate_view(cursor, child_node, state, lang)

    def execute_cr(self, cursor, user, data, state='init', context=None):
        if context is None:
            context = {}
        res = {}
        pool = pooler.get_pool(cursor.dbname)
        values_obj = pool.get('ir.values')
        translation_obj = pool.get('ir.translation')
        try:
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
                        False, [('wizard.'+self.wiz_name, False)])
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
                            self.wiz_name + ',' + state + ',' + field,
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
                            self.wiz_name + ',' + state + ',' + button_name,
                            'wizard_button', lang)
                    if res_trans:
                        button = list(button)
                        button[1] = res_trans
                        button_list[i] = tuple(button)

                res['fields'] = fields
                res['arch'] = arch
                res['state'] = button_list

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

        if result_def['type'] == 'choice':
            next_state = result_def['next_state'](self, cursor, user,
                    data, context)
            return self.execute_cr(cursor, user, data, next_state, context)
        return res

    def execute(self, dbname, user, data, state='init', context=None):
        cursor = pooler.get_db(dbname).cursor()
        try:
            try:
                res = self.execute_cr(cursor, user, data, state, context)
                cursor.commit()
            except Exception:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res
