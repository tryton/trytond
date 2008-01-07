"model"
from trytond.osv import fields, OSV
from trytond.netsvc import Logger, LocalService, LOG_ERROR, LOG_INFO, LOG_WARNING
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
        'fs_id': fields.char('Identifier on File System', required=True,
            size=64, help="The id of the record as known on the file system."),
        'model': fields.char('Model', required=True, size=64),
        'module': fields.char('Module', required=True, size=64),
        'db_id': fields.integer('Resource ID',
            help="The id of the record in the database."),
        'date_update': fields.datetime('Update Date'),
        'date_init': fields.datetime('Init Date'),
        'values': fields.text('Values'),
    }
    _defaults = {
        'date_init': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def __init__(self, pool):
        OSV.__init__(self, pool)

        # fs2db contain the data of the table ir.model.data.  This
        # fs2db provide a mapping from the data in the fs to the data
        # in the db. This mean that this dict can become very big if a
        # lot of files are imported. (improvement store a hash instead of all the values).
        self.fs2db = None
        # imported_records keep tracks of all the records that have
        # been imported.
        self.imported_records = {}


    def populate_fs2db(self, cursor, user):
        """Fetch all the table in one shot (if necessary)."""
        if not self.fs2db: self.fs2db = {}
        if cursor.dbname not in self.fs2db:
            module_data_ids = self.search(cursor, user,[])
            self.fs2db[cursor.dbname] = dict([
                ((x.fs_id, x.module),
                 (x.db_id, x.model, x.values)) for x in \
                self.browse(cursor, user, module_data_ids)])

    def get_id(self, cursor, user, module, fs_id):

        # Pre-Fetch all the data at once
        self.populate_fs2db(cursor, user)

        # return only the db_id
        if (fs_id, module) in self.fs2db[cursor.dbname]:
            return self.fs2db[cursor.dbname][(fs_id, module)][0]
        else:
            raise Exception("Reference to %s not found"% ".".join([module,fs_id]))

    def import_record(self, cursor, user, model, module, values, fs_id):

        if not fs_id:
            raise Exception('import_record : Argument fs_id is mandatory')

        if '.' in fs_id:
            assert len(fs_id.split('.')) == 2, '"%s" contains too many dots. '\
                    'file system ids should contain ot most one dot ! ' \
                    'These are used to refer to other modules data, ' \
                    'as in module.reference_id' % (fs_id)

            module, fs_id = fs_id.split('.')

        self.populate_fs2db(cursor, user)

        # keep track of the lits of parsed records.
        if cursor.dbname in self.imported_records:
            self.imported_records[cursor.dbname].append((fs_id, module))
        else:
            self.imported_records[cursor.dbname]= [(fs_id, module)]

        if (fs_id, module) in self.fs2db[cursor.dbname]:
            # this record is already in the db:
            db_id, db_model, old_values = \
                   self.fs2db[cursor.dbname][(fs_id, module)]
            old_values = eval(old_values)

            # Check if this record has been modified in the db:
            if model != db_model:
                raise Exception("This record try to overwrite"
                "data with the wrong model.")
            object_ref = self.pool.get(model)
            db_values = object_ref.read(cursor, user, db_id, old_values.keys())

            modified = False
            for key in old_values:

                if object_ref._columns[key]._type == 'many2one':
                    db_field = db_values[key][0]
                elif object_ref._columns[key]._type in ['one2one', 'one2many', "many2many"]:
                    logger = Logger()
                    logger.notify_channel('init', LOG_WARNING,
                        'Field %s on %s : integrity not tested.'%(key, model))
                    continue
                else:
                    db_field = db_values[key]

                if old_values[key] != db_field:
                    modified = True
                    break

            if not modified:
                # Update the db with the values
                # TODO : check if this id exist for this model.

                self.pool.get(model).write(cursor, user, db_id, values)
                self.create(cursor, user, {
                    'fs_id': fs_id,
                    'model': model,
                    'module': module,
                    'db_id': db_id,
                    'values': str(values),
                    'date_update': time.strftime('%Y-%m-%d %H:%M:%S'),
                    })

                # Update fs2db:
                self.fs2db[cursor.dbname][(fs_id, module)]= (db_id, model, str(values))
            else:
                # We may not overwrite modified data:
                logger = Logger()
                logger.notify_channel('init', LOG_INFO,
                    'Record %s ignored, the corresponding data (%s@%s) '
                    'in the db has been modified' % (fs_id,db_id, model))

        else:
            # this record is new
            db_id = self.pool.get(model).create(cursor, user, values)
            self.create(cursor, user, {
                'fs_id': fs_id,
                'model': model,
                'module': module,
                'db_id': db_id,
                'values': str(values),
                })
            # update fs2db:
            self.fs2db[cursor.dbname][(fs_id, module)]= (db_id, model, str(values))

    def post_import(self, cursor, user, modules):

        # Test because of a wrong extra call see todo at the end of
        # load_module_graph in module.py
        # Globaly this function is a bit dirty.
        if not (self.fs2db and self.fs2db.get(cursor.dbname)):
            return True

        wf_service = LocalService("workflow")

        data_unlink = []

        for ((fs_id, module),(db_id, model, values)) in  \
                self.fs2db[cursor.dbname].items():

            if module in modules and \
                ((fs_id, module) not in self.imported_records[cursor.dbname]):

                if model == 'workflow.activity':
                    cursor.execute('SELECT res_type, db_id ' \
                            'FROM wkf_instance ' \
                            'WHERE id IN (' \
                                'SELECT inst_id FROM wkf_workitem ' \
                                'WHERE act_id = %d)', (db_id,))
                    wkf_todo.extend(cursor.fetchall())
                    cursor.execute("UPDATE wkf_transition " \
                            "SET condition = 'True', role_id = NULL, " \
                                "signal = NULL, act_to = act_from, " \
                                "act_from = %d " \
                            "WHERE act_to = %d", (db_id, db_id))
                    cursor.execute("DELETE FROM wkf_transition " \
                            "WHERE act_to = %d", (db_id,))

                    wf_service.trg_write(user, model, db_id, cursor)

                logger = Logger()
                logger.notify_channel('init', LOG_INFO,
                        'Deleting %s@%s' % (db_id, model))
                try:
                    self.pool.get(model).unlink(cursor, user, db_id)
                    data_unlink.append((fs_id, module))
                except:
                    logger.notify_channel('init', LOG_ERROR,
                            'Could not delete id: %d of model %s\t' \
                                    'There should be some relation ' \
                                    'that points to this resource\t' \
                                    'You should manually fix this ' \
                                    'and restart --update=module' % \
                                    (db_id, model))

        if data_unlink:
            cursor.execute("""
            DELETE FROM ir_model_data
            WHERE (fs_id, module) in (%s)
            """% ','.join(["('%s','%s')"%x for x in data_unlink]))

        del self.fs2db[cursor.dbname]
        del self.imported_records[cursor.dbname]

        return True



ModelData()
