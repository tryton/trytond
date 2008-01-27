# -*- coding: utf-8 -*-
from xml import dom
from xml.dom import minidom
from xml import xpath
from trytond.netsvc import Logger, LOG_ERROR, LOG_WARNING, LocalService
import fields
from trytond.tools import Cache
import md5

ID_MAX = 1000

def intersect(i, j):
    return [x for x in j if x in i]


class ExceptORM(Exception):

    def __init__(self, name, value):
        Exception.__init__(self)
        self.name = name
        self.value = value
        self.args = (name, value)

except_orm = ExceptORM


# TODO: execute an object method on BrowseRecordList
class BrowseRecordList(list):

    def __init__(self, lst, context=None):
        super(BrowseRecordList, self).__init__(lst)
        self.context = context

browse_record_list = BrowseRecordList


class BrowseRecord(object):

    def __init__(self, cursor, user, object_id, table, cache, context=None,
            list_class=None):
        '''
        table : the object (inherited from orm)
        context : a dictionnary with an optionnal context
        '''
        self._list_class = list_class or BrowseRecordList
        self._cursor = cursor
        self._user = user
        self._id = object_id
        self._table = table
        self._table_name = self._table._name
        self._context = context

        cache.setdefault(table._name, {})
        self._data = cache[table._name]
        if not object_id in self._data:
            self._data[object_id] = {'id': object_id}
        self._cache = cache

    def __getitem__(self, name):
        if name == 'id':
            return self._id
        if not self._data[self._id].has_key(name) and self._id:
            # build the list of fields we will fetch

            # fetch the definition of the field which was asked for
            if name in self._table._columns:
                col = self._table._columns[name]
            elif name in self._table._inherit_fields:
                col = self._table._inherit_fields[name][2]
            elif hasattr(self._table, name):
                return getattr(self._table, name)
            else:
                logger = Logger()
                logger.notify_channel('orm', LOG_ERROR,
                        "Programming error: field '%s' " \
                                "does not exist in object '%s'!" % \
                                (name, self._table._name))
                return False

            # if the field is a classic one or a many2one,
            # we'll fetch all classic and many2one fields
            if col._classic_write:
                # gen the list of "local" (ie not inherited)
                # fields which are classic or many2one
                ffields = [x for x in self._table._columns.items() \
                        if x[1]._classic_write]
                # gen the list of inherited fields
                inherits = [(x[0], x[1][2]) for x in \
                        self._table._inherit_fields.items()]
                # complete the field list with the inherited fields
                # which are classic or many2one
                ffields += [x for x in inherits if x[1]._classic_write]
            # otherwise we fetch only that field
            else:
                ffields = [(name, col)]
            ids = [x for x in self._data.keys() \
                    if not self._data[x].has_key(name) and x]
            # read the data
            datas = self._table.read(self._cursor, self._user, ids,
                    [x[0] for x in ffields], context=self._context,
                    load="_classic_write")

            # create browse records for 'remote' objects
            for data in datas:
                for i, j in ffields:
                    if j._type in ('many2one', 'one2one'):
                        obj = self._table.pool.get(j._obj)
                        if not j._classic_write and data[i]:
                            ids2 = data[i][0]
                        else:
                            ids2 = data[i]
                        data[i] = BrowseRecord(self._cursor, self._user,
                                ids2, obj, self._cache,
                                context=self._context,
                                list_class=self._list_class)
                    elif j._type in ('one2many', 'many2many') and len(data[i]):
                        data[i] = self._list_class([BrowseRecord(self._cursor,
                            self._user, x, self._table.pool.get(j._obj),
                            self._cache, context=self._context,
                            list_class=self._list_class) for x in data[i]],
                            self._context)
                self._data[data['id']].update(data)
        return self._data[self._id][name]

    def __getattr__(self, name):
        # TODO raise an AttributeError exception
        return self[name]

    def __contains__(self, name):
        return (name in self._table._columns) \
                or (name in self._table._inherit_fields) \
                or hasattr(self._table, name)

    def __hasattr__(self, name):
        return name in self

    def __int__(self):
        return self._id

    def __str__(self):
        return "BrowseRecord(%s, %d)" % (self._table_name, self._id)

    def __eq__(self, other):
        return (self._table_name, self._id) == (other._table_name, other._id)

    def __ne__(self, other):
        return (self._table_name, self._id) != (other._table_name, other._id)

    # we need to define __unicode__ even though we've already defined __str__
    # because we have overridden __getattr__
    def __unicode__(self):
        return unicode(str(self))

    def __hash__(self):
        return hash((self._table_name, self._id))

    def __nonzero__(self):
        return bool(self._id)

    __repr__ = __str__

browse_record = BrowseRecord

def get_pg_type(field):
    '''
    returns a tuple
    (type returned by postgres when the column was created,
    type expression to create the column)
    '''
    type_dict = {
            fields.boolean:'bool',
            fields.integer:'int4',
            fields.text:'text',
            fields.date:'date',
            fields.time:'time',
            fields.datetime:'timestamp',
            fields.binary:'bytea',
            fields.many2one:'int4',
            }

    if type_dict.has_key(type(field)):
        f_type = (type_dict[type(field)], type_dict[type(field)])
    elif isinstance(field, fields.float):
        if field.digits:
            f_type = ('numeric', 'NUMERIC(%d, %d)' % \
                    (field.digits[0],field.digits[1]))
        else:
            f_type = ('float8', 'DOUBLE PRECISION')
    elif isinstance(field, (fields.char, fields.reference)):
        f_type = ('varchar', 'VARCHAR(%d)' % (field.size,))
    elif isinstance(field, fields.selection):
        if isinstance(field.selection, list) \
                and isinstance(field.selection[0][0], (str, unicode)):
            f_size = reduce(lambda x, y: max(x, len(y[0])), field.selection,
                    field.size or 16)
        elif isinstance(field.selection, list) \
                and isinstance(field.selection[0][0], int):
            f_size = -1
        else:
            f_size = (hasattr(field,'size') and field.size) or 16

        if f_size == -1:
            f_type = ('int4', 'INTEGER')
        else:
            f_type = ('varchar', 'VARCHAR(%d)' % f_size)
    elif isinstance(field, fields.function) \
            and type_dict.has_key(eval('fields.' + (field._type))):
        ftype = eval('fields.' + (field._type))
        f_type = (type_dict[ftype], type_dict[ftype])
    elif isinstance(field, fields.function) and field._type == 'float':
        f_type = ('float8', 'DOUBLE PRECISION')
    else:
        logger = Logger()
        logger.notify_channel("init", LOG_WARNING,
                '%s type not supported!' % (type(field)))
        f_type = None
    return f_type


