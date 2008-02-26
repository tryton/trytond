"model"
from trytond.osv import fields, OSV
from trytond.netsvc import Logger, LocalService, LOG_ERROR, LOG_INFO, LOG_WARNING, LOG_DEBUG
from trytond.osv.orm import ExceptORM
from trytond.tools import Cache
import time


# Custom exception:

class Unhandled_field(Exception):
    """
    Raised when a field type is not supported by the update mechanism.
    """
    pass


class Model(OSV):
    "Model"
    _name = 'ir.model'
    _description = __doc__
    name = fields.Char('Model name', size=64, translate=True)
    model = fields.Char('Object name', size=64, required=True)
    info = fields.Text('Information')
    fields = fields.One2Many('ir.model.field', 'model', 'Fields',
       required=True)
    _defaults = {
        'name': lambda *a: 'No Name',
    }

Model()

class ModelField(OSV):
    "Model field"
    _name = 'ir.model.field'
    _description = __doc__
    name = fields.Char('Name', size=64)
    relation = fields.Char('Model Relation', size=64)
    model = fields.Many2One('ir.model', 'Model', required=True,
       select=True, ondelete='cascade')
    field_description = fields.Char('Field Description', size=256,
       translate=True)
    ttype = fields.Char('Field Type', size=64)
    relate = fields.Boolean('Click and Relate')
    groups = fields.Many2Many('res.group', 'ir_model_field_group_rel',
       'field_id', 'group_id', 'Groups')
    group_name = fields.Char('Group Name', size=128)
    view_load = fields.Boolean('View Auto-Load')
    help = fields.Text('Help', translate=True)
    _defaults = {
        'relate': lambda *a: 0,
        'view_load': lambda *a: 0,
        'name': lambda *a: 'No Name',
        'field_description': lambda *a: 'No description available',
    }
    _order = "id"

ModelField()


