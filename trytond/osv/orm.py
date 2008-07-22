#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
# -*- coding: utf-8 -*-
from trytond.netsvc import Logger, LOG_ERROR, LOG_WARNING, LocalService
import fields
from trytond.tools import Cache
import md5
import time
import traceback
import datetime
from lxml import etree
import copy

ID_MAX = 1000

def intersect(i, j):
    return [x for x in j if x in i]

def exclude(i, j):
    return [x for x in i if x not in j]


# TODO: execute an object method on BrowseRecordList
class BrowseRecordList(list):
    '''
    A list of BrowseRecord
    '''

    def __init__(self, lst, context=None):
        super(BrowseRecordList, self).__init__(lst)
        self.context = context

browse_record_list = BrowseRecordList


class BrowseRecord(object):
    '''
    A object that represents record defined by a ORM object.
    '''

    def __init__(self, cursor, user, object_id, table, cache, context=None):
        '''
        table : the object (inherited from orm)
        context : a dictionnary with an optionnal context
        '''
        self._cursor = cursor
        self._user = user
        self._id = object_id
        self._table = table
        self._table_name = self._table._name
        self._context = context
        self._language_cache = {}

        cache.setdefault(table._name, {})
        self._data = cache[table._name]
        if not object_id in self._data:
            self._data[object_id] = {'id': object_id}
        self._cache = cache

    def __getitem__(self, name):
        if name == 'id':
            return self._id
        if name == 'setLang':
            return self.setLang
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
                raise Exception('Error', 'Programming error: field "%s" ' \
                        'does not exist in object "%s"!' \
                        % (name, self._table._name))

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
                    if not j._obj in self._table.pool.object_name_list():
                        continue
                    obj = self._table.pool.get(j._obj)
                    if j._type in ('many2one',):
                        if not j._classic_write and data[i]:
                            if isinstance(data[i][0], (list, tuple)):
                                ids2 = data[i][0][0]
                            else:
                                ids2 = data[i][0]
                        else:
                            ids2 = data[i]
                        data[i] = BrowseRecord(self._cursor, self._user,
                                ids2, obj, self._cache,
                                context=self._context)
                    elif j._type in ('one2many', 'many2many') and len(data[i]):
                        data[i] = BrowseRecordList([BrowseRecord(self._cursor,
                            self._user, x, obj,
                            self._cache, context=self._context) for x in data[i]],
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

    def setLang(self, lang):
        self._context = self._context.copy()
        self._context['language'] = lang
        for table in self._cache:
            for obj_id in self._cache[table]:
                self._language_cache.setdefault(self._context['language'],
                        {}).setdefault(table, {}).update(
                                self._cache[table][obj_id])
                if lang in self._language_cache \
                        and table in self._language_cache[lang] \
                        and obj_id in self._language_cache[lang][table]:
                    self._cache[table][obj_id] = \
                            self._language_cache[lang][table][obj_id]
                else:
                    self._cache[table][obj_id] = {'id': obj_id}

browse_record = BrowseRecord


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
    _log_access = True
    _table = None
    _name = None
    _rec_name = 'name'
    _order_name = None # Use to force order field when sorting on Many2One
    _date_name = 'date'
    _order = None
    _inherits = {} #XXX remove from class instance
    _sequence = None
    _description = ''
    _auto = True
    _obj = None
    _sql = ''
    pool = None
    __columns = None
    __defaults = None

    def _reset_columns(self):
        self.__columns = None

    def _getcolumns(self):
        if self.__columns:
            return self.__columns
        res = {}
        for attr in dir(self):
            if attr in ('_columns', '_defaults'):
                continue
            if isinstance(getattr(self, attr), fields.Column):
                res[attr] = getattr(self, attr)
        self.__columns = res
        return res

    _columns = property(fget=_getcolumns)

    def _reset_defaults(self):
        self.__defaults = None

    def _getdefaults(self):
        if self.__defaults:
            return self.__defaults
        res = {}
        columns = self._columns.keys()
        columns += self._inherit_fields.keys()
        for column in columns:
            if getattr(self, 'default_' + column, False):
                res[column] = getattr(self, 'default_' + column)
        self.__defaults = res
        return res

    _defaults = property(fget=_getdefaults)

    def _field_create(self, cursor, module_name):
        cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                (self._name,))
        if not cursor.rowcount:
            # reference model in order to have a description
            # of its fonctionnality in custom_report
            cursor.execute("INSERT INTO ir_model " \
                    "(model, name, info) VALUES (%s, %s, %s)",
                    (self._name, self._description, self.__doc__))
            cursor.execute("SELECT id FROM ir_model WHERE model = %s",
                    (self._name,))
        (model_id,) = cursor.fetchone()

        cursor.execute('SELECT f.id AS id, f.name AS name, ' \
                    'f.field_description AS field_description, ' \
                    'f.ttype AS ttype, f.relation AS relation, ' \
                    'f.group_name AS group_name, f.view_load AS view_load ' \
                'FROM ir_model_field AS f, ir_model AS m ' \
                'WHERE f.model = m.id ' \
                    'AND m.model = %s ' \
                    'AND f.name in ' \
                        '(' + ','.join(['%s' for x in self._columns]) + ')',
                        (self._name,) + tuple(self._columns))
        columns = {}
        for column in cursor.dictfetchall():
            columns[column['name']] = column
        cursor.execute('SELECT id, name, src, type FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type IN (%s, %s, %s) ' \
                    'AND name IN ' \
                        '(' + ','.join(['%s' for x in self._columns]) + ')',
                        ('en_US', 'field', 'help', 'selection') + \
                                tuple([self._name + ',' + x \
                                    for x in self._columns]))
        trans_columns = {}
        trans_help = {}
        trans_selection = {}
        for trans in cursor.dictfetchall():
            if trans['type'] == 'field':
                trans_columns[trans['name']] = trans
            elif trans['type'] == 'help':
                trans_help[trans['name']] = trans
            elif trans['type'] == 'selection':
                trans_selection.setdefault(trans['name'], {})
                trans_selection[trans['name']][trans['src']] = trans
        for k in self._columns:
            field = self._columns[k]
            if k not in columns:
                cursor.execute("INSERT INTO ir_model_field " \
                        "(model, name, field_description, ttype, " \
                            "relation, group_name, view_load, help) " \
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (model_id, k, field.string, field._type,
                            field._obj or '', field.group_name or '',
                            (field.view_load and 'True') or 'False',
                            field.help))
            elif columns[k]['field_description'] != field.string \
                    or columns[k]['ttype'] != field._type \
                    or columns[k]['relation'] != (field._obj or '') \
                    or columns[k]['group_name'] != (field.group_name or '') \
                    or columns[k]['view_load'] != \
                        ((field.view_load and 'True') or 'False') \
                    or columns[k]['help'] != field.help:
                cursor.execute('UPDATE ir_model_field ' \
                        'SET field_description = %s, ' \
                            'ttype = %s, ' \
                            'relation = %s, ' \
                            'group_name = %s, ' \
                            'view_load = %s, ' \
                            'help = %s ' \
                        'WHERE id = %s ',
                        (field.string, field._type, field._obj or '',
                            field.group_name or '',
                            (field.view_load and 'True') or 'False',
                            field.help, columns[k]['id']))
            trans_name = self._name + ',' + k
            if trans_name not in trans_columns:
                if k not in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id'):
                    cursor.execute('INSERT INTO ir_translation ' \
                            '(name, lang, type, src, value, module) ' \
                            'VALUES (%s, %s, %s, %s, %s, %s)',
                            (trans_name, 'en_US', 'field',
                                field.string, '', module_name))
            elif trans_columns[trans_name]['src'] != field.string:
                cursor.execute('UPDATE ir_translation ' \
                        'SET src = %s ' \
                        'WHERE id = %s ',
                        (field.string, trans_columns[trans_name]['id']))
            if trans_name not in trans_help:
                if field.help:
                    cursor.execute('INSERT INTO ir_translation ' \
                            '(name, lang, type, src, value, module) ' \
                            'VALUES (%s, %s, %s, %s, %s, %s)',
                            (trans_name, 'en_US', 'help',
                                field.help, '', module_name))
            elif trans_help[trans_name]['src'] != field.help:
                cursor.execute('UPDATE ir_translation ' \
                        'SET src = %s ' \
                        'WHERE id = %s ',
                        (field.help, trans_help[trans_name]['id']))
            if hasattr(field, 'selection') \
                    and isinstance(field.selection, (tuple, list)):
                for (key, val) in field.selection:
                    if trans_name not in trans_selection \
                            or val not in trans_selection[trans_name]:
                        cursor.execute('INSERT INTO ir_translation ' \
                                '(name, lang, type, src, value, ' \
                                    'module) ' \
                                'VALUES (%s, %s, %s, %s, %s, %s)',
                                (trans_name, 'en_US', 'selection', val, '',
                                    module_name))

    def auto_init(self, cursor, module_name):
        self.init(cursor, module_name)
        self._auto_init(cursor, module_name)

    def init(self, cursor, module_name):
        cursor.execute('SELECT id, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name = %s',
                ('en_US', 'error', self._name))
        trans_error = {}
        for trans in cursor.dictfetchall():
            trans_error[trans['src']] = trans

        for error in self._error_messages.values():
            if error not in trans_error:
                cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module) ' \
                        'VALUES (%s, %s, %s, %s, %s, %s)',
                        (self._name, 'en_US', 'error', error, '', module_name))

    def _auto_init(self, cursor, module_name):
        logger = Logger()
        create = False

        self._field_create(cursor, module_name)
        if self._auto and not self.table_query():
            cursor.execute("SELECT relname FROM pg_class " \
                    "WHERE relkind in ('r', 'v') AND relname = %s",
                    (self._table,))
            if not cursor.rowcount:
                cursor.execute("CREATE TABLE \"%s\" " \
                        "(id SERIAL NOT NULL, " \
                            "PRIMARY KEY(id))" % self._table)
                create = True
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
                if isinstance(field, fields.One2Many):
                    cursor.execute("SELECT relname FROM pg_class " \
                            "WHERE relkind = 'r' AND relname = %s",
                            (field._obj,))
                    if cursor.fetchone():
                        cursor.execute("SELECT count(*) as c " \
                                "FROM pg_class c, pg_attribute a " \
                                "WHERE c.relname = %s " \
                                    "AND a.attname = %s " \
                                    "AND c.oid = a.attrelid",
                                    (field._obj, field._field))
                        (res,) = cursor.fetchone()
                        if not res:
                            cursor.execute("ALTER TABLE \"%s\" " \
                                    "ADD FOREIGN KEY (%s) " \
                                    "REFERENCES \"%s\" ON DELETE SET NULL" % \
                                    (self._obj, field._field, field._table))
                elif isinstance(field, fields.Many2Many):
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
                                    "ON DELETE CASCADE)" % \
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
                        if not isinstance(field, fields.Function):
                            # add the missing field
                            cursor.execute("ALTER TABLE \"%s\" " \
                                    "ADD COLUMN \"%s\" %s" % \
                                    (self._table, k, field.sql_type()[1]))
                            if isinstance(field, (fields.Integer, fields.Float)):
                                cursor.execute('ALTER TABLE "%s" ' \
                                        'ALTER COLUMN "%s" SET DEFAULT 0' % \
                                        (self._table, k))
                            # initialize it
                            if not create and k in self._defaults:
                                default = self._defaults[k](cursor, 1, {})
                                if not default:
                                    cursor.execute("UPDATE \"%s\" " \
                                            "SET \"%s\" = NULL" % \
                                            (self._table, k))
                                else:
                                    if isinstance(field, fields.Many2One) \
                                        and isinstance(default, (list, tuple)):
                                        default = default[0]
                                    cursor.execute("UPDATE \"%s\" " \
                                            "SET \"%s\" = '%s'" % \
                                            (self._table, k, default))
                            # and add constraints if needed
                            if isinstance(field, fields.Many2One):
                                # res.user and res.group are not present when ir initialize
                                if field._obj == 'res.user':
                                    ref = 'res_user'
                                elif field._obj == 'res.group':
                                    ref = 'res_group'
                                else:
                                    ref = self.pool.get(field._obj)._table
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
                                cursor.execute('SELECT id FROM "%s" ' \
                                        'WHERE "%s" IS NULL' % \
                                        (self._table, k))
                                if not cursor.rowcount:
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                            "ALTER COLUMN \"%s\" " \
                                                "SET NOT NULL" % \
                                                (self._table, k))
                                else:
                                    logger.notify_channel('init',
                                            LOG_WARNING,
                                            'Unable to set column %s ' \
                                                    'of table %s not null !\n'\
                                            'Try to re-run: ' \
                                        'trytond.py --update=module\n' \
                'If it doesn\'t work, update records and execute manually:\n' \
                'ALTER TABLE %s ALTER COLUMN %s SET NOT NULL' % \
                                        (k, self._table, self._table, k))
                    elif len(res)==1:
                        f_pg_def = res[0]
                        f_pg_type = f_pg_def['typname']
                        f_pg_size = f_pg_def['size']
                        f_pg_notnull = f_pg_def['attnotnull']
                        if isinstance(field, fields.Function):
                            logger.notify_channel('init', LOG_WARNING,
                                    'column %s (%s) in table %s was converted '\
                                            'to a function !\n' \
                        'You should remove this column from your database.' % \
                                (k, field.string, self._table))
                            f_obj_type = None
                        else:
                            f_obj_type = field.sql_type() \
                                    and field.sql_type()[0]
                        if f_obj_type:
                            if f_pg_type != f_obj_type:
                                logger.notify_channel('init',
                                        LOG_WARNING,
                                        "column '%s' in table '%s' must " \
                                        "change type %s -> %s!" % \
                                        (k, self._table, f_pg_type, f_obj_type,))
                            if f_pg_type == 'varchar' \
                                    and field._type == 'char' \
                                    and (f_pg_size != field.size \
                                    and not (f_pg_size == -5 and field.size is None)):
                                # columns with the name 'type' cannot be changed
                                # for an unknown reason?!
                                if k != 'type':
                                    if field.size and f_pg_size > field.size:
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
                                            "ADD COLUMN \"%s\" %s" % \
                                            (self._table, k, field.sql_type()[1]))
                                    cursor.execute("UPDATE \"%s\" " \
                                "SET \"%s\" = temp_change_size::%s" % \
                                        (self._table, k, field.sql_type()[1]))
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                            "DROP COLUMN temp_change_size" % \
                                            (self._table,))
                            # if the field is required
                            # and hasn't got a NOT NULL constraint
                            if field.required and f_pg_notnull == 0:
                                # set the field to the default value if any
                                if self._defaults.has_key(k):
                                    default = self._defaults[k](cursor,
                                            1, {})
                                    if default:
                                        if isinstance(field, fields.Many2One) \
                                            and isinstance(default, (list, tuple)):
                                            default = default[0]
                                        cursor.execute("UPDATE \"%s\" " \
                                        "SET \"%s\" = '%s' WHERE %s is NULL" % \
                                            (self._table, k, default, k))
                                cursor.execute('SELECT "%s" FROM "%s" ' \
                                        'WHERE "%s" IS NULL' % \
                                        (k, self._table, k))
                                if not cursor.rowcount:
                                    # add the NOT NULL constraint
                                    cursor.execute("ALTER TABLE \"%s\" " \
                                        "ALTER COLUMN \"%s\" SET NOT NULL" % \
                                        (self._table, k))
                                else:
                                    logger.notify_channel('init',
                                            LOG_WARNING,
                                            'unable to set ' \
                    'a NOT NULL constraint on column %s of the %s table !\n' \
'If you want to have it, you should update the records and execute manually:\n'\
                            'ALTER TABLE %s ALTER COLUMN %s SET NOT NULL' % \
                                        (k, self._table, self._table, k))
                            elif not field.required and f_pg_notnull == 1:
                                cursor.execute("ALTER TABLE \"%s\" " \
                                        "ALTER COLUMN \"%s\" DROP NOT NULL" % \
                                        (self._table, k))
                            cursor.execute("SELECT indexname FROM pg_indexes " \
                    "WHERE indexname = '%s_%s_index' AND tablename = '%s'" % \
                                    (self._table, k, self._table))
                            res = cursor.dictfetchall()
                            if not res and field.select:
                                cursor.execute("CREATE INDEX \"%s_%s_index\" " \
                                        "ON \"%s\" (\"%s\")" % \
                                        (self._table, k, self._table, k))
                            if res and not field.select:
                                cursor.execute("DROP INDEX \"%s_%s_index\"" % \
                                        (self._table, k))
                            if isinstance(field, fields.Many2One):
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
                    else:
                        # TODO add error message
                        logger.notify_channel('init', LOG_ERROR, '')
        else:
            cursor.execute("SELECT relname FROM pg_class " \
                    "WHERE relkind in ('r', 'v') AND relname = %s",
                    (self._table,))
            create = not bool(cursor.fetchone())

        for (key, con, msg) in self._sql_constraints:
            cursor.execute("SELECT conname FROM pg_constraint " \
                    "WHERE conname = %s", ((self._table + '_' + key),))
            if not cursor.dictfetchall():
                try:
                    cursor.execute('ALTER TABLE \"%s\" ' \
                            'ADD CONSTRAINT \"%s_%s\" %s' % \
                            (self._table, self._table, key, con,))
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

        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                cursor.execute('SELECT id FROM "%s" ' \
                        'WHERE "%s" IS NULL OR "%s" IS NULL '\
                            'OR "%s" = 0 OR "%s" = 0'% \
                        (self._table, field.left, field.right,
                            field.left, field.right))
                if cursor.rowcount:
                    self._rebuild_tree(cursor, 0, k, False, 0)

    def __init__(self):
        self._rpc_allowed = [
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
                'export_data',
                'search_count',
                'search_read',
                ]
        self._sql_constraints = []
        self._constraints = []
        self._inherit_fields = []
        self._order = [('id', 'ASC')]
        self._error_messages = {
            'delete_xml_record': 'You are not allowed to delete this record.',
            'xml_record_desc': "This record is part of the base configuration.",
            'write_xml_record': 'You are not allowed to modify this record.'}
        # reinit the cache on _columns and _defaults
        self.__columns = None
        self.__defaults = None

        if not self._table:
            self._table = self._name.replace('.', '_')
        if not self._description:
            self._description = self._name

        self._inherits_reload()
        if not self._sequence:
            self._sequence = self._table+'_id_seq'

        if self._log_access:
            self.create_uid = fields.Many2One('res.user',
                    'Create User', required=True, readonly=True)
            self.create_date = fields.DateTime('Create Date',
                    required=True, readonly=True)
            self.write_uid = fields.Many2One('res.user',
                       'Write User', readonly=True)
            self.write_date = fields.DateTime(
                    'Write Date', readonly=True)
        self.id = fields.Integer('ID', readonly=True)
        # reinit the cache on _columns
        self.__columns = None

        for name in self._columns:
            if isinstance(self._columns[name], (fields.Selection, fields.Reference)) \
                    and not isinstance(self._columns[name].selection, (list, tuple)) \
                    and self._columns[name].selection not in self._rpc_allowed:
                self._rpc_allowed.append(self._columns[name].selection)
            if self._columns[name].on_change:
                on_change = 'on_change_' + name
                if on_change not in self._rpc_allowed:
                    self._rpc_allowed.append(on_change)

        for k in self._defaults:
            assert (k in self._columns) or (k in self._inherit_fields), \
            'Default function defined in %s but field %s does not exist!' % \
                (self._name, k,)

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

    def default_create_uid(self, cursor, user, context=None):
        "Default value for uid field"
        return user

    def default_create_date(self, cursor, user, context=None):
        "Default value for create_date field"
        return datetime.datetime.today()

    def table_query(self, context=None):
        '''
        Return None if the table object is a real table in the database
        or return a tuple wiht the query for the table object and the arguments
        '''
        return None

    def raise_user_error(self, cursor, error, error_args=None,
            error_description='', error_description_args=None, context=None):
        '''
        Raise an exception that will be display as an error message
        in the client.

        :param cursor: the database cursor
        :param error: the key of the dictionary _error_messages used
            for error message
        :param error_args: the arguments that will be used
            for "%"-based substitution
        :param error_description: the key of the dictionary
            _error_messages used for error description
        :param error_description_args: the arguments that will be used
            for "%"-based substitution
        :param context: the context in which the language key will
            be used for translation
        '''
        translation_obj = self.pool.get('ir.translation')

        if context is None:
            context = {}

        error = self._error_messages.get(error, error)

        res = translation_obj._get_source(cursor, self._name, 'error',
                context.get('language', 'en_US'), error)
        if res:
            error = res

        if error_args:
            error = error % error_args

        if error_description:
            error_description = self._error_messages.get(error_description,
                    error_description)

            res = translation_obj._get_source(cursor, self._name, 'error',
                    context.get('language', 'en_US'), error_description)
            if res:
                error_description = res

            if error_description_args:
                error_description = error_description % error_description_args

            raise Exception('UserError', error, error_description)
        raise Exception('UserError', error)

    def browse(self, cursor, user, ids, context=None):
        '''
        Return a browse a BrowseRecordList for the ids
            or BrowseRecord if ids is a integer.
        '''
        cache = {}
        # need to accepts ints and longs because ids coming from a method
        # launched by button in the interface have a type long...
        if isinstance(ids, (int, long)):
            return BrowseRecord(cursor, user, ids, self, cache,
                    context=context)
        return BrowseRecordList([BrowseRecord(cursor, user, x, self, cache,
            context=context) for x in ids], context)

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
        '''
        Return list of list of values for each ids.
        The list of values follow the fields_names.
        Relational fields are defined with '/' at any deep.
        '''
        fields_names = [x.split('/') for x in fields_names]
        datas = []
        for row in self.browse(cursor, user, ids, context):
            datas += self.__export_row(cursor, user, row, fields_names, context)
        return datas

    # TODO: Send a request with the result and multi-thread !
    def import_data(self, cursor, user, fields_names, datas, context=None):
        '''
        Create record for each values in datas.
        The fields name of values must be defined in fields_names.
        '''
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

            # Import normal fields_names
            for i in range(len(fields_names)):
                if i >= len(line):
                    raise Exception('ImportError',
                            'Please check that all your lines have %d cols.' % \
                            (len(fields_names),))
                field = fields_names[i]
                if (len(field) == len(prefix) + 1) \
                        and field[len(prefix)].endswith(':id'):
                    res_id = False
                    if line[i]:
                        if fields_def[field[len(prefix)][:-3]]['type'] \
                                == 'many2many':
                            res_id = []
                            for word in line[i].split(','):
                                module, xml_id = word.rsplit('.', 1)
                                ir_model_data_obj = \
                                        self.pool.get('ir.model.data')
                                new_id = ir_model_data_obj._get_id(cursor,
                                        user, module, xml_id)
                                res_id2 = ir_model_data_obj.read(cursor, user,
                                        [new_id], ['res_id'])[0]['res_id']
                                if res_id2:
                                    res_id.append(res_id2)
                            if len(res_id):
                                res_id = [('set', res_id)]
                        else:
                            module, xml_id = line[i].rsplit('.', 1)
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
                            sel = getattr(self, fields_def[field[len(prefix)]]\
                                    ['selection'])(cursor, user, context)
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
                                res = [('set', res)]
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
                (newrow, max2, warning2, translate2) = res
                nbrmax = max(nbrmax, max2)
                warning = warning + warning2
                reduce(lambda x, y: x and y, newrow)
                row[field] = (reduce(lambda x, y: x or y, newrow.values()) and \
                        [('create', newrow)]) or []
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

                    (newrow, max2, warning2, translate2) = \
                            process_liness(self, datas, prefix+[field], newfd,
                                    position + i)
                    warning = warning + warning2
                    if reduce(lambda x, y: x or y, newrow.values()):
                        row[field].append(('create', newrow))
                    i += max2
                    nbrmax = max(nbrmax, i)

            if len(prefix) == 0:
                for i in range(max(nbrmax, 1)):
                    datas.pop(0)
            result = (row, nbrmax, warning, translate)
            return result

        fields_def = self.fields_get(cursor, user, context=context)
        done = 0

        while len(datas):
            res = {}
            try:
                (res, other, warning, translate) = \
                        process_liness(self, datas, [], fields_def)
                if warning:
                    cursor.rollback()
                    return (-1, res, warning, '')
                new_id = self.create(cursor, user, res, context=context)
                for lang in translate:
                    context2 = context.copy()
                    context2['language'] = lang
                    self.write(cursor, user, new_id, translate[lang],
                            context=context2)
            except Exception, exp:
                logger.notify_channel("import", LOG_ERROR, exp)
                cursor.rollback()
                return (-1, res, exp[0], warning)
            done += 1
        return (done, 0, 0, 0)

    def read(self, cursor, user, ids, fields_names=None, context=None,
            load='_classic_read'):
        '''
        Return list of a dict for each ids or just a dict if ids is an integer.
        The dict have fields_names as keys.
        '''
        self.pool.get('ir.model.access').check(cursor, user, self._name, 'read')
        if not fields_names:
            fields_names = self._columns.keys() + \
                    exclude(self._inherit_fields.keys(), self._columns.keys())
        select = ids
        if isinstance(ids, (int, long)):
            select = [ids]
        result =  self._read_flat(cursor, user, select, fields_names, context,
                load)
        for i in result:
            for key, j in i.items():
                if j is None:
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

        if fields_names is None:
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
        table_query = ''
        table_args = []
        if self.table_query(context):
            table_query, table_args = self.table_query(context)
            table_query = '(' + table_query + ') AS '
        if len(fields_pre) :
            fields_pre2 = [(x in ('create_date', 'write_date')) \
                    and ('date_trunc(\'second\', ' + x + ') as ' + x) \
                    or '"' + x + '"' for x in fields_pre]
            for i in range((len(ids) / ID_MAX) + ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids = ids[ID_MAX * i:ID_MAX * (i + 1)]
                if domain1:
                    cursor.execute(('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM ' + table_query + '\"' + self._table +'\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join([str(x) for x in sub_ids]) + ')'\
                            ' AND (' + domain1 + ') ORDER BY ' + \
                            ','.join([self._table + '.' + x[0] + ' ' + x[1] \
                            for x in self._order])),
                            table_args + domain2)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('ValidateError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                else:
                    cursor.execute('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM ' + table_query + '\"' + self._table + '\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join([str(x) for x in sub_ids]) + ')'\
                            ' ORDER BY ' + \
                            ','.join([self._table + '.' + x[0] + ' ' + x[1] \
                            for x in self._order]), table_args)
                res.extend(cursor.dictfetchall())
        else:
            res = [{'id': x} for x in ids]

        for field in fields_pre:
            if self._columns[field].translate:
                ids = [x['id'] for x in res]
                res_trans = self.pool.get('ir.translation')._get_ids(cursor,
                        self._name + ',' + field, 'model',
                        context.get('language', False) or 'en_US', ids)
                for i in res:
                    i[field] = res_trans.get(i['id'], False) or i[field]

        for table in self._inherits:
            col = self._inherits[table]
            cols = intersect(self._inherit_fields.keys(), fields_names)
            cols = exclude(cols, self._columns.keys())
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
            if not getattr(self, field[0])(cursor, user, ids):
                if len(field) > 1:
                    field_error += field[2]
                field_err_str.append(field[1])
        if len(field_err_str):
            raise Exception('UserError',
                    ('\n'.join(field_err_str), ','.join(field_error)))

    def default_get(self, cursor, user, fields_names, context=None):
        '''
        Return a dict with the default values for each fields_names.
        '''
        value = {}
        # get the default values for the inherited fields
        for i in self._inherits.keys():
            value.update(self.pool.get(i).default_get(cursor, user,
                fields_names, context=context))

        # get the default values defined in the object
        for field in fields_names:
            if field in self._defaults:
                value[field] = self._defaults[field](cursor, user, context)
            if field in self._columns:
                if isinstance(self._columns[field], fields.Property):
                    property_obj = self.pool.get('ir.property')
                    value[field] = property_obj.get(cursor, user, field,
                            self._name)
                    if self._columns[field]._type in ('many2one',) \
                            and value[field]:
                        obj = self.pool.get(self._columns[field]._obj)
                        if isinstance(value[field], (int, long)):
                            value[field] = obj.name_get(cursor, user,
                                    value[field], context=context)[0]

        # get the default values set by the user and override the default
        # values defined in the object
        ir_default_obj = self.pool.get('ir.default')
        defaults = ir_default_obj.get_default(cursor, user,
                self._name, False, context=context)
        for field, field_value in defaults.items():
            if field in fields_names:
                fld_def = (field in self._columns) and self._columns[field] \
                        or self._inherit_fields[field][2]
                if fld_def._type in ('many2one',):
                    obj = self.pool.get(fld_def._obj)
                    if not obj.search(cursor, user, [('id', '=', field_value)]):
                        continue
                    if isinstance(field_value, (int, long)):
                        field_value = obj.name_get(cursor, user, field_value,
                                context=context)[0]
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
                    for i in range(len(field_value or [])):
                        field_value2.append({})
                        for field2 in field_value[i]:
                            if obj._columns[field2]._type \
                                    in ('many2one',):
                                obj2 = self.pool.get(obj._columns[field2]._obj)
                                if not obj2.search(cursor, user,
                                        [('id', '=', field_value[i][field2])]):
                                    continue
                                if isinstance(field_value[i][field2],
                                        (int, long)):
                                    field_value[i][field2] = obj2.name_get(
                                            cursor, user,
                                            field_value[i][field2],
                                            context=context)[0]
                            # TODO add test for many2many and one2many
                            field_value2[i][field2] = field_value[i][field2]
                    field_value = field_value2
                value[field] = field_value
        value = self._default_on_change(cursor, user, value, context=context)
        return value

    def _default_on_change(self, cursor, user, value, context=None):
        res = value.copy()
        val = {}
        for i in self._inherits.keys():
            val.update(self.pool.get(i)._default_on_change(cursor, user,
                value, context=context))
        for field in value.keys():
            if field in self._columns:
                if self._columns[field].on_change:
                    args = {}
                    for arg in self._columns[field].on_change:
                        args[arg] = value.get(arg, False)
                        if arg in self._columns \
                                and self._columns[arg]._type == 'many2one':
                            if isinstance(args[arg], (list, tuple)):
                                args[arg] = args[arg][0]
                    val.update(getattr(self, 'on_change_' + field)(cursor, user,
                        [], args, context=context))
                if self._columns[field]._type in ('one2many',):
                    obj = self.pool.get(self._columns[field]._obj)
                    for val2 in res[field]:
                        val2.update(obj._default_on_change(cursor, user,
                            val2, context=context))
        res.update(val)
        return res

    def unlink(self, cursor, user, ids, context=None):
        '''
        Remove the ids.
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if self.table_query(context):
            return True
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
                    raise Exception('ConcurrencyException',
                            'This record was modified in the meanwhile')
            del context['read_delta']

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'unlink')

        cursor.execute(
            "SELECT id FROM wkf_instance "\
                "WHERE res_id IN (" + ",".join(["%s" for i in ids]) + ") "\
                "AND res_type = %s AND state != 'complete'",
            ids + [self._name])
        if cursor.rowcount != 0:
            raise Exception('UserError',
                    'You cannot delete a record with a running workflow.')

        wf_service = LocalService("workflow")
        for obj_id in ids:
            wf_service.trg_delete(user, self._name, obj_id, cursor)

        if not self.check_xml_record(cursor, user, ids, None, context=context):
            self.raise_user_error(cursor, 'delete_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)

        #cursor.execute('select * from ' + self._table + \
        #       ' where id in ('+str_d+')', ids)
        #res = cursor.dictfetchall()
        #for key in self._inherits:
        #    ids2 = [x[self._inherits[key]] for x in res]
        #    self.pool.get(key).unlink(cursor, user, ids2)

        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name)
        if domain1:
            domain1 = ' AND (' + domain1 + ') '
        for i in range((len(ids) / ID_MAX) + \
                ((len(ids) % ID_MAX) and 1 or 0)):
            sub_ids = ids[ID_MAX * i:ID_MAX * (i + 1)]
            str_d = ','.join(('%s',) * len(sub_ids))
            if domain1:
                cursor.execute('SELECT id FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ') ' + domain1,
                        sub_ids + domain2)
                if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                    raise Exception('AccessError',
                            'You try to bypass an access rule ' \
                                '(Document type: %s).' % self._description)

            if domain1:
                cursor.execute('DELETE FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ') ' + domain1,
                        sub_ids + domain2)
            else:
                cursor.execute('DELETE FROM "'+self._table+'" ' \
                        'WHERE id IN (' + str_d + ')', sub_ids)
        return True

    def check_xml_record(self, cursor, user, ids, values, context=None):
        """
        Check if a list of records and their corresponding fields are
        originating from xml data. This is used by write and delete
        functions: if the return value is True the records can be
        written/deleted, False otherwise. The default behaviour is to
        forbid all modification on records/fields originating from
        xml. Values is the dictionary of written values. If values is
        equal to None, no field by field check is performed, False is
        return has soon has one of the record comes from the xml.
        """
        # Allow root user to update/delete
        if user == 0:
            return True
        cursor.execute('SELECT values '\
                         'FROM ir_model_data '\
                         'WHERE model = %s '\
                         'AND db_id in (' + ','.join('%s' for x in ids)+ ') ',
                       [self._name]+ids)
        if cursor.rowcount == 0:
            return True
        if values == None:
            return False
        for line in cursor.fetchall():
            xml_values = eval(line[0])
            for key, val in values.iteritems():
                if key in xml_values and val != xml_values[key]:
                    return False
        return True

    # TODO: Validate
    def write(self, cursor, user, ids, vals, context=None):
        '''
        Update ids with the content of vals.
        vals is a dict with fields name as keys.
        '''
        if context is None:
            context = {}
        if not ids:
            return True
        if self.table_query(context):
            return True

        vals = vals.copy()

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
                            raise Exception('ConcurrencyException',
                                    'This record was modified in the meanwhile')
            del context['read_delta']

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'write')

        if 'write_uid' in vals:
            del vals['write_uid']
        if 'write_date' in vals:
            del vals['write_date']
        if 'id' in vals:
            del vals['id']

        #for v in self._inherits.values():
        #    assert v not in vals, (v, vals)
        upd0 = []
        upd1 = []
        upd_todo = []
        updend = []
        direct = []
        for field in vals:
            if field in self._columns:
                if self._columns[field]._classic_write:
                    if (not self._columns[field].translate) \
                            or context.get('language', 'en_US') == 'en_US':
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
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
                else:
                    if val not in dict(getattr(self,
                        self._columns[field].selection)(
                        cursor, user, context=context)):
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))

        if not self.check_xml_record(cursor, user, ids, vals, context=context):
            self.raise_user_error(cursor, 'write_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)

        if self._log_access:
            upd0.append('write_uid = %s')
            upd0.append('write_date = now()')
            upd1.append(user)

        if len(upd0):
            domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor,
                    user, self._name)
            if domain1:
                domain1 = ' AND (' + domain1 + ') '
            for i in range((len(ids) / ID_MAX) + \
                    ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids = ids[ID_MAX * i:ID_MAX * (i + 1)]
                ids_str = ','.join([str(x) for x in sub_ids])
                if domain1:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE id IN (' + ids_str + ') ' + domain1, domain2)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                else:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE id IN (' + ids_str + ')')
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('AccessError',
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

            for field in direct:
                if self._columns[field].translate:
                    self.pool.get('ir.translation')._set_ids(cursor, user,
                            self._name + ',' + field, 'model',
                            context.get('language','en_US'), ids, vals[field])

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

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                if field.left in vals or field.right in vals:
                    raise Exception('ValidateError', 'You can not update fields: ' \
                            '"%s", "%s"' % (field.left, field.right))
                if k in vals:
                    for object_id in ids:
                        self._update_tree(cursor, user, object_id, k,
                                field.left, field.right)

        # Restart rule cache
        if self.pool.get('ir.rule.group').search(cursor, 0, [
            ('model.model', '=', self._name),
            ], context=context):
            self.pool.get('ir.rule').domain_get(cursor.dbname)

        wf_service = LocalService("workflow")
        for obj_id in ids:
            wf_service.trg_write(user, self._name, obj_id, cursor)
        return True

    def __clean_defaults(self, defaults):
        vals = {}
        for field in defaults.keys():
            fld_def = (field in self._columns) and self._columns[field] \
                    or self._inherit_fields[field][2]
            if fld_def._type in ('many2one',):
                if isinstance(defaults[field], (list, tuple)):
                    vals[field] = defaults[field][0]
                else:
                    vals[field] = defaults[field]
            elif fld_def._type in ('one2many',):
                obj = self.pool.get(self._columns[field]._obj)
                vals[field] = []
                for defaults2 in defaults[field]:
                    vals2 = obj.__clean_defaults(defaults2)
                    vals[field].append(('create', vals2))
            elif fld_def._type in ('many2many',):
                vals[field] = [('set', defaults[field])]
            else:
                vals[field] = defaults[field]
        return vals

    def create(self, cursor, user, vals, context=None):
        """
        Create a record with the content of vals.
        vals is a dict with fields name as key.
        """
        if self.table_query(context):
            return False

        vals = vals.copy()

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'create')

        if 'create_uid' in vals:
            del vals['create_uid']
        if 'create_date' in vals:
            del vals['create_date']
        if 'id' in vals:
            del vals['id']

        default = []
        avoid_table = []
        for (i, j) in self._inherits.items():
            if j in vals:
                avoid_table.append(i)
        for i in self._columns.keys(): # + self._inherit_fields.keys():
            if not i in vals \
                    and i not in ('create_uid', 'create_date',
                            'write_uid', 'write_date'):
                default.append(i)
        for i in self._inherit_fields.keys():
            if (not i in vals) \
                    and (not self._inherit_fields[i][0] in avoid_table):
                default.append(i)

        if len(default):
            defaults = self.default_get(cursor, user, default, context)
            vals.update(self.__clean_defaults(defaults))

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
            new_id = self.pool.get(table).create(cursor, user, tocreate[table],
                    context=context)
            upd0 += ',' + self._inherits[table]
            upd1 += ',%s'
            upd2.append(new_id)

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
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
                else:
                    if val not in dict(getattr(self,
                        self._columns[field].selection)(
                        cursor, user, context=context)):
                        raise Exception('ValidateError',
                        'The value "%s" for the field "%s" ' \
                                'is not in the selection' % \
                                (val, field))
        if self._log_access:
            upd0 += ', create_uid, create_date'
            upd1 += ', %s, now()'
            upd2.append(user)
        cursor.execute('INSERT INTO "' + self._table + '" ' \
                '(id' + upd0 + ') ' \
                'VALUES (' + str(id_new) + upd1 + ')', tuple(upd2))
        upd_todo.sort(lambda x, y: self._columns[x].priority - \
                self._columns[y].priority)
        for field in upd_todo:
            self._columns[field].set(cursor, self, id_new, field, vals[field],
                    user=user, context=context)

        self._validate(cursor, user, [id_new])

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                self._update_tree(cursor, user, id_new, k, field.left, field.right)

        wf_service = LocalService("workflow")
        wf_service.trg_create(user, self._name, id_new, cursor)
        return id_new

    def fields_get(self, cursor, user, fields_names=None, context=None):
        """
        Returns the definition of each field in the object
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
        write_access = model_access_obj.check(cursor, user, self._name, 'write',
                raise_exception=False)
        if self.table_query(context):
            write_access = False

        #Add translation to cache
        trans_args = []
        for field in self._columns.keys():
            trans_args.append((self._name + ',' + field, 'field',
                context.get('language', 'en_US'), None))
            trans_args.append((self._name + ',' + field, 'help',
                context.get('language', 'en_US'), None))
            if hasattr(self._columns[field], 'selection'):
                if isinstance(self._columns[field].selection, (tuple, list)):
                    sel = self._columns[field].selection
                    for (key, val) in sel:
                        trans_args.append((self._name + ',' + field,
                            'selection', context.get('language', 'en_US'),
                            val))
        translation_obj._get_sources(cursor, trans_args)

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
                    'on_change',
                    'add_remove',
                    ):
                if getattr(self._columns[field], arg, False):
                    res[field][arg] = getattr(self._columns[field], arg)
            if not write_access:
                res[field]['readonly'] = True
                if res[field].get('states') and \
                        'readonly' in res[field]['states']:
                    res[field]['states'] = res[field]['states'].copy()
                    del res[field]['states']['readonly']
            for arg in ('digits', 'invisible'):
                if hasattr(self._columns[field], arg) \
                        and getattr(self._columns[field], arg):
                    res[field][arg] = getattr(self._columns[field], arg)
            if isinstance(self._columns[field], fields.Function) \
                    and not self._columns[field].order_field:
                res[field]['sortable'] = False

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
                    res[field]['selection'] = self._columns[field].selection
            if res[field]['type'] in (
                    'one2many',
                    'many2many',
                    'many2one',
                    ):
                res[field]['relation'] = self._columns[field]._obj
                res[field]['domain'] = self._columns[field]._domain
                res[field]['context'] = self._columns[field]._context
            if res[field]['type'] == 'one2many':
                res[field]['relation_field'] = self._columns[field]._field

        if fields_names:
            # filter out fields which aren't in the fields_names list
            for i in res.keys():
                if i not in fields_names:
                    del res[i]
        return res

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        """
        Overload this method if you need a window title
        which depends on the context
        """
        return False

    def __view_look_dom(self, cursor, user, element, type, context=None):
        if context is None:
            context = {}
        result = False
        fields_attrs = {}
        childs = True
        fields_width = {}
        if type == 'tree':
            viewtreewidth_obj = self.pool.get('ir.ui.view_tree_width')
            viewtreewidth_ids = viewtreewidth_obj.search(cursor, user, [
                ('model', '=', self._name),
                ('user', '=', user),
                ], context=context)
            for viewtreewidth in viewtreewidth_obj.browse(cursor, user,
                    viewtreewidth_ids, context=context):
                fields_width[viewtreewidth.field] = viewtreewidth.width
        if element.tag in ('field', 'label', 'separator', 'group'):
            for attr in ('name', 'icon'):
                if element.get(attr):
                    attrs = {}
                    try:
                        if element.get(attr) in self._columns:
                            relation = self._columns[element.get(attr)]._obj
                        else:
                            relation = self._inherit_fields[element.get(attr)][2]._obj
                    except:
                        relation = False
                    if relation and element.tag == 'field':
                        childs = False
                        views = {}
                        for field in element:
                            if field.tag in ('form', 'tree', 'graph'):
                                field2 = copy.copy(field)
                                xarch, xfields = self.pool.get(relation
                                        )._view_look_dom_arch(cursor, user, field2,
                                                field.tag, context)
                                views[field.tag] = {
                                    'arch': xarch,
                                    'fields': xfields
                                }
                                element.remove(field)
                        attrs = {'views': views}
                    fields_attrs[element.get(attr)] = attrs
            if element.get('name') in fields_width:
                element.set('width', str(fields_width[element.get('name')]))

        if element.tag in ('form', 'tree', 'graph'):
            value = ''
            if element.get('string'):
                value = element.get('string')
            result = self.view_header_get(cursor, user, value, element.tag,
                    context)
            if result:
                element.set('string', result)

        # translate view
        translation_obj = self.pool.get('ir.translation')
        if ('language' in context) and not result:
            if element.get('string'):
                trans = translation_obj._get_source(cursor,
                        self._name, 'view', context['language'],
                        element.get('string'))
                if trans:
                    element.set('string', trans)
            if element.get('sum'):
                trans = translation_obj._get_source(cursor,
                        self._name, 'view', context['language'],
                        element.get('sum'))
                if trans:
                    element.set('sum', trans)
        # Add view for properties !
        if element.tag == 'properties':
            parent = element.getparent()
            models = ["'" + x + "'" for x in  [self._name] + \
                    self._inherits.keys()]
            cursor.execute('SELECT f.name AS name, ' \
                        'f.group_name AS group_name ' \
                    'FROM ir_model_field AS f, ir_model AS m ' \
                    'WHERE f.model = m.id ' \
                        'AND m.model in (' + ','.join(models) + ') ' \
                        'AND f.view_load ORDER BY f.group_name, f.id')
            oldgroup = None
            for fname, gname in cursor.fetchall():
                if oldgroup != gname:
                    child = etree.Element('separator')
                    child.set('string', gname)
                    child.set('colspan', '4')
                    oldgroup = gname
                    parent.insert(parent.index(element), child)

                child = etree.Element('label')
                child.set('name', fname)
                parent.insert(parent.index(element), child)
                child = etree.Element('field')
                child.set('name', fname)
                parent.insert(parent.index(element), child)
            parent.remove(element)
            element = parent

        if childs:
            for field in element:
                fields_attrs.update(self.__view_look_dom(cursor, user, field,
                    type, context))
        return fields_attrs

    def _view_look_dom_arch(self, cursor, user, tree, type, context=None):
        tree_root = tree.getroottree().getroot()
        fields_def = self.__view_look_dom(cursor, user, tree_root, type,
                context=context)
        arch = etree.tostring(tree, encoding='utf-8')
        fields2 = self.fields_get(cursor, user, fields_def.keys(), context)
        for field in fields_def:
            if field in fields2:
                fields2[field].update(fields_def[field])
        return arch, fields2

    def fields_view_get(self, cursor, user, view_id=None, view_type='form',
            context=None, toolbar=False, hexmd5=None):
        '''
        Return a dict with keys:
            - arch: the xml description of the view.
            - fields: a dict with the definition of each fields.
            - toolbar: if toolbar is True, a dict with 'print', 'action', 'relate'
                keyword action defintion for the view.
            - md5: the check sum of the above dict that will be used for caching.
        view_id can specify the id of the view, if empty the system
            will select the first view
        view_type specify the type of the view if view_id is empty
        If hexmd5 is fill, the function will return True if the view have the same
            md5 or the dict.
        '''

        def _inherit_apply(src, inherit):

            def _find(tree, element):
                if element.tag == 'xpath':
                    res = tree.xpath(element.get('expr'))
                    if res:
                        return res[0]
                return None

            tree_src = etree.fromstring(src)
            tree_inherit = etree.fromstring(inherit)
            root_inherit = tree_inherit.getroottree().getroot()
            for element2 in root_inherit:
                element = _find(tree_src, element2)
                if element is not None:
                    pos = element2.get('position', 'inside')
                    if pos == 'replace':
                        parent = element.getparent()
                        parent.remove(element)
                        parent.extend(element2.getchildren())
                    elif pos == 'inside':
                        element.extend(element2.getchildren())
                    elif pos == 'after':
                        parent = element.getparent()
                        next = element.getnext()
                        if next is not None:
                            for child in element2:
                                index = parent.index(next)
                                parent.insert(index, child)
                        else:
                            parent.extend(element2.getchildren())
                    elif pos == 'before':
                        parent = element.getparent()
                        for child in element2:
                            index = parent.index(element)
                            parent.insert(index, child)
                    else:
                        raise AttributeError('Unknown position ' \
                                'in inherited view %s!' % pos)
                else:
                    raise AttributeError('Couldn\'t find tag in parent view!')
            return etree.tostring(tree_src, encoding='utf-8')

        result = {'type': view_type, 'model': self._name}

        test = True
        model = True
        sql_res = False
        while test:
            if view_id:
                where = (model and (" and model='%s'" % (self._name,))) or ''
                cursor.execute('SELECT arch, name, field_childs, id, type, ' \
                            'inherit ' \
                        'FROM ir_ui_view WHERE id = %s ' + where, (view_id,))
            else:
                cursor.execute('SELECT arch, name, field_childs, id, type, ' \
                        'inherit ' \
                        'FROM ir_ui_view ' \
                        'WHERE model = %s AND type = %s AND inherit IS NULL ' \
                        'ORDER BY priority',
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
                        'WHERE inherit = %s AND model = %s ' \
                        'ORDER BY priority', (inherit_id, self._name))
                sql_inherit = cursor.fetchall()
                for (inherit, view_id) in sql_inherit:
                    result = _inherit_apply(result, inherit)
                    result = _inherit_apply_rec(result, view_id)
                return result

            result['arch'] = _inherit_apply_rec(result['arch'], sql_res[3])

            result['name'] = sql_res[1]
            result['field_childs'] = sql_res[2] or False
        # otherwise, build some kind of default view
        else:
            if view_type == 'form':
                res = self.fields_get(cursor, user, context=context)
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<form string="%s">''' % (self._description,)
                for i in res:
                    if i in ('create_uid', 'create_date',
                            'write_uid', 'write_date', 'id'):
                        continue
                    if res[i]['type'] not in ('one2many', 'many2many'):
                        xml += '<label name="%s"/>' % (i,)
                        xml += '<field name="%s"/>' % (i,)
                        if res[i]['type'] == 'text':
                            xml += "<newline/>"
                xml += "</form>"
            elif view_type == 'tree':
                field = 'id'
                if self._rec_name in self._columns:
                    field = self._rec_name
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<tree string="%s"><field name="%s"/></tree>''' \
                % (self._description, field)
            elif view_type == 'calendar':
                xml = '''<?xml version="1.0" encoding="utf-8"?>''' \
                '''<calendar string="%s" date_start="%s">''' \
                '''<field name="%s"/></calendar>''' \
                % (self._description, self._date_name, self._rec_name)
            else:
                xml = ''
            result['type'] = view_type
            result['arch'] = xml
            result['name'] = 'default'
            result['field_childs'] = False
            result['view_id'] = 0

        tree = etree.fromstring(result['arch'])
        xarch, xfields = self._view_look_dom_arch(cursor, user, tree,
                result['type'], context=context)
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

    fields_view_get = Cache('orm.fields_view_get')(fields_view_get)

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
        table_query = ''
        table_args = []
        if self.table_query(context):
            table_query, table_args = self.table_query(context)
            table_query = '(' + table_query + ') AS '
        tables = [table_query + '"' + self._table + '"']
        tables_args = table_args
        joins = []
        while i < len(args):
            if args[i][1] not in (
                    'child_of',
                    '=',
                    'like',
                    'ilike',
                    '',
                    '!=',
                    'in',
                    '<=',
                    '>=',
                    '<',
                    '>'):
                raise Exception('ValidateError', 'Argument "%s" not supported' \
                        % args[i][1])

            table = self
            if args[i][0] in self._inherit_fields:
                itable = self.pool.get(self._inherit_fields[args[i][0]][0])
                table_query = ''
                table_arg = []
                if itable.table_query(context):
                    table_query, table_args = self.table_query(context)
                    table_query = '(' + table_query + ') AS '
                if (table_query + '"' + itable._table + '"' not in tables):
                    tables.append(table_query + '"' + itable._table + '"')
                    tables_args += table_arg
                    joins.append(('id', 'join', '%s.%s' % \
                            (self._table, self._inherits[itable._name]), itable))
            fargs = args[i][0].split('.', 1)
            field = table._columns.get(fargs[0], False)
            if not field:
                if not fargs[0] in self._inherit_fields:
                    raise Exception('ValidateError', 'Field "%s" doesn\'t ' \
                            'exist' % fargs[0])
                table = self.pool.get(self._inherit_fields[args[i][0]][0])
                field = table._columns.get(fargs[0], False)
            if len(fargs) > 1:
                if field._type == 'many2one':
                    args[i] = (fargs[0], 'inselect',
                            self.pool.get(field._obj).search(cursor, user,
                                [(fargs[1], args[i][1], args[i][2])],
                                context=context, query_string=True))
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
                        arg[0][0], arg, context=context))
            elif field._type == 'one2many':
                field_obj = self.pool.get(field._obj)

                if isinstance(args[i][2], basestring):
                    # get the ids of the records of the "distant" resource
                    ids2 = [x[0] for x in field_obj.name_search(cursor, user,
                        args[i][2], [], args[i][1], context=context)]
                else:
                    ids2 = args[i][2]
                if not ids2:
                    args[i] = ('id', '=', '0')
                else:
                    table_query = ''
                    table_args = []
                    if field_obj.table_query(context):
                        table_query, table_args = field_obj.table_query(context)
                        table_query = '(' + table_query + ') AS '
                    if len(ids2) < ID_MAX:
                        query1 = 'SELECT "' + field._field + '" ' \
                                'FROM ' + table_query + '"' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join(['%s' for x in ids2]) + ')'
                        query2 = table_args + [str(x) for x in ids2]
                        args[i] = ('id', 'inselect', (query1, query2))
                    else:
                        ids3 = []
                        for i in range((len(ids2) / ID_MAX) + \
                                (len(ids2) % ID_MAX)):
                            sub_ids = ids2[ID_MAX * i:ID_MAX * (i + 1)]
                            cursor.execute(
                                'SELECT "' + field._field + \
                                '" FROM ' + table_query + '"' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join(['%s' for x in sub_ids2]) + ')',
                                table_args + [str(x) for x in sub_ids2])

                            ids3.extend([x[0] for x in cursor.fetchall()])

                        args[i] = ('id', 'in', ids3)
                i += 1
            elif field._type == 'many2many':
                # XXX must find a solution for long id list
                if args[i][1] == 'child_of':
                    if isinstance(args[i][2], basestring):
                        ids2 = [x[0] for x in self.pool.get(
                        field._obj).name_search(cursor, user, args[i][2], [],
                            'like', context=context)]
                    elif isinstance(args[i][2], (int, long)):
                        ids2 = [args[i][2]]
                    else:
                        ids2 = args[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids), (parent, '!=', False)],
                                context=context)
                        return ids + _rec_get(ids2, table, parent)

                    if field._obj != table._name:
                        raise Exception('Error', 'Programming error: ' \
                                'child_of on field "%s" is not allowed!' % \
                                (args[i][0],))

                    parent = None
                    for k in table._columns:
                        field2 = table._columns[k]
                        if field2._type == 'many2many' \
                                and field._rel == field2._rel \
                                and field._id1 == field2._id2 \
                                and field._id2 == field2._id1:
                            parent = k
                            break
                    if not parent:
                        raise Exception('Error', 'Programming error: ' \
                                'child_of on field "%s" is not allowed!' % \
                                (args[i][0],))
                    args[i] = ('id', 'in', ids2 + _rec_get(ids2,
                        table, parent))
                else:
                    if isinstance(args[i][2], basestring):
                        res_ids = [x[0] for x in self.pool.get(field._obj
                            ).name_search(cursor, user, args[i][2], [],
                                args[i][1], context=context)]
                    else:
                        res_ids = args[i][2]
                    if res_ids == True or res_ids == False:
                        query1 = 'SELECT "' + field._id1 + '" ' \
                                'FROM "' + field._rel + '"'
                        query2 = []
                        clause = 'inselect'
                        if res_ids == False:
                            clause = 'notinselect'
                        args[i] = ('id', clause, (query1, query2))
                    elif not res_ids:
                        args[i] = ('id', '=', '0')
                    else:
                        query1 = 'SELECT "' + field._id1 + '" ' \
                                'FROM "' + field._rel + '" ' \
                                'WHERE "' + field._id2 + '" IN (' + \
                                    ','.join(['%s' for x in res_ids]) + ')'
                        query2 = [str(x) for x in res_ids]
                        args[i] = ('id', 'inselect', (query1, query2))
                i += 1

            elif field._type == 'many2one':
                # XXX must find a solution for long id list
                if args[i][1] == 'child_of':
                    if isinstance(args[i][2], basestring):
                        ids2 = [x[0] for x in self.pool.get(
                            field._obj).name_search(cursor, user, args[i][2],
                                [], 'like', context=context)]
                    elif isinstance(args[i][2], (int, long)):
                        ids2 = [args[i][2]]
                    else:
                        ids2 = args[i][2]

                    def _rec_get(ids, table, parent):
                        if not ids:
                            return []
                        ids2 = table.search(cursor, user,
                                [(parent, 'in', ids), (parent, '!=', False)],
                                context=context)
                        return ids + _rec_get(ids2, table, parent)

                    if field._obj != table._name:
                        raise Exception('Error', 'Programming error: ' \
                                'child_of on field "%s" is not allowed!' % \
                                (args[i][0],))
                    else:
                        if field.left and field.right:
                            cursor.execute('SELECT "' + field.left + '", ' \
                                        '"' + field.right + '" ' + \
                                    'FROM "' + self._table + '" ' + \
                                    'WHERE id IN ' + \
                                        '(' + ','.join(['%s' for x in ids2]) + ')',
                                        ids2)
                            clause = ''
                            for left, right in cursor.fetchall():
                                if clause:
                                    clause += 'OR '
                                clause += '( "' + field.left + '" >= ' + \
                                        str(left) + ' ' + \
                                        'AND "' + field.right + '" <= ' + \
                                        str(right) + ')'

                            query = 'SELECT id FROM "' + self._table + '" ' + \
                                    'WHERE ' + clause
                            args[i] = ('id', 'inselect', (query, []))
                        else:
                            args[i] = ('id', 'in', ids2 + _rec_get(ids2, table,
                                args[i][0]), table)
                else:
                    if isinstance(args[i][2], basestring):
                        res_ids = self.pool.get(field._obj).name_search(cursor,
                                user, args[i][2], [], args[i][1],
                                context=context)
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
                        query1 = '(SELECT res_id FROM ir_translation ' \
                                'WHERE name = %s AND lang = %s ' \
                                    'AND type = %s ' \
                                    'AND VALUE ' + args[i][1] + ' %s)'
                        query2 = [table._name + ',' + args[i][0],
                                context.get('language', False) or 'en_US',
                                'model', args[i][2]]
                        query1 += ' UNION '
                        table_query = ''
                        table_args = []
                        if table.table_query(context):
                            table_query, table_args = table.table_query(context)
                            table_query = '(' + table_query  + ') AS '
                        query1 += '(SELECT id FROM ' + table_query + \
                                '"' + table._table + '" ' \
                                'WHERE "' + args[i][0] + '" ' + \
                                args[i][1] + ' %s)'
                        query2 += table_args + [args[i][2]]
                        args[i] = ('id', 'inselect', (query1, query2), table)
                else:
                    args[i] += (table,)
                i += 1
        args.extend(joins)

        qu1, qu2 = [], []
        for arg in args:
            table = self
            if len(arg) > 3:
                table = arg[3]
            if arg[1] in ('inselect', 'notinselect'):
                clause = 'IN'
                if arg[1] == 'notinselect':
                    clause = 'NOT IN'
                qu1.append('(%s.%s %s (%s))' % (table._table, arg[0], clause,
                    arg[2][0]))
                qu2 += arg[2][1]
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
                    if len(arg[2]):
                        if arg[0] == 'id':
                            qu1.append('(%s.id in (%s))' % \
                                    (table._table,
                                        ','.join(['%s'] * len(arg[2])),))
                        else:
                            qu1.append('(%s.%s in (%s))' % \
                                    (table._table, arg[0], ','.join(
                                        [table._columns[arg[0]].\
                                                _symbol_set[0]] * len(arg[2]))))
                        if todel:
                            qu1[-1] = '(' + qu1[-1] + ' or ' + arg[0] + ' is null)'
                        qu2 += arg[2]
                    elif todel:
                        qu1.append('(' + arg[0] + ' IS NULL)')
                else:
                    qu1.append(' false')
            else:
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
                        if arg[0] in table._columns:
                            if arg[1] in ('like', 'ilike'):
                                qu1.append('(%s.%s %s %s)' % (table._table,
                                    arg[0], arg[1], '%s'))
                            else:
                                qu1.append('(%s.%s %s %s)' % (table._table,
                                    arg[0], arg[1],
                                    table._columns[arg[0]]._symbol_set[0]))
                        else:
                            qu1.append('(%s.%s %s \'%s\')' % \
                                    (table._table, arg[0], arg[1], arg[2]))

                        if add_null:
                            qu1[-1] = '('+qu1[-1]+' or '+arg[0]+' is null)'

        return (qu1, qu2, tables, tables_args)

    def search_count(self, cursor, user, args, context=None):
        '''
        Return the number of record that match the clause defined in args.
        see function search
        '''
        res = self.search(cursor, user, args, context=context, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    def _order_calc(self, cursor, user, field, otype, context=None):
        order_by = []
        tables = []
        field_name = None
        table_name = None
        link_field = None
        clause = ''

        if field in self._columns:
            table_name = self._table

            if self._columns[field]._classic_write:
                field_name = field

            if self._columns[field].order_field:
                field_name = self._columns[field].order_field

            if isinstance(self._columns[field], fields.Many2One):
                obj = self.pool.get(self._columns[field]._obj)
                table_name = obj._table
                link_field = field
                field_name = None

                if obj._rec_name in obj._columns:
                    field_name = obj._rec_name

                if obj._order_name in obj._columns:
                    field_name = obj._order_name

                if field_name:
                    order_by, tables, clause = obj._order_calc(cursor, user,
                            field_name, otype, context=context)
                    if '"' + table_name + '"' not in tables:
                        tables.append('"' + table_name + '"')
                        if clause:
                            clause += ' AND '
                        clause += ' %s.%s = %s.id' % (self._table, link_field,
                                table_name)
                    return order_by, tables, clause

                obj2 = None
                if obj._rec_name in obj._inherit_fields.keys():
                    obj2 = self.pool.get(obj._inherit_fields[obj._rec_name][0])
                    field_name = obj._rec_name

                if obj._order_name in obj._inherit_fields.keys():
                    obj2 = self.pool.get(obj._inherit_fields[obj._order_name][0])
                    field_name = obj._order_name

                if obj2 and field_name:
                    table_name2 = obj2._table
                    link_field2 = obj._inherits[obj2._name]
                    order_by, tables, clause = obj2._order_calc(cursor, user,
                            field_name, otype, context=context)

                    if '"' + table_name + '"' not in tables:
                        tables.append('"' + table_name + '"')
                        if clause:
                            clause += ' AND '
                        clause += ' %s.%s = %s.id' % (self._table, link_field,
                                table_name)

                    if '"' + table_name2 + '"' not in tables:
                        tables.append('"' + table_name2 + '"')
                        if clause:
                            clause += ' AND '
                        clause += ' %s.%s = %s.id' % (obj._table, link_field2,
                                table_name2)
                    return order_by, tables, clause

            if field_name:
                order_by.append(table_name + '.' + field_name + ' ' + otype)
                return order_by, tables, clause

        if field in self._inherit_fields.keys():
            obj = self.pool.get(self._inherit_fields[field][0])
            table_name = obj._table
            link_field = self._inherits[obj._name]
            order_by, tables, clause = obj._order_calc(cursor, user, field,
                    otype, context=context)
            if '"' + table_name + '"' not in tables:
                tables.append('"' + table_name + '"')
                if clause:
                    clause += ' AND '
                clause += ' %s.%s = %s.id' % (self._table, link_field,
                        table_name)
            return order_by, tables, clause

        raise Exception('Error', 'Wrong field name (%s) in order!' \
                % field)

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        '''
        Return a list of id that match the clause defined in args.
        args is a list of tuple that are construct like this:
            ('field name', 'operator', value)
            field name: is the name of a field of the object
                or a relational field by using '.' as separator.
            operator can be:
                child_of  (all the child of a relation field)
                =
                like
                ilike (case insensitive)
                !=
                in
                <=
                >=
                <
                >
        offset can be used to specify a offset in the result
        limit can be used to limit the number of ids return
        order is a list of tupe that are construct like this:
            ('field name', 'DESC|ASC')
            it allow to specify the order of the ids in the return list
        count can be used to return just the len of the list
        if query_string is True, the function will return a tuple with
            the SQL query string and the arguments.
        '''
        # compute the where, order by, limit and offset clauses
        (qu1, qu2, tables, tables_args) = self._where_calc(cursor, user, args,
                context=context)

        if len(qu1):
            qu1 = ' WHERE ' + ' AND '.join(qu1)
        else:
            qu1 = ''

        order_by = []
        for field, otype in (order or self._order):
            if otype.upper() not in ('DESC', 'ASC'):
                raise Exception('Error', 'Wrong order type (%s)!' % otype)
            order_by2, tables2, clause = self._order_calc(cursor, user,
                    field, otype, context=context)
            order_by += order_by2
            for table in tables2:
                if table not in tables:
                    tables.append(table)
            if clause:
                if qu1:
                    qu1 += ' AND ' + clause
                else:
                    qu1 += 'WHERE ' + clause

        order_by = ','.join(order_by)

        limit_str = limit and (type(limit) in (float, int, long))\
                    and ' LIMIT %d' % limit or ''
        offset_str = offset and (type(offset) in (float, int, long))\
                     and ' OFFSET %d' % offset or ''


        # construct a clause for the rules :
        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name)
        if domain1:
            qu1 = qu1 and qu1 + ' AND ' + domain1 or ' WHERE ' + domain1
            qu2 += domain2

        if count:
            cursor.execute('SELECT COUNT(%s.id) FROM ' % self._table +
                    ','.join(tables) + qu1 + limit_str + offset_str,
                    tables_args + qu2)
            res = cursor.fetchall()
            return res[0][0]
        # execute the "main" query to fetch the ids we were searching for
        query_str = 'SELECT %s.id FROM ' % self._table + \
                ','.join(tables) + qu1 + ' order by ' + order_by + \
                limit_str + offset_str
        if query_string:
            return (query_str, tables_args + qu2)
        cursor.execute(query_str, tables_args + qu2)
        res = cursor.fetchall()
        return [x[0] for x in res]

    def name_get(self, cursor, user, ids, context=None):
        '''
        Return a list of tuple for each ids.
        The tuple contains the id and the name of the record.
        '''
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r['id'], unicode(r[self._rec_name])) for r in self.read(cursor,
            user, ids, [self._rec_name], context, load='_classic_write')]

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        '''
        Return a list of ids where the name and the args clause matches.
        args is a clause like in the function search.
        operator is the operator used to compare the name.
        limit can be used to limit the number of id.
        '''
        if args is None:
            args = []
        args = args[:]
        if name:
            args += [(self._rec_name, operator, name)]
        ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def copy(self, cursor, user, object_id, default=None, context=None):
        '''
        Duplicate the object_id record.
        default can be a dict with field name as keys,
        it will replace the value of the record.
        '''
        if default is None:
            default = {}
        if 'state' not in default:
            if 'state' in self._defaults:
                default['state'] = self._defaults['state'](cursor, user,
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
            elif ftype in ('one2many',):
                res = []
                rel = self.pool.get(fields2[field]['relation'])
                for rel_id in data[field]:
                    # the lines are first duplicated using the wrong (old)
                    # parent but then are reassigned to the correct one thanks
                    # to the ('add', ...)
                    res.append(('add', rel.copy(cursor, user, rel_id,
                        context=context)))
                data[field] = res
            elif ftype == 'many2many':
                data[field] = [('set', data[field])]
        del data['id']
        for i in self._inherits:
            del data[self._inherits[i]]
        return self.create(cursor, user, data, context=context)

    def search_read(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, fields_names=None, load='_classic_read'):
        '''
        Call search function and read in once.
        Usefull for the client to reduce the number of calls.
        '''
        ids = self.search(cursor, user, args, offset=offset, limit=limit,
                order=order, context=context)
        if limit == 1:
            ids = ids[0]
        return self.read(cursor, user, ids, fields_names=fields_names,
                context=context, load=load)

    def check_recursion(self, cursor, user, ids, parent='parent'):
        '''
        Function that check if there is no recursion in the tree
        composed with parent as parent field name.
        '''
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

    def default_sequence(self, cursor, user, context=None):
        '''
        Return the default value for sequence field.
        '''
        cursor.execute('SELECT MAX(sequence) ' \
                'FROM "' + self._table + '"')
        res = cursor.fetchone()
        if res:
            return res[0]
        return 0

    def _rebuild_tree(self, cursor, user, parent, parent_id, left):
        '''
        Rebuild left, right value for the tree.
        '''
        right = left + 1

        if not parent_id:
            cursor.execute('SELECT id FROM "' + self._table + '" ' \
                    'WHERE "' + parent + '" IS NULL')
        else:
            cursor.execute('SELECT id FROM "' + self._table + '" ' \
                    'WHERE "' + parent + '" = %s', (parent_id,))
        child_ids = [x[0] for x in cursor.fetchall()]

        for child_id in child_ids:
            right = self._rebuild_tree(cursor, user, parent, child_id, right)

        field = self._columns[parent]

        if parent_id:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + field.left + '" = %s, ' \
                        '"' + field.right + '" = %s ' \
                    'WHERE id = %s', (left, right, parent_id))
        return right + 1

    def _update_tree(self, cursor, user, object_id, field_name, left, right):
        '''
        Update left, right values for the tree.
        '''
        cursor.execute('SELECT "' + right + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id IN (' \
                    'SELECT "' + field_name + '" FROM "' + self._table + '" ' \
                    'WHERE id = %s)', (object_id,))
        if cursor.rowcount:
            parent_right = cursor.fetchone()[0]
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + 2 ' \
                    'WHERE "' + left + '" >= %s', (parent_right,))
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + right + '" = "' + right + '" + 2 ' \
                    'WHERE "' + right + '" >= %s', (parent_right,))
            cursor.execute('UPDATE "' +  self._table + '" ' \
                    'SET "' + left + '" = %s, ' \
                        '"' + right + '" = %s ' \
                    'WHERE id = %s', (parent_right, parent_right + 1, object_id))
        else:
            max_right = 0
            cursor.execute('SELECT MAX("' + right + '") ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE "' + field_name + '" IS NULL')
            if cursor.rowcount:
                max_right = cursor.fetchone()[0]

            cursor.execute('UPDATE "' +  self._table + '" ' \
                    'SET "' + left + '" = %s, ' \
                        '"' + right + '" = %s ' \
                    'WHERE id = %s', (max_right + 1, max_right + 2, object_id))

orm = ORM