class ORM(object):
    """
    Object relationnal mapping to postgresql module
       . Hierarchical structure
       . Constraints consistency, validations
       . Object meta Data depends on its status
       . Optimised processing by complex query (multiple actions at once)
       . Default fields value
       . Permissions optimisation
       . Persistant object: DB postgresql
       . Datas conversions
       . Multi-level caching system
       . 2 different inheritancies
       . Fields:
            - classicals (varchar, integer, boolean, ...)
            - relations (one2many, many2one, many2many)
            - functions
    """
    _columns = {}
    _sql_constraints = []
    _constraints = []
    _defaults = {}
    _log_access = True
    _table = None
    _name = None
    _rec_name = 'name'
    _parent_name = 'parent_id'
    _date_name = 'date'
    _order = 'id'
    _inherits = {}
    _sequence = None
    _description = __doc__
    _protected = [
            'read',
            'write',
            'create',
            'default_get',
            'unlink',
            'fields_get',
            'fields_view_get',
            'search',
            'name_get',
            'name_search',
            'copy',
            'import_data',
            'search_count',
            ]
    _auto = True
    _obj = None
    _sql = ''
    _inherit_fields = []
    pool = None

    def _field_create(self, cursor):
        cursor.execute("SELECT id FROM ir_model WHERE model='%s'" % self._name)
        if not cursor.rowcount:
            # reference model in order to have a description
            # of its fonctionnality in custom_report
            cursor.execute("INSERT INTO ir_model " \
                    "(model, name, info) VALUES (%s, %s, %s)",
                    (self._name, self._description, self.__doc__))
        cursor.commit()

        for k in self._columns:
            field = self._columns[k]
            cursor.execute("SELECT id, relate FROM ir_model_fields " \
                    "WHERE model = %s AND name = %s", (self._name, k))
            if not cursor.rowcount:
                cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                        (self._name,))
                (model_id,) = cursor.fetchone()
                cursor.execute("INSERT INTO ir_model_fields " \
                        "(model_id, model, name, field_description, ttype, " \
                            "relation, group_name, view_load) " \
                        "VALUES (%d, %s, %s, %s, %s, %s, %s, %s)",
                        (model_id, self._name, k,
                            field.string.replace("'", " "), field._type,
                            field._obj or 'NULL', field.group_name or '',
                            (field.view_load and 'True') or 'False'))
        cursor.commit()

    def auto_init(self, cursor):
        self.init(cursor)
        self._auto_init(cursor)

    def init(self, cursor):
        pass

    def _auto_init(self, cursor):
        logger = Logger()
        create = False
        self._field_create(cursor)
        if self._auto:
            cursor.execute("SELECT relname FROM pg_class " \
                    "WHERE relkind in ('r', 'v') AND relname = %s",
                    (self._table,))
            if not cursor.rowcount:
                cursor.execute("CREATE TABLE \"%s\" " \
                        "(id SERIAL NOT NULL, " \
                            "PRIMARY KEY(id)) WITH OIDS" % self._table)
                create = True
            cursor.commit()
            if self._log_access:
                logs = {
                    'create_uid': 'INTEGER REFERENCES res_user ' \
                            'ON DELETE SET NULL',
                    'create_date': 'TIMESTAMP',
                    'write_uid': 'INTEGER REFERENCES res_user ' \
                            'ON DELETE SET NULL',
                    'write_date': 'TIMESTAMP'
                }
                for k in logs:
                    cursor.execute("SELECT c.relname " \
                        "FROM pg_class c, pg_attribute a " \
                        "WHERE c.relname = %s " \
                            "AND a.attname = %s " \
                            "AND c.oid = a.attrelid",
                            (self._table, k))
                    if not cursor.rowcount:
                        cursor.execute("ALTER TABLE \"%s\" " \
                                "ADD COLUMN \"%s\" %s" %
                            (self._table, k, logs[k]))
                        cursor.commit()

            # iterate on the database columns to drop the NOT NULL constraints
            # of fields which were required but have been removed
            cursor.execute(
                "SELECT a.attname, a.attnotnull "\
                "FROM pg_class c, pg_attribute a "\
                "WHERE c.oid=a.attrelid AND c.relname='%s'" % self._table)
            db_columns = cursor.dictfetchall()
            for column in db_columns:
                if column['attname'] not in (
                        'id',
                        'oid',
                        'tableoid',
                        'ctid',
                        'xmin',
                        'xmax',
                        'cmin',
                        'cmax',
                        ):
                    if column['attnotnull'] \
                            and (column['attname'] not in self._columns):
                        cursor.execute("ALTER TABLE \"%s\" " \
                                "ALTER COLUMN \"%s\" DROP NOT NULL" % \
                                (self._table, column['attname']))

            # iterate on the "object columns"
            for k in self._columns:
                if k in (
                        'id',
                        'write_uid',
                        'write_date',
                        'create_uid',
                        'create_date',
                        ):
                    continue

                field = self._columns[k]
                if isinstance(field, fields.one2many):
                    cursor.execute("SELECT relname FROM pg_class " \
                            "WHERE relkind = 'r' AND relname = %s",
                            (field._obj,))
                    if cursor.fetchone():
                        cursor.execute("SELECT count(*) as c " \
                                "FROM pg_class c, pg_attribute a " \
                                "WHERE c.relname = %s " \
                                    "AND a.attname = %s " \
                                    "AND c.oid = a.attrelid",
                                    (field._obj, field._fields_id))
                        (res,) = cursor.fetchone()
                        if not res:
                            cursor.execute("ALTER TABLE \"%s\" " \
                                    "ADD FOREIGN KEY (%s) " \
                                    "REFERENCES \"%s\" ON DELETE SET NULL" % \
                                    (self._obj, field._fields_id, field._table))
                elif isinstance(field, fields.many2many):
                    cursor.execute("SELECT relname FROM pg_class " \
                            "WHERE relkind in ('r','v') AND relname=%s",
                            (field._rel,))
                    if not cursor.dictfetchall():
                        #FIXME: Remove this try/except
                        try:
                            ref = self.pool.get(field._obj)._table
                        except AttributeError:
                            ref = field._obj.replace('.','_')
                        cursor.execute("CREATE TABLE \"%s\" " \
                                "(\"%s\" INTEGER NOT NULL REFERENCES \"%s\" " \
                                    "ON DELETE CASCADE, " \
                                "\"%s\" INTEGER NOT NULL REFERENCES \"%s\" " \
                                    "ON DELETE CASCADE) WITH OIDS" % \
                                    (field._rel, field._id1, self._table,
                                        field._id2, ref))
                        cursor.execute("CREATE INDEX \"%s_%s_index\" " \
                                "ON \"%s\" (\"%s\")" % \
                                (field._rel, field._id1, field._rel,
                                    field._id1))
                        cursor.execute("CREATE INDEX \"%s_%s_index\" " \
                                "ON \"%s\" (\"%s\")" % \
                                (field._rel, field._id2, field._rel,
                                    field._id2))
                        cursor.commit()
                else:
                    cursor.execute("SELECT c.relname, a.attname, a.attlen, " \
                                "a.atttypmod, a.attnotnull, a.atthasdef, " \
                                "t.typname, " \
                                    "CASE WHEN a.attlen = -1 " \
                                    "THEN a.atttypmod-4 " \
                                    "ELSE a.attlen END as size " \
                            "FROM pg_class c, pg_attribute a, pg_type t " \
                            "WHERE c.relname = %s " \
                                "AND a.attname = %s " \
                                "AND c.oid = a.attrelid " \
                                "AND a.atttypid = t.oid",
                                (self._table, k))
                    res = cursor.dictfetchall()
                    if not res:
                        if not isinstance(field, fields.function):
                            # add the missing field
                            cursor.execute("ALTER TABLE \"%s\" " \
                                    "ADD COLUMN \"%s\" %s" % \
                                    (self._table, k, get_pg_type(field)[1]))
                            # initialize it
                            if not create and k in self._defaults:
                                default = self._defaults[k](self, cursor, 1, {})
                                if not default:
                                    cursor.execute("UPDATE \"%s\" " \
                                            "SET \"%s\" = NULL" % \
                                            (self._table, k))
                                else:
                                    cursor.execute("UPDATE \"%s\" " \
                                            "SET \"%s\" = '%s'" % \
                                            (self._table, k, default))
                            # and add constraints if needed
                            if isinstance(field, fields.many2one):
                                #FIXME: Remove this try/except
                                try:
                                    ref = self.pool.get(field._obj)._table
                                except AttributeError:
                                    ref = field._obj.replace('.','_')
                                # ir_actions is inherited so foreign
                                # key doesn't work on it
                                if ref != 'ir_actions':
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                            "ADD FOREIGN KEY (\"%s\") " \
                                                "REFERENCES \"%s\" " \
                                                "ON DELETE %s" % \
                                            (self._table, k, ref,
                                                field.ondelete))
                            if field.select:
                                cursor.execute("CREATE INDEX \"%s_%s_index\" " \
                                        "ON \"%s\" (\"%s\")" % \
                                        (self._table, k, self._table, k))
                            if field.required:
                                try:
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                            "ALTER COLUMN \"%s\" " \
                                                "SET NOT NULL" % \
                                                (self._table, k))
                                except:
                                    logger.notify_channel('init',
                                            LOG_WARNING,
                                            'Unable to set column %s ' \
                                                    'of table %s not null !\n'\
                                            'Try to re-run: ' \
                                        'tinyerp-server.py --update=module\n' \
                'If it doesn\'t work, update records and execute manually:\n' \
                'ALTER TABLE %s ALTER COLUMN %s SET NOT NULL' % \
                                        (k, self._table, self._table, k))
                            cursor.commit()
                    elif len(res)==1:
                        f_pg_def = res[0]
                        f_pg_type = f_pg_def['typname']
                        f_pg_size = f_pg_def['size']
                        f_pg_notnull = f_pg_def['attnotnull']
                        if isinstance(field, fields.function):
                            logger.notify_channel('init', LOG_WARNING,
                                    'column %s (%s) in table %s was converted '\
                                            'to a function !\n' \
                        'You should remove this column from your database.' % \
                                (k, field.string, self._table))
                            f_obj_type = None
                        else:
                            f_obj_type = get_pg_type(field) \
                                    and get_pg_type(field)[0]
                        if f_obj_type:
                            if f_pg_type != f_obj_type:
                                logger.notify_channel('init',
                                        LOG_WARNING,
                                        "column '%s' in table '%s' has " \
                                        "changed type (DB = %s, def = %s) !" % \
                                        (k, self._table, f_pg_type,
                                            field._type))
                            if f_pg_type == 'varchar' \
                                    and field._type == 'char' \
                                    and f_pg_size != field.size:
                                # columns with the name 'type' cannot be changed
                                # for an unknown reason?!
                                if k != 'type':
                                    if f_pg_size > field.size:
                                        logger.notify_channel('init',
                                                LOG_WARNING,
                                                "column '%s' in table '%s' " \
        "has changed size (DB = %d, def = %d), strings will be truncated !" % \
                                        (k, self._table, f_pg_size, field.size))