class ModelAccess(OSV):
    "Model access"
    _name = 'ir.model.access'
    _description = __doc__
    _rec_name = 'model'
    model = fields.Many2One('ir.model', 'Model', required=True)
    group = fields.Many2One('res.group', 'Group')
    perm_read = fields.Boolean('Read Access')
    perm_write = fields.Boolean('Write Access')
    perm_create = fields.Boolean('Create Access')
    perm_unlink = fields.Boolean('Delete Permission')
    description = fields.Text('Description')
    _sql_constraints = [
        ('model_group_uniq', 'UNIQUE("model", "group")',
            'Only on record by model and group is allowed!'),
    ]

    def check(self, cursor, user, model_name, mode='read',
            raise_exception=True):
        assert mode in ['read', 'write', 'create', 'unlink'], \
                'Invalid access mode for security'
        if user == 0:
            return True
        cursor.execute('SELECT MAX(CASE WHEN perm_'+mode+' THEN 1 else 0 END) '
            'FROM ir_model_access a '
                'JOIN ir_model m '
                    'ON (a.model = m.id) '
                'JOIN res_group_user_rel gu '
                    'ON (gu.gid = a.group) '
            'WHERE m.model = %s AND gu.uid = %s', (model_name, user,))
        row = cursor.fetchall()
        if row[0][0] == None:
            cursor.execute('SELECT ' \
                        'MAX(CASE WHEN perm_' + mode + ' THEN 1 else 0 END) ' \
                    'FROM ir_model_access a ' \
                    'JOIN ir_model m ' \
                        'ON (a.model = m.id) ' \
                    'WHERE a.group IS NULL AND m.model = %s', (model_name,))
            row = cursor.fetchall()
            if row[0][0] == None:
                return True

        if not row[0][0]:
            if raise_exception:
                if mode == 'read':
                    raise ExceptORM('AccessError',
                            'You can not read this document! (%s)' \
                                    % model_name)
                elif mode == 'write':
                    raise ExceptORM('AccessError',
                            'You can not write in this document! (%s)' \
                                    % model_name)
                elif mode == 'create':
                    raise ExceptORM('AccessError',
                            'You can not create this kind of document! (%s)' \
                                    % model_name)
                elif mode == 'unlink':
                    raise ExceptORM('AccessError',
                            'You can not delete this document! (%s)' \
                                    % model_name)
                raise ExceptORM('AccessError',
                        'You do not have access to this document! (%s)' \
                                % model_name)
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
    fs_id = fields.Char('Identifier on File System', required=True,
       size=64, help="The id of the record as known on the file system.")
    model = fields.Char('Model', required=True, size=64)
    module = fields.Char('Module', required=True, size=64)
    db_id = fields.Integer('Resource ID',
       help="The id of the record in the database.")
    date_update = fields.DateTime('Update Date')
    date_init = fields.DateTime('Init Date')
    values = fields.Text('Values')
    _defaults = {
        'date_init': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    _sql_constraints = [
        ('fs_id_module_uniq', 'UNIQUE("fs_id", "module")',
            'The couple (fs_id, module) must be unique!'),
    ]

    def __init__(self, pool):
        super(ModelData, self).__init__(pool)
        if pool:
            self.fs2db = None
            self.fs2values = None


    def populate_fs2db(self, cursor, user):
        """Fetch all the db_id, model tuple in the table in one shot
        (if necessary). This table is kept as a cache for the future
        conversions between fs_id abd db_id"""

        if not self.fs2db: self.fs2db = {}
        if cursor.dbname not in self.fs2db:
            module_data_ids = self.search(cursor, user,[])
            self.fs2db[cursor.dbname] = dict([
                ((x.fs_id, x.module),
                 (x.db_id, x.model, x.id)) for x in \
                self.browse(cursor, user, module_data_ids)])

    def populate_fs2values(self, cursor, user):
        """Fetch all the table in one shot (if necessary). When a
        record is imported ny import_record, the corresponding item in
        fs2values is removed. When post_import is called, the items
        remaining in fs2values are the one that were in the model_data
        table but not in the fs, so they are removed."""
        # Improvement: store the fiedls names and a hash of the values
        # instead of all the values.
        if not self.fs2values: self.fs2values = {}
        if cursor.dbname not in self.fs2values:
            module_data_ids = self.search(cursor, user,[])
            self.fs2values[cursor.dbname] = dict([
                ((x.fs_id, x.module),
                 x.values) for x in \
                self.browse(cursor, user, module_data_ids)])

    def get_id(self, cursor, user, module, fs_id):

        # Pre-Fetch all the data at once
        self.populate_fs2db(cursor, user)

        # return only the db_id
        if (fs_id, module) in self.fs2db[cursor.dbname]:
            return self.fs2db[cursor.dbname][(fs_id, module)][0]
        else:
            raise Exception("Reference to %s not found"%\
                            ".".join([module,fs_id]))

    @staticmethod
    def _clean_value(key, browse_record, object_ref):
        """
        Take a field name, a browse_record, and a reference to the
        corresponding object.  Return a raw value has it must look on the
        db.
        """

        # search the field type in the object or in a parent
        if key in object_ref._columns:
            field_type = object_ref._columns[key]._type
        else:
            field_type = object_ref._inherit_fields[key][2]._type

        # handle the value regarding to the type
        if field_type == 'many2one':
            return browse_record[key] and browse_record[key].id or False
        elif field_type in ['one2one', 'one2many', "many2many"]:
            raise Unhandled_field()
        else:
            return browse_record[key]


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
        self.populate_fs2values(cursor, user)

        object_ref = self.pool.get(model)

        if (fs_id, module) in self.fs2db[cursor.dbname]:
            # this record is already in the db:
            db_id, db_model, mdata_id = \
                   self.fs2db[cursor.dbname][(fs_id, module)]
            old_values = self.fs2values[cursor.dbname][(fs_id, module)]
            if old_values == None:
                old_values = {}
            else:
                old_values = eval(old_values)


            # Check if values for this record has been modified in the
            # db, if not it's ok to overwrite them.
            if model != db_model:
                raise Exception("This record try to overwrite"
                "data with the wrong model: %s (module: %s)"% (fs_id, module))

            #Re-create object if it was deleted
            if not object_ref.search(cursor, user, [('id', '=', db_id)]):
                db_id = object_ref.create(cursor, user, values,
                        context={'module': module})
                data_id = self.search(cursor, user, [
                    ('fs_id', '=', fs_id),
                    ('module', '=', module),
                    ], limit=1)[0]
                self.write(cursor, user, data_id, {
                    'db_id': db_id,
                    })
                self.fs2db[cursor.dbname][(fs_id, module)] = \
                        (db_id, db_model, mdata_id)

            db_values = object_ref.browse(cursor, user, db_id)

            to_update = {}
            for key in values:

                try:
                    db_field = ModelData._clean_value(key, db_values,
                            object_ref)
                except Unhandled_field:
                    logger = Logger()
                    logger.notify_channel('init', LOG_WARNING,
                        'Field %s on %s : integrity not tested.'%(key, model))
                    to_update[key] = values[key]
                    continue

                # if the fs value is the same has in the db, whe ignore it
                if db_field == values[key]:
                    continue

                # we cannot update a field if it was changed by a user
                if key not in  old_values:
                    default_value = object_ref._defaults.get(
                        key, lambda *a:None)(cursor, user)
                    if db_field != default_value:
                        logger = Logger()
                        logger.notify_channel('init', LOG_WARNING,
                            "Field %s of %s@%s not updated (id: %s), because "\
                            "it has changed since the last update"% \
                            (key, db_id, model, fs_id))
                        continue

                elif (old_values[key] and db_field) and \
                         old_values[key] != db_field:
                    logger = Logger()
                    logger.notify_channel('init', LOG_WARNING,
                        "Field %s of %s@%s not updated (id: %s), because "\
                        "it has changed since the last update."%\
                        (key, db_id, model, fs_id))
                    continue

                # so, the field in the fs and in the db are different,
                # and no user changed the value in the db:
                to_update[key] = values[key]

            # if there is values to update:
            if to_update:
                # write the values in the db:
                object_ref.write(cursor, user, db_id, to_update)
                # re-read it: this ensure that we store the real value
                # in the model_data table:
                db_val = object_ref.browse(cursor, user, db_id)
                for key in to_update:
                    try:
                        values[key] = ModelData._clean_value(
                            key, db_val, object_ref)
                    except Unhandled_field:
                        continue

            if values != old_values:
                self.write(cursor, user, mdata_id, {
                    'fs_id': fs_id,
                    'model': model,
                    'module': module,
                    'db_id': db_id,
                    'values': str(values),
                    'date_update': time.strftime('%Y-%m-%d %H:%M:%S'),
                    })

            # Remove this record from the value list. This means that
            # the corresponding record have been found.
            self.fs2values[cursor.dbname][(fs_id, module)] = None
        else:
            # this record is new, create it in the db:
            db_id = object_ref.create(cursor, user, values,
                    context={'module': module})
            # re-read it: this ensure that we store the real value
            # in the model_data table:
            db_val = object_ref.browse(cursor, user, db_id)
            for key in values:
                try:
                    values[key] = ModelData._clean_value(key, db_val,
                            object_ref)
                except Unhandled_field:
                    continue

            mdata_id = self.create(cursor, user, {
                'fs_id': fs_id,
                'model': model,
                'module': module,
                'db_id': db_id,
                'values': str(values),
                })
            # update fs2db:
            self.fs2db[cursor.dbname][(fs_id, module)]= (db_id, model,
                    mdata_id)
            self.fs2values[cursor.dbname][(fs_id, module)] = None

    def post_import(self, cursor, user, modules):
        # Test because of a wrong extra call. See todo at the end of
        # load_module_graph in module.py
        # Globaly this function is a bit dirty.
        if not (self.fs2values and self.fs2values.get(cursor.dbname)):
            return True

        wf_service = LocalService("workflow")

        mdata_unlink = []

        for (fs_id, module) in self.fs2values[cursor.dbname]:
            if self.fs2values[cursor.dbname][(fs_id, module)] == None:
                continue
            if module in modules:
                (db_id, model, mdata_id) = self.fs2db[cursor.dbname]\
                        [(fs_id, module)]

                if model == 'workflow.activity':
                    cursor.execute('SELECT res_type, db_id ' \
                            'FROM wkf_instance ' \
                            'WHERE id IN (' \
                                'SELECT instance FROM wkf_workitem ' \
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
                    mdata_unlink.append(mdata_id)
                except:
                    raise
                    logger.notify_channel('init', LOG_ERROR,
                            'Could not delete id: %d of model %s\n' \
                                    'There should be some relation ' \
                                    'that points to this resource\n' \
                                    'You should manually fix this ' \
                                    'and restart --update=module' % \
                                    (db_id, model))

        if mdata_unlink:
            self.unlink(cursor, user, mdata_unlink)
        del self.fs2values[cursor.dbname]
        return True


ModelData()
