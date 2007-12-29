"model"
from trytond.osv import fields, OSV
from trytond.netsvc import Logger, LocalService, LOG_ERROR, LOG_INFO
from trytond.osv.orm import except_orm
from trytond.tools import Cache
import time

class Model(OSV):
    "Model"
    _name = 'ir.model'
    _rec_name = 'model'
    _description = __doc__
    _columns = {
        'name': fields.char('Model name', size=64, translate=True),
        'model': fields.char('Object name', size=64, required=True),
        'info': fields.text('Information'),
        'field_id': fields.one2many('ir.model.fields', 'model_id', 'Fields',
            required=True),
    }
    _defaults = {
        'name': lambda *a: 'No Name',
    }

Model()

class ModelFields(OSV):
    "Model fields"
    _name = 'ir.model.fields'
    _description = __doc__
    _columns = {
        'name': fields.char('Name', size=64),
        'model': fields.char('Model Name', size=64, required=True),
        'relation': fields.char('Model Relation', size=64),
        'model_id': fields.many2one('ir.model', 'Model id', required=True,
            select=True),
        'field_description': fields.char('Field Description', size=256),
        'ttype': fields.char('Field Type', size=64),
        'relate': fields.boolean('Click and Relate'),

        'groups': fields.many2many('res.group', 'ir_model_fields_group_rel',
            'field_id', 'group_id', 'Groups'),
        'group_name': fields.char('Group Name', size=128),
        'view_load': fields.boolean('View Auto-Load'),
    }
    _defaults = {
        'relate': lambda *a: 0,
        'view_load': lambda *a: 0,
        'name': lambda *a: 'No Name',
        'field_description': lambda *a: 'No description available',
    }
    _order = "id"

ModelFields()


class ModelAccess(OSV):
    "Model access"
    _name = 'ir.model.access'
    _description = __doc__
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'model_id': fields.many2one('ir.model', 'Model', required=True),
        'group_id': fields.many2one('res.group', 'Group'),
        'perm_read': fields.boolean('Read Access'),
        'perm_write': fields.boolean('Write Access'),
        'perm_create': fields.boolean('Create Access'),
        'perm_unlink': fields.boolean('Delete Permission'),
    }

    def check(self, cursor, user, model_name, mode='read',
            raise_exception=True):
        assert mode in ['read', 'write', 'create', 'unlink'], \
                'Invalid access mode for security'
        if user == 1:
            return True
        cursor.execute('SELECT MAX(CASE WHEN perm_'+mode+' THEN 1 else 0 END) '
            'FROM ir_model_access a '
                'JOIN ir_model m '
                    'ON (a.model_id=m.id) '
                'JOIN res_group_user_rel gu '
                    'ON (gu.gid = a.group_id) '
            'WHERE m.model = %s AND gu.uid = %s', (model_name, user,))
        row = cursor.fetchall()
        if row[0][0] == None:
            cursor.execute('SELECT ' \
                        'MAX(CASE WHEN perm_' + mode + ' THEN 1 else 0 END) ' \
                    'FROM ir_model_access a ' \
                    'JOIN ir_model m ' \
                        'ON (a.model_id = m.id) ' \
                    'WHERE a.group_id IS NULL AND m.model = %s', (model_name,))
            row = cursor.fetchall()
            if row[0][0] == None:
                return True

        if not row[0][0]:
            if raise_exception:
                if mode == 'read':
                    raise except_orm('AccessError',
                            'You can not read this document!')
                elif mode == 'write':
                    raise except_orm('AccessError',
                            'You can not write in this document!')
                elif mode == 'create':
                    raise except_orm('AccessError',
                            'You can not create this kind of document!')
                elif mode == 'unlink':
                    raise except_orm('AccessError',
                            'You can not delete this document!')
                raise except_orm('AccessError',
                        'You do not have access to this document!')
            else:
                return False
        return True

    check = Cache()(check)

    # Methods to clean the cache on the Check Method.
    def write(self, cursor, user, ids, vals, context=None):
        res = super(ModelAccess, self).write(cursor, user, ids, vals,
                context=context)
        self.check()
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(ModelAccess, self).create(cursor, user, vals,
                context=context)
        self.check()
        return res

    def unlink(self, cursor, user, ids, context=None):
        res = super(ModelAccess, self).unlink(cursor, user, ids,
                context=context)
        self.check()
        return res