#TODO: check si y a des donnees qui vont poser probleme (select char_length())
#TODO: issue a log message even if f_pg_size < field.size
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                            "RENAME COLUMN \"%s\" " \
                                            "TO temp_change_size" % \
                                            (self._table,k))
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                            "ADD COLUMN \"%s\" VARCHAR(%d)" % \
                                            (self._table,k,field.size))
                                    cursor.execute("UPDATE \"%s\" " \
                                "SET \"%s\" = temp_change_size::VARCHAR(%d)" % \
                                        (self._table, k, field.size))
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                            "DROP COLUMN temp_change_size" % \
                                            (self._table,))
                                    cursor.commit()
                            # if the field is required
                            # and hasn't got a NOT NULL constraint
                            if field.required and f_pg_notnull == 0:
                                # set the field to the default value if any
                                if self._defaults.has_key(k):
                                    default = self._defaults[k](self, cursor,
                                            1, {})
                                    if not (default is False):
                                        cursor.execute("UPDATE \"%s\" " \
                                        "SET \"%s\" = '%s' WHERE %s is NULL" % \
                                            (self._table, k, default, k))
                                        cursor.commit()
                                # add the NOT NULL constraint
                                try:
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                        "ALTER COLUMN \"%s\" SET NOT NULL" % \
                                        (self._table, k))
                                    cursor.commit()
                                except:
                                    logger.notify_channel('init',
                                            LOG_WARNING,
                                            'unable to set ' \
                    'a NOT NULL constraint on column %s of the %s table !\n' \
'If you want to have it, you should update the records and execute manually:\n'\
                            'ALTER TABLE %s ALTER COLUMN %s SET NOT NULL' % \
                                        (k, self._table, self._table, k))
                                cursor.commit()
                            elif not field.required and f_pg_notnull == 1:
                                cursor.execute("ALTER TABLE \"%s\" " \
                                        "ALTER COLUMN \"%s\" DROP NOT NULL" % \
                                        (self._table, k))
                                cursor.commit()
                            cursor.execute("SELECT indexname FROM pg_indexes " \
                    "WHERE indexname = '%s_%s_index' AND tablename = '%s'" % \
                                    (self._table, k, self._table))
                            res = cursor.dictfetchall()
                            if not res and field.select:
                                cursor.execute("CREATE INDEX \"%s_%s_index\" " \
                                        "ON \"%s\" (\"%s\")" % \
                                        (self._table, k, self._table, k))
                                cursor.commit()
                            if res and not field.select:
                                cursor.execute("DROP INDEX \"%s_%s_index\"" % \
                                        (self._table, k))
                                cursor.commit()
                            if isinstance(field, fields.many2one):
                                ref_obj = self.pool.get(field._obj)
                                if ref_obj:
                                    ref = ref_obj._table
                                else:
                                    ref = field._obj.replace('.', '_')
                                if ref != 'ir_actions':
                                    cursor.execute('SELECT confdeltype, conname ' \
                                            'FROM pg_constraint as con, ' \
                                                'pg_class as cl1, pg_class as cl2, ' \
                                            'pg_attribute as att1, pg_attribute as att2 ' \
                                            'WHERE con.conrelid = cl1.oid ' \
                                                'AND cl1.relname = %s ' \
                                                'AND con.confrelid = cl2.oid ' \
                                                'AND cl2.relname = %s ' \
                                                'AND array_lower(con.conkey, 1) = 1 ' \
                                                'AND con.conkey[1] = att1.attnum ' \
                                                'AND att1.attrelid = cl1.oid ' \
                                                'AND att1.attname = %s ' \
                                                'AND array_lower(con.confkey, 1) = 1 ' \
                                                'AND con.confkey[1] = att2.attnum ' \
                                                'AND att2.attrelid = cl2.oid ' \
                                                'AND att2.attname = %s ' \
                                                'AND con.contype = \'f\'',
                                            (self._table, ref, k, 'id'))
                                    res = cursor.dictfetchall()
                                    if res:
                                        confdeltype = {
                                                'RESTRICT': 'r',
                                                'NO ACTION': 'a',
                                                'CASCADE': 'c',
                                                'SET NULL': 'n',
                                                'SET DEFAULT': 'd',
                                        }
                                        if res[0]['confdeltype'] != \
                                                confdeltype.get(
                                                        field.ondelete.upper(),
                                                        'a'):
                                            cursor.execute('ALTER TABLE "' + \
                                                    self._table + '" ' \
                                                    'DROP CONSTRAINT "' + \
                                                    res[0]['conname'] + '"')
                                            cursor.execute('ALTER TABLE "' + \
                                                    self._table + '" ' \
                                                    'ADD FOREIGN KEY ' \
                                                    '("' + k + '") ' \
                                                    'REFERENCES "' + ref + \
                                                    '" ON DELETE ' + field.ondelete)
                                            cursor.commit()
                    else:
                        # TODO add error message
                        logger.notify_channel('init', LOG_ERROR, '')
        else:
            cursor.execute("SELECT relname FROM pg_class " \
                    "WHERE relkind in ('r', 'v') AND relname = %s",
                    (self._table,))
            create = not bool(cursor.fetchone())

        for (key, con, _) in self._sql_constraints:
            cursor.execute("SELECT conname FROM pg_constraint " \
                    "WHERE conname = %s", ((self._table + '_' + key),))
            if not cursor.dictfetchall():
                try:
                    cursor.execute('ALTER TABLE \"%s\" ' \
                            'ADD CONSTRAINT \"%s_%s\" %s' % \
                            (self._table, self._table, key, con,))
                    cursor.commit()
                except:
                    logger.notify_channel('init', LOG_WARNING,
                            'unable to add \'%s\' constraint on table %s !\n' \
'If you want to have it, you should update the records and execute manually:\n'\
                            'ALTER table %s ADD CONSTRAINT %s_%s %s' % \
                        (con, self._table, self._table, self._table,key, con,))

        if create:
            if hasattr(self, "_sql"):
                for line in self._sql.split(';'):
                    line2 = line.replace('\n', '').strip()
                    if line2:
                        cursor.execute(line2)
                        cursor.commit()

    def __init__(self):
        if not self._table:
            self._table = self._name.replace('.', '_')
        if not self._description:
            self._description = self._name
        for (key, ham, msg) in self._sql_constraints:
            self.pool._sql_error[self._table + '_' + key] = msg

        self._inherits_reload()
        if not self._sequence:
            self._sequence = self._table+'_id_seq'
        for k in self._defaults:
            assert (k in self._columns) or (k in self._inherit_fields), \
            'Default function defined in %s but field %s does not exist!' % \
                (self._name, k,)
        # FIXME: does not work at all
#        if self._log_access:
#            self._columns.update({
#                'create_uid': fields.many2one('res.user', 'Creation user',
#                       required=True, readonly=True),
#                'create_date': fields.datetime('Creation date', required=True,
#                       readonly=True),
#                'write_uid': fields.many2one('res.user',
#                       'Last modification by', readonly=True),
#                'write_date': fields.datetime('Last modification date',
#                       readonly=True),
#                })
#             self._defaults.update({
#                 'create_uid': lambda self, cursor, user, context: user,
#                 'create_date': lambda *a: time.strftime("%Y-%m-%d %H:%M:%S")
#                 })

    def _inherits_reload_src(self):
        "Update objects that uses this one to update their _inherits fields"
        for obj in self.pool.object_name_pool.values():
            if self._name in obj._inherits:
                obj._inherits_reload()

    def _inherits_reload(self):
        res = {}
        for table in self._inherits:
            res.update(self.pool.get(table)._inherit_fields)
            for col in self.pool.get(table)._columns.keys():
                res[col] = (table, self._inherits[table],
                        self.pool.get(table)._columns[col])
            for col in self.pool.get(table)._inherit_fields.keys():
                res[col] = (table, self._inherits[table],
                        self.pool.get(table)._inherit_fields[col][2])
        self._inherit_fields = res
        self._inherits_reload_src()

    def browse(self, cursor, user, select, context=None, list_class=None):
        list_class = list_class or BrowseRecordList
        cache = {}
        # need to accepts ints and longs because ids coming from a method
        # launched by button in the interface have a type long...
        if isinstance(select, (int, long)):
            return BrowseRecord(cursor, user, select, self, cache,
                    context=context, list_class=list_class)
        return list_class([BrowseRecord(cursor, user, x, self, cache,
            context=context, list_class=list_class) for x in select],
            context)

    def __export_row(self, cursor, user, row, fields_names, context=None):
        lines = []
        data = ['' for x in range(len(fields_names))]
        done = []
        for fpos in range(len(fields_names)):
            field = fields_names[fpos]
            if field:
                row2 = row
                i = 0
                while i < len(field):
                    row2 = row2[field[i]]
                    if not row2:
                        break
                    if isinstance(row2, (BrowseRecordList, list)):
                        first = True
                        fields2 = [(x[:i+1]==field[:i+1] and x[i+1:]) \
                                or [] for x in fields_names]
                        if fields2 in done:
                            break
                        done.append(fields2)
                        for row2 in row2:
                            lines2 = self.__export_row(cursor, user, row2,
                                    fields2, context)
                            if first:
                                for fpos2 in range(len(fields_names)):
                                    if lines2 and lines2[0][fpos2]:
                                        data[fpos2] = lines2[0][fpos2]
                                lines += lines2[1:]
                                first = False
                            else:
                                lines += lines2
                        break
                    i += 1
                if i == len(field):
                    data[fpos] = str(row2 or '')
        return [data] + lines

    def export_data(self, cursor, user, ids, fields_names, context=None):
        fields_names = [x.split('/') for x in fields_names]
        datas = []
        for row in self.browse(cursor, user, ids, context):
            datas += self.__export_row(cursor, user, row, fields_names, context)
        return datas

    # TODO: Send a request with the result and multi-thread !
    def import_data(self, cursor, user, fields_names, datas, mode='init',
            current_module=None, noupdate=False, context=None):
        if context is None:
            context = {}
        fields_names = [x.split('/') for x in fields_names]
        logger = Logger()

        def process_liness(self, datas, prefix, fields_def, position=0):
            line = datas[position]
            row = {}
            translate = {}
            todo = []
            warning = ''
            data_id = False

            # Import normal fields_names
            for i in range(len(fields_names)):
                if i >= len(line):
                    raise Exception, \
                            'Please check that all your lines have %d cols.' % \
                            (len(fields_names),)
                field = fields_names[i]
                if field == ["id"]:
                    data_id = line[i]
                    continue
                if (len(field) == len(prefix) + 1) \
                        and field[len(prefix)].endswith(':id'):
                    res_id = False
                    if line[i]:
                        if fields_def[field[len(prefix)][:-3]]['type'] \
                                == 'many2many':
                            res_id = []
                            for word in line[i].split(','):
                                if '.' in word:
                                    module, xml_id = word.rsplit('.', 1)
                                else:
                                    module, xml_id = current_module, word
                                ir_model_data_obj = \
                                        self.pool.get('ir.model.data')
                                new_id = ir_model_data_obj._get_id(cursor,
                                        user, module, xml_id)
                                res_id2 = ir_model_data_obj.read(cursor, user,
                                        [new_id], ['res_id'])[0]['res_id']
                                if res_id2:
                                    res_id.append(res_id2)
                            if len(res_id):
                                res_id = [(6, 0, res_id)]
                        else:
                            if '.' in line[i]:
                                module, xml_id = line[i].rsplit('.', 1)
                            else:
                                module, xml_id = current_module, line[i]
                            ir_model_data_obj = self.pool.get('ir.model.data')
                            new_id = ir_model_data_obj._get_id(cursor, user,
                                    module, xml_id)
                            res_id = ir_model_data_obj.read(cursor, user,
                                    [new_id], ['res_id'])[0]['res_id']
                    row[field[0][:-3]] = res_id or False
                    continue
                if (len(field) == len(prefix)+1) and \
                        len(field[len(prefix)].split(':lang=')) == 2:
                    field, lang = field[len(prefix)].split(':lang=')
                    translate.setdefault(lang, {})[field]=line[i] or False
                    continue
                if (len(field) == len(prefix)+1) and \
                        (prefix == field[0:len(prefix)]):
                    if fields_def[field[len(prefix)]]['type'] == 'integer':
                        res = line[i] and int(line[i])
                    elif fields_def[field[len(prefix)]]['type'] == 'float':
                        res = line[i] and float(line[i])
                    elif fields_def[field[len(prefix)]]['type'] == 'selection':
                        res = False
                        if isinstance(
                                fields_def[field[len(prefix)]]['selection'],
                                (tuple, list)):
                            sel = fields_def[field[len(prefix)]]['selection']
                        else:
                            sel = fields_def[field[len(prefix)]]['selection'](
                                    self, cursor, user, context)
                        for key, val in sel:
                            if str(key) == line[i]:
                                res = key
                        if line[i] and not res:
                            logger.notify_channel("import", LOG_WARNING,
                                    "key '%s' not found " \
                                            "in selection field '%s'" % \
                                            (line[i], field[len(prefix)]))
                    elif fields_def[field[len(prefix)]]['type'] == 'many2one':
                        res = False
                        if line[i]:
                            relation = \
                                    fields_def[field[len(prefix)]]['relation']
                            res2 = self.pool.get(relation).name_search(cursor,
                                    user, line[i], [], operator='=')
                            res = (res2 and res2[0][0]) or False
                            if not res:
                                warning += ('Relation not found: ' + line[i] + \
                                        ' on ' + relation + ' !\n')
                                logger.notify_channel("import",
                                        LOG_WARNING,
                                        'Relation not found: ' + line[i] + \
                                                ' on ' + relation + ' !\n')
                    elif fields_def[field[len(prefix)]]['type'] == 'many2many':
                        res = []
                        if line[i]:
                            relation = \
                                    fields_def[field[len(prefix)]]['relation']
                            for word in line[i].split(','):
                                res2 = self.pool.get(relation).name_search(
                                        cursor, user, word, [], operator='=')
                                res3 = (res2 and res2[0][0]) or False
                                if not res3:
                                    warning += ('Relation not found: ' + \
                                            line[i] + ' on '+relation + ' !\n')
                                    logger.notify_channel("import",
                                            LOG_WARNING,
                                            'Relation not found: ' + line[i] + \
                                                    ' on '+relation + ' !\n')
                                else:
                                    res.append(res3)
                            if len(res):
                                res = [(6, 0, res)]
                    else:
                        res = line[i] or False
                    row[field[len(prefix)]] = res
                elif (prefix==field[0:len(prefix)]):
                    if field[0] not in todo:
                        todo.append(field[len(prefix)])

            # Import one2many fields
            nbrmax = 1
            for field in todo:
                newfd = self.pool.get(fields_def[field]['relation']).fields_get(
                        cursor, user, context=context)
                res = process_liness(self, datas, prefix + [field], newfd,
                        position)
                (newrow, max2, warning2, translate2, data_id2) = res
                nbrmax = max(nbrmax, max2)
                warning = warning + warning2
                reduce(lambda x, y: x and y, newrow)
                row[field] = (reduce(lambda x, y: x or y, newrow.values()) and \
                        [(0,0,newrow)]) or []
                i = max2
                while (position+i)<len(datas):
                    test = True
                    for j in range(len(fields_names)):
                        field2 = fields_names[j]
                        if (len(field2) <= (len(prefix)+1)) \
                                and datas[position+i][j]:
                            test = False
                    if not test:
                        break

                    (newrow, max2, warning2, translate2, data_id2) = \
                            process_liness(self, datas, prefix+[field], newfd,
                                    position + i)
                    warning = warning + warning2
                    if reduce(lambda x, y: x or y, newrow.values()):
                        row[field].append((0, 0, newrow))
                    i += max2
                    nbrmax = max(nbrmax, i)

            if len(prefix) == 0:
                for i in range(max(nbrmax, 1)):
                    datas.pop(0)
            result = (row, nbrmax, warning, translate, data_id)
            return result

        fields_def = self.fields_get(cursor, user, context=context)
        done = 0

        while len(datas):
            res = {}
            try:
                (res, other, warning, translate, data_id) = \
                        process_liness(self, datas, [], fields_def)
                if warning:
                    cursor.rollback()
                    return (-1, res, warning, '')
                new_id = self.pool.get('ir.model.data')._update(cursor, user,
                        self._name, current_module, res, xml_id=data_id,
                        mode=mode, noupdate=noupdate)
                for lang in translate:
                    context2 = context.copy()
                    context2['language'] = lang
                    self.write(cursor, user, [new_id], translate[lang],
                            context=context2)
            except Exception, exp:
                logger.notify_channel("import", LOG_ERROR, exp)
                cursor.rollback()
                return (-1, res, exp[0], warning)
            done += 1
        return (done, 0, 0, 0)

    def read(self, cursor, user, ids, fields_names=None, context=None,
            load='_classic_read'):
        self.pool.get('ir.model.access').check(cursor, user, self._name, 'read')
        if not fields_names:
            fields_names = self._columns.keys() + self._inherit_fields.keys()
        select = ids
        if isinstance(ids, (int, long)):
            select = [ids]
        result =  self._read_flat(cursor, user, select, fields_names, context,
                load)
        for i in result:
            for key, j in i.items():
                if j == None:
                    i[key] = False
        if isinstance(ids, (int, long)):
            return result[0]
        return result

    def _read_flat(self, cursor, user, ids, fields_names, context=None,
            load='_classic_read'):
        if context is None:
            context = {}
        if not ids:
            return []

        if fields_names == None:
            fields_names = self._columns.keys()

        # construct a clause for the rules :
        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name)

        # all inherited fields + all non inherited fields
        # for which the attribute whose name is in load is True
        fields_pre = [x for x in fields_names if x in self._columns \
                and getattr(self._columns[x], '_classic_write')] + \
                self._inherits.values()

        res = []
        if len(fields_pre) :
            fields_pre2 = [(x in ('create_date', 'write_date')) \
                    and ('date_trunc(\'second\', ' + x + ') as ' + x) \
                    or '"' + x + '"' for x in fields_pre]
            for i in range((len(ids) / ID_MAX) + ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids = ids[ID_MAX * i:ID_MAX * (i + 1)]
                if domain1:
                    cursor.execute(('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM \"' + self._table +'\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join([str(x) for x in sub_ids]) + ')'\
                            ' AND ' + domain1 + ' ORDER BY ' + self._order),
                            domain2)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise ExceptORM('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                else:
                    cursor.execute('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM \"' + self._table + '\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join([str(x) for x in sub_ids]) + ')'\
                            ' ORDER BY ' + self._order)
                res.extend(cursor.dictfetchall())
        else:
            res = [{'id': x} for x in ids]

        for field in fields_pre:
            if self._columns[field].translate:
                ids = [x['id'] for x in res]
                res_trans = self.pool.get('ir.translation')._get_ids(cursor,
                        self._name + ',' + field, 'model',
                        context.get('language', 'en_US'), ids)
                for i in res:
                    i[field] = res_trans.get(i['id'], False) or i[field]

        for table in self._inherits:
            col = self._inherits[table]
            cols = intersect(self._inherit_fields.keys(), fields_names)
            if not cols:
                continue
            res2 = self.pool.get(table).read(cursor, user,
                    [x[col] for x in res], cols, context, load)

            res3 = {}
            for i in res2:
                res3[i['id']] = i
                del i['id']

            for record in res:
                record.update(res3[record[col]])
                if col not in fields_names:
                    del record[col]

        # all fields which need to be post-processed
        # by a simple function (symbol_get)
        fields_post = [x for x in fields_names if x in self._columns \
                and self._columns[x]._symbol_get]
        if fields_post:
            # maybe it would be faster to iterate on the fields_names then
            # on res,  so that we wouldn't need to get the _symbol_get
            # in each occurence
            for i in res:
                for field in fields_post:
                    i[field] = self._columns[field]._symbol_get(i[field])
        ids = [x['id'] for x in res]

        # all non inherited fields for which the attribute
        # whose name is in load is False
        fields_post = [x for x in fields_names if x in self._columns \
                and not getattr(self._columns[x], load)]
        for field in fields_post:
            # get the value of that field for all records/ids
            res2 = self._columns[field].get(cursor, self, ids, field, user,
                    context=context, values=res)
            for record in res:
                record[field] = res2[record['id']]
        return res

    def _validate(self, cursor, user, ids):
        field_error = []
        field_err_str = []
        for field in self._constraints:
            if not field[0](self, cursor, user, ids):
                if len(field) > 1:
                    field_error += field[2]
                field_err_str.append(field[1])
        if len(field_err_str):
            raise ExceptORM('ValidateError',
                    ('\n'.join(field_err_str), ','.join(field_error)))

    def default_get(self, cursor, user, fields_names, context=None):
        value = {}
        # get the default values for the inherited fields
        for i in self._inherits.keys():
            value.update(self.pool.get(i).default_get(cursor, user,
                fields_names, context=context))

        # get the default values defined in the object
        for field in fields_names:
            if field in self._defaults:
                value[field] = self._defaults[field](self, cursor, user,
                        context)
                fld_def = ((field in self._columns) and self._columns[field]) \
                        or ((field in self._inherit_fields) \
                            and self._inherit_fields[field][2]) \
                        or False
                if isinstance(fld_def, fields.Property):
                    property_obj = self.pool.get('ir.property')
                    value[field] = property_obj.get(cursor, user, field,
                            self._name)

        # get the default values set by the user and override the default
        # values defined in the object
        ir_default_obj = self.pool.get('ir.default')
        defaults = ir_default_obj.get_default(cursor, user,
                self._name, False, context=context)
        for field, field_value in defaults.items():
            if field in fields_names:
                fld_def = (field in self._columns) and self._columns[field] \
                        or self._inherit_fields[field][2]
                if fld_def._type in ('many2one', 'one2one'):
                    obj = self.pool.get(fld_def._obj)
                    if not obj.search(cursor, user, [('id', '=', field_value)]):
                        continue
                if fld_def._type in ('many2many'):
                    obj = self.pool.get(fld_def._obj)
                    field_value2 = []
                    for i in range(len(field_value)):
                        if not obj.search(cursor, user, [('id', '=',
                            field_value[i])]):
                            continue
                        field_value2.append(field_value[i])
                    field_value = field_value2
                if fld_def._type in ('one2many'):
                    obj = self.pool.get(fld_def._obj)
                    field_value2 = []
                    for i in range(len(field_value)):
                        field_value2.append({})
                        for field2 in field_value[i]:
                            if obj._columns[field2]._type \
                                    in ('many2one', 'one2one'):
                                obj2 = self.pool.get(obj._columns[field2]._obj)
                                if not obj2.search(cursor, user,
                                        [('id', '=', field_value[i][field2])]):
                                    continue
                            # TODO add test for many2many and one2many
                            field_value2[i][field2] = field_value[i][field2]
                    field_value = field_value2
                value[field] = field_value
        return value

    def unlink(self, cursor, user, ids, context=None):
        if context is None:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        delta = context.get('read_delta', False)
        if delta and self._log_access:
            for i in range((len(ids) / ID_MAX) + \
                    ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids = ids[ID_MAX * i:ID_MAX * (i + 1)]
                cursor.execute(
                        "SELECT (now()  - min(write_date)) <= '%s'::interval " \
                        "FROM \"%s\" WHERE id in (%s)" % \
                        (delta, self._table,
                            ",".join([str(x) for x in sub_ids])))
                res = cursor.fetchone()
                if res and res[0]:
                    raise ExceptORM('ConcurrencyException',
                            'This record was modified in the meanwhile')

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'unlink')

        wf_service = LocalService("workflow")
        for obj_id in ids:
            wf_service.trg_delete(user, self._name, obj_id, cursor)

        #cursor.execute('select * from ' + self._table + \
        #       ' where id in ('+str_d+')', ids)
        #res = cursor.dictfetchall()
        #for key in self._inherits:
        #    ids2 = [x[self._inherits[key]] for x in res]
        #    self.pool.get(key).unlink(cursor, user, ids2)

        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name)
        if domain1:
            domain1 = ' AND ' + domain1
        for i in range((len(ids) / ID_MAX) + \
                ((len(ids) % ID_MAX) and 1 or 0)):
            sub_ids = ids[ID_MAX * i:ID_MAX * (i + 1)]
            str_d = ','.join(('%d',) * len(sub_ids))
            if domain1:
                cursor.execute('SELECT id FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ') ' + domain1,
                        sub_ids + domain2)
                if not cursor.rowcount == len({}.fromkeys(ids)):
                    raise ExceptORM('AccessError',
                            'You try to bypass an access rule ' \
                                '(Document type: %s).' % self._description)

            cursor.execute('DELETE FROM inherit ' \
                    'WHERE (obj_type = %s AND obj_id IN ('+str_d+')) ' \
                        'OR (inst_type = %s AND inst_id IN ('+str_d+'))',
                        ((self._name,) + tuple(sub_ids) + \
                                (self._name,) + tuple(sub_ids)))
            if domain1:
                cursor.execute('DELETE FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ') ' + domain1,
                        sub_ids + domain2)
            else:
                cursor.execute('DELETE FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ')', sub_ids)
        return True

    # TODO: Validate
    def write(self, cursor, user, ids, vals, context=None):
        if context is None:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        delta = context.get('read_delta', False)
        if delta and self._log_access:
            for i in range((len(ids) / ID_MAX) + \
                    ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids = ids[ID_MAX * i:ID_MAX * (i + 1)]
                cursor.execute("SELECT " \
                            "(now() - min(write_date)) <= '%s'::interval"\
                        " FROM %s WHERE id IN (%s)" % \
                        (delta, self._table,
                            ",".join([str(x) for x in sub_ids])))
                res = cursor.fetchone()
                if res and res[0]:
                    for field in vals:
                        if field in self._columns \
                                and self._columns[field]._classic_write:
                            raise ExceptORM('ConcurrencyException',
                                    'This record was modified in the meanwhile')

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'write')

        #for v in self._inherits.values():
        #    assert v not in vals, (v, vals)
        upd0 = []
        upd1 = []
        upd_todo = []
        updend = []
        direct = []
        totranslate = context.get('language', False) \
                and (context['language'] != 'en_US')
        for field in vals:
            if field in self._columns:
                if self._columns[field]._classic_write:
                    if (not totranslate) or not self._columns[field].translate:
                        upd0.append('"' + field + '"=' + \
                                self._columns[field]._symbol_set[0])
                        upd1.append(self._columns[field]._symbol_set[1](
                            vals[field]))
                    direct.append(field)
                else:
                    upd_todo.append(field)
            else:
                updend.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                if self._columns[field]._type == 'reference':
                    val = vals[field].split(',')[0]
                else:
                    val = vals[field]
                if isinstance(self._columns[field].selection, (tuple, list)):
                    if val not in dict(self._columns[field].selection):
                        raise ExceptORM('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
                else:
                    if val not in dict(self._columns[field].selection(
                        self, cursor, user, context=context)):
                        raise ExceptORM('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))

        if self._log_access:
            upd0.append('write_uid=%d')
            upd0.append('write_date=now()')
            upd1.append(user)

        if len(upd0):
            domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor,
                    user, self._name)
            if domain1:
                domain1 = ' and ' + domain1
            for i in range((len(ids) / ID_MAX) + \
                    ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids = ids[ID_MAX * i:ID_MAX * (i + 1)]
                ids_str = ','.join([str(x) for x in sub_ids])
                if domain1:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE id IN (' + ids_str + ') ' + domain1, domain2)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise ExceptORM('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                else:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE id IN (' + ids_str + ')')
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise ExceptORM('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                if domain1:
                    cursor.execute('UPDATE "' + self._table + '" ' \
                            'SET ' + ','.join(upd0) + ' ' \
                            'WHERE id IN (' + ids_str + ') ' + domain1,
                            upd1 + domain2)
                else:
                    cursor.execute('UPDATE "' + self._table + '" ' \
                            'SET ' + ','.join(upd0) + ' ' \
                            'WHERE id IN (' + ids_str + ') ', upd1)

            if totranslate:
                for field in direct:
                    if self._columns[field].translate:
                        self.pool.get('ir.translation')._set_ids(cursor, user,
                                self._name + ',' + field, 'model',
                                context['language'], ids, vals[field])

        # call the 'set' method of fields which are not classic_write
        upd_todo.sort(lambda x, y: self._columns[x].priority - \
                self._columns[y].priority)
        for field in upd_todo:
            for select_id in ids:
                self._columns[field].set(cursor, self, select_id, field,
                        vals[field], user, context=context)

        for table in self._inherits:
            col = self._inherits[table]
            nids = []
            for i in range((len(ids) / ID_MAX) + \
                    ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids = ids[ID_MAX * i:ID_MAX * (i +1)]
                ids_str = ','.join([str(x) for x in sub_ids])
                cursor.execute('SELECT DISTINCT "' + col + '" ' \
                        'FROM "' + self._table + '" WHERE id IN (' + ids_str + ')',
                        upd1)
                nids.extend([x[0] for x in cursor.fetchall()])

            vals2 = {}
            for val in updend:
                if self._inherit_fields[val][0] == table:
                    vals2[val] = vals[val]
            self.pool.get(table).write(cursor, user, nids, vals2,
                    context=context)

        self._validate(cursor, user, ids)

        if context.has_key('read_delta'):
            del context['read_delta']

        wf_service = LocalService("workflow")
        for obj_id in ids:
            wf_service.trg_write(user, self._name, obj_id, cursor)
        return True

    def create(self, cursor, user, vals, context=None):
        """
        cursor = database cursor
        user = user id
        vals = dictionary of the form {'field_name': field_value, ...}
        """
        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'create')

        default = []
        avoid_table = []
        for (i, j) in self._inherits.items():
            if j in vals:
                avoid_table.append(i)
        for i in self._columns.keys(): # + self._inherit_fields.keys():
            if not i in vals:
                default.append(i)
        for i in self._inherit_fields.keys():
            if (not i in vals) \
                    and (not self._inherit_fields[i][0] in avoid_table):
                default.append(i)

        if len(default):
            vals.update(self.default_get(cursor, user, default, context))

        tocreate = {}
        for i in self._inherits:
            if self._inherits[i] not in vals:
                tocreate[i] = {}

        (upd0, upd1, upd2) = ('', '', [])
        upd_todo = []

        for i in vals.keys():
            if i in self._inherit_fields:
                (table, col, col_detail) = self._inherit_fields[i]
                tocreate[table][i] = vals[i]
                del vals[i]

        cursor.execute("SELECT NEXTVAL('" + self._sequence + "')")
        (id_new,) = cursor.fetchone()
        for table in tocreate:
            new_id = self.pool.get(table).create(cursor, user, tocreate[table])
            upd0 += ',' + self._inherits[table]
            upd1 += ',%d'
            upd2.append(new_id)
            cursor.execute('INSERT INTO inherit ' \
                    '(obj_type, obj_id, inst_type, inst_id) ' \
                    'values (%s, %d, %s, %d)',
                    (table, new_id, self._name, id_new))

        for field in vals:
            if self._columns[field]._classic_write:
                upd0 = upd0 + ',"' + field + '"'
                upd1 = upd1 + ',' + self._columns[field]._symbol_set[0]
                upd2.append(self._columns[field]._symbol_set[1](vals[field]))
            else:
                upd_todo.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                if self._columns[field]._type == 'reference':
                    val = vals[field].split(',')[0]
                else:
                    val = vals[field]
                if isinstance(self._columns[field].selection, (tuple, list)):
                    if val not in dict(self._columns[field].selection):
                        raise ExceptORM('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
                else:
                    if val not in dict(self._columns[field].selection(
                        self, cursor, user, context=context)):
                        raise ExceptORM('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
        if self._log_access:
            upd0 += ', create_uid, create_date'
            upd1 += ', %d, now()'
            upd2.append(user)
        cursor.execute('INSERT INTO "' + self._table + '" ' \
                '(id' + upd0 + ') ' \
                'VALUES (' + str(id_new) + upd1 + ')', tuple(upd2))
        upd_todo.sort(lambda x, y: self._columns[x].priority - \
                self._columns[y].priority)
        for field in upd_todo:
            self._columns[field].set(cursor, self, id_new, field, vals[field],
                    user, context)

        self._validate(cursor, user, [id_new])

        wf_service = LocalService("workflow")
        wf_service.trg_create(user, self._name, id_new, cursor)
        return id_new

    def fields_get(self, cursor, user, fields_names=None, context=None):
        """
        returns the definition of each field in the object
        the optional fields_names parameter can limit the result to some fields
        """
        if context is None:
            context = {}
        res = {}
        translation_obj = self.pool.get('ir.translation')
        model_access_obj = self.pool.get('ir.model.access')
        for parent in self._inherits:
            res.update(self.pool.get(parent).fields_get(cursor, user,
                fields_names, context))
        read_access = model_access_obj.check(cursor, user, self._name, 'write',
                raise_exception=False)
        for field in self._columns.keys():
            res[field] = {'type': self._columns[field]._type}
            for arg in (
                    'string',
                    'readonly',
                    'states',
                    'size',
                    'required',
                    'change_default',
                    'translate',
                    'help',
                    'select',
                    ):
                if getattr(self._columns[field], arg):
                    res[field][arg] = getattr(self._columns[field], arg)
            if not read_access:
                res[field]['readonly'] = True
                res[field]['states'] = {}
            for arg in ('digits', 'invisible'):
                if hasattr(self._columns[field], arg) \
                        and getattr(self._columns[field], arg):
                    res[field][arg] = getattr(self._columns[field], arg)

            # translate the field label
            res_trans = translation_obj._get_source(cursor,
                    self._name + ',' + field, 'field',
                    context.get('language', 'en_US'))
            if res_trans:
                res[field]['string'] = res_trans
            help_trans = translation_obj._get_source(cursor,
                    self._name + ',' + field, 'help',
                    context.get('language', 'en_US'))
            if help_trans:
                res[field]['help'] = help_trans

            if hasattr(self._columns[field], 'selection'):
                if isinstance(self._columns[field].selection, (tuple, list)):
                    sel = self._columns[field].selection
                    # translate each selection option
                    sel2 = []
                    for (key, val) in sel:
                        val2 = translation_obj._get_source(cursor,
                                self._name + ',' + field, 'selection',
                                context.get('language', 'en_US'), val)
                        sel2.append((key, val2 or val))
                    sel = sel2
                    res[field]['selection'] = sel
                else:
                    # call the 'dynamic selection' function
                    res[field]['selection'] = self._columns[field].selection(
                            self, cursor, user, context)
            if res[field]['type'] in (
                    'one2many',
                    'many2many',
                    'many2one',
                    'one2one',
                    ):
                res[field]['relation'] = self._columns[field]._obj
                res[field]['domain'] = self._columns[field]._domain
                res[field]['context'] = self._columns[field]._context

        if fields_names:
            # filter out fields which aren't in the fields_names list
            for i in res.keys():
                if i not in fields_names:
                    del res[i]
        return res

    def view_header_get(self, cursor, user, view_id=None, view_type='form',
            context=None):
        """
        Overload this method if you need a window title
        which depends on the context
        """
        return False

    def __view_look_dom(self, cursor, user, node, context=None):
        if context is None:
            context = {}
        result = False
        fields_attrs = {}
        childs = True
        if node.nodeType == node.ELEMENT_NODE and node.localName == 'field':
            if node.hasAttribute('name'):
                attrs = {}
                try:
                    if node.getAttribute('name') in self._columns:
                        relation = self._columns[node.getAttribute('name')]._obj
                    else:
                        relation = self._inherit_fields[node.getAttribute(
                            'name')][2]._obj
                except:
                    relation = False
                if relation:
                    childs = False
                    views = {}
                    for field in node.childNodes:
                        if field.nodeType == field.ELEMENT_NODE \
                                and field.localName in ('form', 'tree'):
                            node.removeChild(field)
                            xarch, xfields = self.pool.get(relation
                                    ).__view_look_dom_arch(cursor, user, field,
                                            context)
                            views[str(field.localName)] = {
                                'arch': xarch,
                                'fields': xfields
                            }
                    attrs = {'views': views}
                fields_attrs[node.getAttribute('name')] = attrs

        elif node.nodeType == node.ELEMENT_NODE \
                and node.localName in ('form','tree'):
            result = self.view_header_get(cursor, user, False, node.localName,
                    context)
            if result:
                node.setAttribute('string', result.decode('utf8'))

        if node.nodeType == node.ELEMENT_NODE:
            # translate view
            translation_obj = self.pool.get('ir.translation')
            if ('language' in context) and not result:
                if node.hasAttribute('string') and node.getAttribute('string'):
                    trans = translation_obj._get_source(cursor,
                            self._name, 'view', context['language'],
                            node.getAttribute('string').encode('utf8'))
                    if trans:
                        node.setAttribute('string', trans.decode('utf8'))
                if node.hasAttribute('sum') and node.getAttribute('sum'):
                    trans = translation_obj._get_source(cursor,
                            self._name, 'view', context['language'],
                            node.getAttribute('sum').encode('utf8'))
                    if trans:
                        node.setAttribute('sum', trans.decode('utf8'))
            # Add view for properties !
            if node.localName == 'properties':
                parent = node.parentNode
                doc = node.ownerDocument
                models = ["'" + x + "'" for x in  [self._name] + \
                        self._inherits.keys()]
                cursor.execute('SELECT name, group_name ' \
                        'FROM ir_model_fields ' \
                        'WHERE model in (' + ','.join(models) + ') ' \
                            'AND view_load ORDER BY group_name, id')
                oldgroup = None
                for fname, gname in cursor.fetchall():
                    if oldgroup != gname:
                        child = doc.createElement('separator')
                        child.setAttribute('string', gname.decode('utf8'))
                        child.setAttribute('colspan', "4")
                        oldgroup = gname
                        parent.insertBefore(child, node)

                    child = doc.createElement('field')
                    child.setAttribute('name', fname.decode('utf8'))
                    parent.insertBefore(child, node)
                parent.removeChild(node)

        if childs:
            for field in node.childNodes:
                fields_attrs.update(self.__view_look_dom(cursor, user, field,
                    context))
        return fields_attrs

    def __view_look_dom_arch(self, cursor, user, node, context=None):
        fields_def = self.__view_look_dom(cursor, user, node, context=context)
        arch = node.toxml(encoding="utf-8").replace('\t', '')
        fields2 = self.fields_get(cursor, user, fields_def.keys(), context)
        for field in fields_def:
            if field in fields2:
                fields2[field].update(fields_def[field])
        return arch, fields2

    def fields_view_get(self, cursor, user, view_id=None, view_type='form',
            context=None, toolbar=False, hexmd5=None):

        def _inherit_apply(src, inherit):

            def _find(node, node2):
                if node2.nodeType == node2.ELEMENT_NODE \
                        and node2.localName == 'xpath':
                    res = xpath.Evaluate(node2.getAttribute('expr'), node)
                    return res and res[0] or None
                return None

            doc_src = dom.minidom.parseString(src)
            doc_dest = dom.minidom.parseString(inherit)
            for node2 in doc_dest.childNodes:
                if not node2.nodeType == node2.ELEMENT_NODE:
                    continue
                node = _find(doc_src, node2)
                if node:
                    pos = 'inside'
                    if node2.hasAttribute('position'):
                        pos = node2.getAttribute('position')
                    if pos == 'replace':
                        parent = node.parentNode
                        for child in node2.childNodes:
                            if child.nodeType == child.ELEMENT_NODE:
                                parent.insertBefore(child, node)
                        parent.removeChild(node)
                    else:
                        for child in node2.childNodes:
                            if child.nodeType == child.ELEMENT_NODE:
                                if pos == 'inside':
                                    node.appendChild(child)
                                elif pos == 'after':
                                    sib = node.nextSibling
                                    if sib:
                                        node.parentNode.insertBefore(child, sib)
                                    else:
                                        node.parentNode.appendChild(child)
                                elif pos == 'before':
                                    node.parentNode.insertBefore(child, node)
                                else:
                                    raise AttributeError, \
                                            'Unknown position ' \
                                            'in inherited view %s!' % pos
                else:
                    attrs = ''.join([
                        ' %s="%s"' % (attr, node2.getAttribute(attr))
                        for attr in node2.attributes.keys()
                        if attr != 'position'
                    ])
                    tag = "<%s%s>" % (node2.localName, attrs)
                    raise AttributeError, \
                            "Couldn't find tag '%s' in parent view !" % tag
            return doc_src.toxml(encoding="utf-8").replace('\t', '')

        result = {'type': view_type, 'model': self._name}

        test = True
        model = True
        sql_res = False
        while test:
            if view_id:
                where = (model and (" and model='%s'" % (self._name,))) or ''
                cursor.execute('SELECT arch, name, field_parent, id, type, ' \
                            'inherit_id ' \
                        'FROM ir_ui_view WHERE id = %d ' + where, (view_id,))
            else:
                cursor.execute('SELECT arch, name, field_parent, id, type, ' \
                        'inherit_id ' \
                        'FROM ir_ui_view ' \
                        'WHERE model = %s AND type = %s ORDER BY priority',
                        (self._name,view_type))
            sql_res = cursor.fetchone()
            if not sql_res:
                break
            test = sql_res[5]
            view_id = test or sql_res[3]
            model = False

        # if a view was found
        if sql_res:
            result['type'] = sql_res[4]
            result['view_id'] = sql_res[3]
            result['arch'] = sql_res[0]

            def _inherit_apply_rec(result, inherit_id):
                # get all views which inherit from (ie modify) this view
                cursor.execute('SELECT arch, id FROM ir_ui_view ' \
                        'WHERE inherit_id = %d AND model = %s ' \
                        'ORDER BY priority', (inherit_id, self._name))
                sql_inherit = cursor.fetchall()
                for (inherit, view_id) in sql_inherit:
                    result = _inherit_apply(result, inherit)
                    result = _inherit_apply_rec(result, view_id)
                return result

            result['arch'] = _inherit_apply_rec(result['arch'], sql_res[3])

            result['name'] = sql_res[1]
            result['field_parent'] = sql_res[2] or False
        # otherwise, build some kind of default view
        else:
            if view_type == 'form':
                res = self.fields_get(cursor, user, context=context)
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<form string="%s">''' % (self._description,)
                for i in res:
                    if res[i]['type'] not in ('one2many', 'many2many'):
                        xml += '<field name="%s"/>' % (i,)
                        if res[i]['type'] == 'text':
                            xml += "<newline/>"
                xml += "</form>"
            elif view_type == 'tree':
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<tree string="%s"><field name="%s"/></tree>''' \
                % (self._description, self._rec_name)
            elif view_type == 'calendar':
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<calendar string="%s" date_start="%s">''' \
                '''<field name="%s"/></calendar>''' \
                % (self._description, self._date_name, self._rec_name)
            else:
                xml = ''
            result['arch'] = xml
            result['name'] = 'default'
            result['field_parent'] = False
            result['view_id'] = 0

        doc = dom.minidom.parseString(result['arch'])
        xarch, xfields = self.__view_look_dom_arch(cursor, user, doc,
                context=context)
        result['arch'] = xarch
        result['fields'] = xfields
        if toolbar:
            action_obj = self.pool.get('ir.action.keyword')
            prints = action_obj.get_keyword(cursor, user, 'form_print',
                    (self._name, 0), context=context)
            actions = action_obj.get_keyword(cursor, user, 'form_action',
                    (self._name, 0), context=context)
            relates = action_obj.get_keyword(cursor, user, 'form_relate',
                    (self._name, 0), context=context)
            result['toolbar'] = {
                'print': prints,
                'action': actions,
                'relate': relates,
            }
        result['md5'] = md5.new(str(result)).hexdigest()
        if hexmd5 == result['md5']:
            return True
        return result

    fields_view_get = Cache()(fields_view_get)

    _view_look_dom_arch = __view_look_dom_arch

    def _where_calc(self, cursor, user, args, active_test=True, context=None):
        if context is None:
            context = {}
        args = args[:]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if 'active' in self._columns \
                and (active_test and context.get('active_test', True)):
            i = 0
            active_found = False
            while i < len(args):
                if args[i][0] == 'active':
                    active_found = True
                i += 1
            if not active_found:
                args.append(('active', '=', 1))

        i = 0
        tables = ['"' + self._table + '"']
        joins = []
        while i < len(args):
            table = self
            if args[i][0] in self._inherit_fields:
                table = self.pool.get(self._inherit_fields[args[i][0]][0])
                if ('"' + table._table + '"' not in tables):
                    tables.append('"' + table._table + '"')
                    joins.append(('id', 'join', '%s.%s' % \
                            (self._table, self._inherits[table._name]), table))
            fargs = args[i][0].split('.', 1)
            field = table._columns.get(fargs[0], False)
            if not field:
                if args[i][0] == 'id' and args[i][1] == 'child_of':
                    ids2 = args[i][2]
                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids)], context=context)
                        return ids2 + _rec_get(ids2, table, parent)
                    args[i] = (args[i][0], 'in', ids2 + \
                            _rec_get(ids2, table, table._parent_name), table)
                i += 1
                continue
            if len(fargs) > 1:
                if field._type == 'many2one':
                    args[i] = (fargs[0], 'in',
                            self.pool.get(field._obj).search(cursor, user,
                                [(fargs[1], args[i][1], args[i][2])],
                                context=context))
                    i += 1
                    continue
                else:
                    i += 1
                    continue
            if field._properties:
                arg = [args.pop(i)]
                j = i
                while j < len(args):
                    if args[j][0] == arg[0][0]:
                        arg.append(args.pop(j))
                    else:
                        j += 1
                if field._fnct_search:
                    args.extend(field.search(cursor, user, self,
                        arg[0][0], arg))
            elif field._type == 'one2many':
                field_obj = self.pool.get(field._obj)

                if isinstance(args[i][2], basestring):
                    # get the ids of the records of the "distant" resource
                    ids2 = [x[0] for x in field_obj.name_search(cursor, user,
                        args[i][2], [], args[i][1])]
                else:
                    ids2 = args[i][2]
                if not ids2:
                    args[i] = ('id', '=', '0')
                else:
                    ids3 = []
                    for i in range((len(ids2) / ID_MAX) + \
                            (len(ids2) % ID_MAX)):
                        sub_ids = ids2[ID_MAX * i:ID_MAX * (i + 1)]
                        cursor.execute('SELECT "' + field._fields_id + \
                                '" FROM "' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join([str(x) for x in sub_ids2]) + ')')
                        ids3.extend([x[0] for x in cursor.fetchall()])

                    args[i] = ('id', 'in', ids3)
                i += 1
            elif field._type == 'many2many':
                #FIXME
                if args[i][1] == 'child_of':
                    if isinstance(args[i][2], basestring):
                        ids2 = [x[0] for x in self.pool.get(
                        field._obj).name_search(cursor, user, args[i][2], [],
                            'like')]
                    else:
                        ids2 = args[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids)], context=context)
                        return ids + _rec_get(ids2, table, parent)

                    def _rec_convert(ids):
                        if self.pool.get(field._obj)==self:
                            return ids
                        if not len(ids):
                            return []
                        cursor.execute('SELECT "' + field._id1 + '" ' \
                                'FROM "' + field._rel + '" ' \
                                'WHERE "' + field._id2 + '" IN (' + \
                                    ','.join([str(x) for x in ids]) + ')')
                        ids = [x[0] for x in cursor.fetchall()]
                        return ids

                    args[i] = ('id', 'in', _rec_convert(ids2 + _rec_get(ids2,
                        self.pool.get(field._obj), table._parent_name)))
                else:
                    if isinstance(args[i][2], basestring):
                        res_ids = [x[0] for x in self.pool.get(field._obj
                            ).name_search(cursor, user, args[i][2], [],
                                args[i][1])]
                    else:
                        res_ids = args[i][2]
                    if not len(res_ids):
                        args[i] = ('id', 'in', [0])
                    else:
                        cursor.execute('SELECT "' + field._id1 + '" ' \
                                'FROM "' + field._rel + '" ' \
                                'WHERE "' + field._id2 + '" IN (' + \
                                    ','.join([str(x) for x in res_ids]) + ')')
                        args[i] = ('id', 'in',
                                [x[0] for x in cursor.fetchall()])
                i += 1

            elif field._type == 'many2one':
                if args[i][1] == 'child_of':
                    if isinstance(args[i][2], basestring):
                        ids2 = [x[0] for x in self.pool.get(
                            field._obj).name_search(cursor, user, args[i][2],
                                [], 'like')]
                    else:
                        ids2 = args[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids)], context=context)
                        return ids + _rec_get(ids2, table, parent)

                    if field._obj != table._name:
                        args[i] = (args[i][0], 'in', ids2 + _rec_get(ids2,
                            self.pool.get(field._obj), table._parent_name),
                            table)
                    else:
                        args[i] = ('id', 'in', ids2 + _rec_get(ids2, table,
                            args[i][0]), table)
                else:
                    if isinstance(args[i][2], basestring):
                        res_ids = self.pool.get(field._obj).name_search(cursor,
                                user, args[i][2], [], args[i][1])
                        args[i] = (args[i][0], 'in', [x[0] for x in res_ids],
                                table)
                    else:
                        args[i] += (table,)
                i += 1
            else:
                if field.translate:
                    if args[i][1] in ('like', 'ilike'):
                        args[i] = (args[i][0], args[i][1],
                                '%%%s%%' % args[i][2])
                    cursor.execute('SELECT res_id FROM ir_translation ' \
                            'WHERE name = %s AND lang = %s ' \
                                'AND type = %s ' \
                                'AND value ' + args[i][1] + ' %s',
                            (table._name + ',' + args[i][0],
                                context.get('language', 'en_US'), 'model',
                                args[i][2]))
                    ids = [x[0] for x in cursor.fetchall()]
                    cursor.execute('SELECT id FROM "' + table._table + '" ' \
                            'WHERE "' + args[i][0]+'" '+args[i][1]+' %s',
                            (args[i][2],))
                    ids += [x[0] for x in cursor.fetchall()]
                    args[i] = ('id', 'in', ids, table)
                else:
                    args[i] += (table,)
                i += 1
        args.extend(joins)

        qu1, qu2 = [], []
        for arg in args:
            table = self
            if len(arg) > 3:
                table = arg[3]
            if arg[1] != 'in':
                if (arg[2] is False) and (arg[1] == '='):
                    qu1.append('(%s.%s IS NULL)' % \
                            (table._table, arg[0]))
                elif (arg[2] is False) and (arg[1] == '<>' or arg[1] == '!='):
                    qu1.append('(%s.%s IS NOT NULL)' % \
                            (table._table, arg[0]))
                else:
                    if arg[0] == 'id':
                        if arg[1] == 'join':
                            qu1.append('(%s.%s = %s)' % \
                                    (table._table, arg[0], arg[2]))
                        else:
                            qu1.append('(%s.%s %s %%s)' % \
                                    (table._table, arg[0], arg[1]))
                            qu2.append(arg[2])
                    else:
                        add_null = False
                        if arg[1] in ('like', 'ilike'):
                            if isinstance(arg[2], str):
                                str_utf8 = arg[2]
                            elif isinstance(arg[2], unicode):
                                str_utf8 = arg[2].encode('utf-8')
                            else:
                                str_utf8 = str(arg[2])
                            qu2.append('%%%s%%' % str_utf8)
                            if not str_utf8:
                                add_null = True
                        else:
                            if arg[0] in table._columns:
                                qu2.append(table._columns[arg[0]].\
                                        _symbol_set[1](arg[2]))
                        if arg[1] == '=like':
                            arg1 = 'like'
                        else:
                            arg1 = arg[1]
                        if arg[0] in table._columns:
                            if arg[1] in ('like', 'ilike'):
                                qu1.append('(%s.%s %s %s)' % (table._table,
                                    arg[0], arg1, '%s'))
                            else:
                                qu1.append('(%s.%s %s %s)' % (table._table,
                                    arg[0], arg1,
                                    table._columns[arg[0]]._symbol_set[0]))
                        else:
                            qu1.append('(%s.%s %s \'%s\')' % \
                                    (table._table, arg[0], arg1, arg[2]))

                        if add_null:
                            qu1[-1] = '('+qu1[-1]+' or '+arg[0]+' is null)'
            elif arg[1] == 'in':
                if len(arg[2]) > 0:
                    todel = []
                    for xitem in range(len(arg[2])):
                        if arg[2][xitem] == False \
                                and isinstance(arg[2][xitem],bool):
                            todel.append(xitem)
                    for xitem in todel[::-1]:
                        del arg[2][xitem]
                    #TODO fix max_stack_depth
                    if arg[0] == 'id':
                        qu1.append('(%s.id in (%s))' % \
                                (table._table,
                                    ','.join(['%d'] * len(arg[2])),))
                    else:
                        qu1.append('(%s.%s in (%s))' % \
                                (table._table, arg[0], ','.join(
                                    [table._columns[arg[0]].\
                                            _symbol_set[0]] * len(arg[2]))))
                    if todel:
                        qu1[-1] = '(' + qu1[-1] + ' or ' + arg[0] + ' is null)'
                    qu2 += arg[2]
                else:
                    qu1.append(' false')
        return (qu1, qu2, tables)

    def search_count(self, cursor, user, args, context=None):
        res = self.search(cursor, user, args, context=context, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False):
        # compute the where, order by, limit and offset clauses
        (qu1, qu2, tables) = self._where_calc(cursor, user, args,
                context=context)

        if len(qu1):
            qu1 = ' WHERE ' + ' AND '.join(qu1)
        else:
            qu1 = ''
        order_by = order or self._order

        limit_str = limit and ' LIMIT %d' % limit or ''
        offset_str = offset and ' OFFSET %d' % offset or ''


        # construct a clause for the rules :
        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name)
        if domain1:
            qu1 = qu1 and qu1 + ' AND ' + domain1 or ' WHERE ' + domain1
            qu2 += domain2

        if count:
            cursor.execute('SELECT COUNT(%s.id) FROM ' % self._table +
                    ','.join(tables) + qu1 + limit_str + offset_str, qu2)
            res = cursor.fetchall()
            return res[0][0]
        # execute the "main" query to fetch the ids we were searching for
        cursor.execute('SELECT %s.id FROM ' % self._table +
                ','.join(tables) + qu1 + ' order by ' + order_by + limit_str +
                offset_str, qu2)
        res = cursor.fetchall()
        return [x[0] for x in res]

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r['id'], str(r[self._rec_name])) for r in self.read(cursor,
            user, ids, [self._rec_name], context, load='_classic_write')]

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=80):
        if args is None:
            args = []
        args = args[:]
        if name:
            args += [(self._rec_name, operator, name)]
        ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context)
        return res

    def copy(self, cursor, user, object_id, default=None, context=None):
        if default is None:
            default = {}
        if 'state' not in default:
            if 'state' in self._defaults:
                default['state'] = self._defaults['state'](self, cursor, user,
                        context)
        data = self.read(cursor, user, object_id, context=context)
        fields2 = self.fields_get(cursor, user)
        for field in fields2:
            ftype = fields2[field]['type']

            if self._log_access \
                     and (field in (
                         'create_date',
                         'create_uid',
                         'write_date',
                         'write_uid',
                         )):
                del data[field]

            if field in default:
                data[field] = default[field]
            elif ftype == 'function':
                del data[field]
            elif ftype == 'many2one':
                try:
                    data[field] = data[field] and data[field][0]
                except:
                    pass
            elif ftype in ('one2many', 'one2one'):
                res = []
                rel = self.pool.get(fields2[field]['relation'])
                for rel_id in data[field]:
                    # the lines are first duplicated using the wrong (old) 
                    # parent but then are reassigned to the correct one thanks
                    # to the (4, ...)
                    res.append((4, rel.copy(cursor, user, rel_id,
                        context=context)))
                data[field] = res
            elif ftype == 'many2many':
                data[field] = [(6, 0, data[field])]
        del data['id']
        for i in self._inherits:
            del data[self._inherits[i]]
        return self.create(cursor, user, data)

    def read_string(self, cursor, user, object_id, langs, fields_names=None,
            context=None):
        res = {}
        res2 = {}
        self.pool.get('ir.model.access').check(cursor, user, 'ir.translation',
                'read')
        if fields_names is None:
            fields_names = self._columns.keys() + self._inherit_fields.keys()
        for lang in langs:
            res[lang] = {'code': lang}
            for field in fields_names:
                if field in self._columns:
                    res_trans = self.pool.get('ir.translation').\
                            _get_source(cursor, self._name + ',' + field,
                                    'field', lang)
                    if res_trans:
                        res[lang][field] = res_trans
                    else:
                        res[lang][field] = self._columns[field].string
        for table in self._inherits:
            cols = intersect(self._inherit_fields.keys(), fields_names)
            res2 = self.pool.get(table).read_string(cursor, user, object_id,
                    langs, cols, context)
        for lang in res2:
            if lang in res:
                res[lang] = {'code': lang}
            for field in res2[lang]:
                res[lang][field] = res2[lang][field]
        return res

    def write_string(self, cursor, user, object_id, langs, vals, context=None):
        self.pool.get('ir.model.access').check(cursor, user, 'ir.translation',
                'write')
        for lang in langs:
            for field in vals:
                if field in self._columns:
                    self.pool.get('ir.translation')._set_ids(cursor, user,
                            self._name + ',' + field, 'field', lang, [0],
                            vals[field])
        for table in self._inherits:
            cols = intersect(self._inherit_fields.keys(), vals)
            if cols:
                self.pool.get(table).write_string(cursor, user, object_id,
                        langs, vals, context)
        return True

    def check_recursion(self, cursor, user, ids, parent=None):
        if parent is None:
            parent = self._parent_name
        ids_parent = ids[:]
        while len(ids_parent):
            ids_parent2 = []
            for i in range((len(ids) / ID_MAX) + \
                    ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids_parent = ids_parent[ID_MAX * i:ID_MAX * (i + 1)]
                cursor.execute('SELECT distinct "' + parent + '" ' +
                    'FROM "' + self._table + '" ' +
                    'WHERE id IN ' \
                        '(' + ','.join([str(x) for x in sub_ids_parent]) + ')')
                ids_parent2.extend(filter(None,
                    [x[0] for x in cursor.fetchall()]))
            ids_parent = ids_parent2
            for i in ids_parent:
                if i in ids:
                    return False
        return True

orm = ORM