ModelAccess()


class ModelData(OSV):
    "Model data"
    _name = 'ir.model.data'
    _description = __doc__
    _columns = {
        'name': fields.char('XML Identifier', required=True, size=64),
        'model': fields.char('Model', required=True, size=64),
        'module': fields.char('Module', required=True, size=64),
        'res_id': fields.integer('Resource ID'),
        'noupdate': fields.boolean('Non Updatable'),
        'date_update': fields.datetime('Update Date'),
        'date_init': fields.datetime('Init Date')
    }
    _defaults = {
        'date_init': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'date_update': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'noupdate': lambda *a: False
    }

    def __init__(self, pool):
        OSV.__init__(self, pool)
        self.loads = {}
        self.doinit = True
        self.unlink_mark = {}

    def _get_id(self, cursor, user, module, xml_id):
        ids = self.search(cursor, user, [
            ('module', '=', module),
            ('name', '=', xml_id),
            ])
        assert len(ids)==1, '%d reference(s) to %s. ' \
                'You should have only one !' % (len(ids),xml_id)
        return ids[0]

    _get_id = Cache()(_get_id)

    def _update_dummy(self, cursor, user, model, module, xml_id=False):
        if not xml_id:
            return False
        try:
            obj_id = self.read(cursor, user, self._get_id(cursor, user, module,
                xml_id), ['res_id'])['res_id']
            self.loads[(module, xml_id)] = (model, obj_id)
        except:
            obj_id = False
        return obj_id

    def _update(self, cursor, user, model, module, values, xml_id='',
            noupdate=False, mode='init', res_id=False):
        model_obj = self.pool.get(model)
        if xml_id and ('.' in xml_id):
            assert len(xml_id.split('.')) == 2, '"%s" contains too many dots. '\
                    'XML ids should not contain dots ! ' \
                    'These are used to refer to other modules data, ' \
                    'as in module.reference_id' % (xml_id)
            module, xml_id = xml_id.split('.')
        if (not xml_id) and (not self.doinit):
            return False
        action_id = False
        if xml_id:
            cursor.execute('SELECT id, res_id FROM ir_model_data ' \
                    'WHERE module = %s AND name = %s', (module,xml_id))
            results = cursor.fetchall()
            for action_id2, res_id2 in results:
                cursor.execute('SELECT id ' \
                        'FROM ' + self.pool.get(model)._table + ' ' \
                        'WHERE id = %d', (res_id2,))
                result3 = cursor.fetchone()
                if not result3:
                    cursor.execute('DELETE FROM ir_model_data ' \
                            'WHERE id = %d', (action_id2,))
                else:
                    res_id, action_id = res_id2, action_id2

        if action_id and res_id:
            model_obj.write(cursor, user, [res_id], values)
            self.write(cursor, user, [action_id], {
                'date_update': time.strftime('%Y-%m-%d %H:%M:%S'),
                })
        elif res_id:
            model_obj.write(cursor, user, [res_id], values)
            if xml_id:
                self.create(cursor, user, {
                    'name': xml_id,
                    'model': model,
                    'module':module,
                    'res_id':res_id,
                    'noupdate': noupdate,
                    })
                if model_obj._inherits:
                    for table in model_obj._inherits:
                        inherit_id = model_obj.browse(cursor, user,
                                res_id)[model_obj._inherits[table]]
                        self.create(cursor, user, {
                            'name': xml_id + '_' + table.replace('.', '_'),
                            'model': table,
                            'module': module,
                            'res_id': inherit_id,
                            'noupdate': noupdate,
                            })
        else:
            if mode == 'init' or (mode == 'update' and xml_id):
                res_id = model_obj.create(cursor, user, values)
                if xml_id:
                    self.create(cursor, user, {
                        'name': xml_id,
                        'model': model,
                        'module': module,
                        'res_id': res_id,
                        'noupdate': noupdate
                        })
                    if model_obj._inherits:
                        for table in model_obj._inherits:
                            inherit_id = model_obj.browse(cursor, user,
                                    res_id)[model_obj._inherits[table]]
                            self.create(cursor, user, {
                                'name': xml_id + '_' + table.replace('.', '_'),
                                'model': table,
                                'module': module,
                                'res_id': inherit_id,
                                'noupdate': noupdate,
                                })
        if xml_id:
            if res_id:
                self.loads[(module, xml_id)] = (model, res_id)
        return res_id

    def _unlink(self, cursor, user, model, ids, direct=False):
        #self.pool.get(model).unlink(cursor, user, ids)
        for obj_id in ids:
            self.unlink_mark[(model, obj_id)]=False
            cursor.execute('DELETE FROM ir_model_data ' \
                    'WHERE res_id = %d AND model = %s', (obj_id, model))
        return True

    def ir_set(self, cursor, user, key, key2, name, models, value,
            replace=True, isobject=False, meta=None, xml_id=False):
        obj = self.pool.get('ir.values')
        if type(models[0])==type([]) or type(models[0])==type(()):
            model, res_id = models[0]
        else:
            res_id = None
            model = models[0]

        if res_id:
            where = ' AND res_id = %d' % (res_id,)
        else:
            where = ' AND (res_id IS NULL)'

        if key2:
            where += ' AND key2 = \'%s\'' % (key2,)
        else:
            where += ' AND (key2 IS NULL)'

        cursor.execute('SELECT * FROM ir_values ' \
                'WHERE model = %s AND key = %s AND name = %s' + where,
                (model, key, name))
        res = cursor.fetchone()
        if not res:
            res = obj.set(cursor, user, key, key2, name, models, value,
                    replace, isobject, meta)
        elif xml_id:
            cursor.execute('UPDATE ir_values SET value = %s ' \
                    'WHERE model = %s AND key = %s AND name = %s' + where,
                    (value, model, key, name))
        return True

    def _process_end(self, cursor, user, modules):
        if not modules:
            return True
        module_str = ["'%s'" % m for m in modules]
        cursor.execute('SELECT id, name, model, res_id, module ' \
                'FROM ir_model_data ' \
                'WHERE module IN (' + ','.join(module_str) + ') ' \
                    'AND NOT noupdate')
        wkf_todo = []
        for (obj_id, name, model, res_id, module) in cursor.fetchall():
            if (module, name) not in self.loads:
                self.unlink_mark[(model, res_id)] = obj_id
                if model == 'workflow.activity':
                    cursor.execute('SELECT res_type, res_id ' \
                            'FROM wkf_instance ' \
                            'WHERE id IN (' \
                                'SELECT inst_id FROM wkf_workitem ' \
                                'WHERE act_id = %d)', (res_id,))
                    wkf_todo.extend(cursor.fetchall())
                    cursor.execute("UPDATE wkf_transition " \
                            "SET condition = 'True', role_id = NULL, " \
                                "signal = NULL, act_to = act_from, " \
                                "act_from = %d " \
                            "WHERE act_to = %d", (res_id, res_id))
                    cursor.execute("DELETE FROM wkf_transition " \
                            "WHERE act_to = %d", (res_id,))

        for model, obj_id in wkf_todo:
            wf_service = LocalService("workflow")
            wf_service.trg_write(user, model, obj_id, cursor)

        for (model, obj_id) in self.unlink_mark.keys():
            if self.pool.get(model):
                logger = Logger()
                logger.notify_channel('init', LOG_INFO,
                        'Deleting %s@%s' % (obj_id, model))
                try:
                    self.pool.get(model).unlink(cursor, user, [obj_id])
                    if self.unlink_mark[(model, obj_id)]:
                        self.unlink(cursor, user,
                                [self.unlink_mark[(model, obj_id)]])
                        cursor.execute('DELETE FROM ir_values WHERE value=%s',
                                (model + ',' + str(obj_id),))
                except:
                    logger.notify_channel('init', LOG_ERROR,
                            'Could not delete id: %d of model %s\t' \
                                    'There should be some relation ' \
                                    'that points to this resource\t' \
                                    'You should manually fix this ' \
                                    'and restart --update=module' % \
                                    (obj_id, model))
        return True

ModelData()
