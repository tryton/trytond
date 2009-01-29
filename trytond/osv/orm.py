#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
# -*- coding: utf-8 -*-
from trytond.model import ModelView
from trytond.netsvc import LocalService
import fields
from trytond.tools import Cache
import time
import traceback
import datetime
import copy
from trytond.sql_db import table_handler
from decimal import Decimal
import logging

OPERATORS = (
        'child_of',
        'not child_of',
        '=',
        '!=',
        'like',
        'not like',
        'ilike',
        'not ilike',
        'in',
        'not in',
        '<=',
        '>=',
        '<',
        '>',
    )

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

    def get_eval(self):
        res = []
        for record in self:
            res2 = {}
            for field_name, field in record._table._columns.iteritems():
                if not isinstance(record[field_name], BrowseRecordList):
                    res2[field_name] = record.get_eval(field_name)
            res.append(res2)
        return res


class BrowseRecordNull(object):
    '''
    An object that represents an empty record.
    '''

    def __init__(self):
        self.id = False

    def __getitem__(self, name):
        return False

    def __int__(self):
        return False

    def __str__(self):
        return ''

    def __nonzero__(self):
        return False


class BrowseRecord(object):
    '''
    An object that represents record defined by a ORM object.
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
        if not self._data[self._id].has_key(name):
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
                        if x[1]._classic_write \
                        and x[0] not in self._data[self._id] \
                        and ((not x[1].translate \
                                and x[1]._type not in ('text', 'binary')) \
                            or x[0] == name)]
                # gen the list of inherited fields
                inherits = [(x[0], x[1][2]) for x in \
                        self._table._inherit_fields.items()]
                # complete the field list with the inherited fields
                # which are classic or many2one
                ffields += [x for x in inherits if x[1]._classic_write \
                        and x[0] not in self._data[self._id] \
                        and ((not x[1].translate \
                                and x[1]._type not in ('text', 'binary')) \
                            or x[0] == name)]
            # otherwise we fetch only that field
            else:
                ffields = [(name, col)]
            ids = [x for x in self._data.keys() \
                    if not self._data[x].has_key(name)]
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
                        if ids2 is False:
                            data[i] = BrowseRecordNull()
                        else:
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
        prev_lang = self._context.get('language') or 'en_US'
        self._context['language'] = lang
        for table in self._cache:
            for obj_id in self._cache[table]:
                self._language_cache.setdefault(prev_lang,
                        {}).setdefault(table, {}).update(
                                self._cache[table][obj_id])
                if lang in self._language_cache \
                        and table in self._language_cache[lang] \
                        and obj_id in self._language_cache[lang][table]:
                    self._cache[table][obj_id] = \
                            self._language_cache[lang][table][obj_id]
                else:
                    self._cache[table][obj_id] = {'id': obj_id}

    def get_eval(self, name):
        res = self[name]
        if isinstance(res, BrowseRecord):
            res = res.id
        if isinstance(res, BrowseRecordList):
            res = res.get_eval()
        if isinstance(res, BrowseRecordNull):
            res = False
        return res


class EvalEnvironment(dict):

    def __init__(self, record, obj):
        super(EvalEnvironment, self).__init__()
        self.record = record
        self.obj = obj

    def __getitem__(self, item):
        if item.startswith('_parent_'):
            field = item[8:]
            if field in self.obj._columns:
                _obj = self.obj._columns[field]._obj
            else:
                _obj = self.obj._inherit_fields[field][2]._obj
            obj = self.obj.pool.get(_obj)
            return EvalEnvironment(self.record[field], obj)
        if item in self.obj._columns \
                or item in self.obj._inherit_fields:
            return self.record.get_eval(item)
        return super(EvalEnvironment, self).__getitem__(item)

    def __getattr__(self, item):
        return self.__getitem__(item)

    def get(self, item):
        try:
            return self.__getitem__(item)
        except:
            pass
        return super(EvalEnvironment, self).get(item)

    def __nonzero__(self):
        return bool(self.record)

class ORM(ModelView):
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
    _table = None
    _rec_name = 'name'
    _order_name = None # Use to force order field when sorting on Many2One
    _date_name = 'date'
    _order = None
    _sequence = None
    _auto = True
    _sql = ''

    create_uid = fields.Many2One('res.user',
       'Create User', required=True, readonly=True)
    create_date = fields.DateTime('Create Date',
       required=True, readonly=True)
    write_uid = fields.Many2One('res.user',
          'Write User', readonly=True)
    write_date = fields.DateTime(
       'Write Date', readonly=True)
    id = fields.Integer('ID', readonly=True)

    def auto_init(self, cursor, module_name):
        self.init(cursor, module_name)
        self._auto_init(cursor, module_name)

    def init(self, cursor, module_name):
        super(ORM, self).init(cursor, module_name)
        cursor.execute('SELECT id, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name = %s',
                ('en_US', 'error', self._name))
        trans_error = {}
        for trans in cursor.dictfetchall():
            trans_error[trans['src']] = trans

        errors = self._sql_error_messages.values()
        for _, _, error in self._sql_constraints:
            errors.append(error)
        for error in set(errors):
            if error not in trans_error:
                cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module, fuzzy) ' \
                        'VALUES (%s, %s, %s, %s, %s, %s, false)',
                        (self._name, 'en_US', 'error', error, '', module_name))

    def _auto_init(self, cursor, module_name):
        if not self._auto or self.table_query():
            # No db table for this object.
            return

        table = table_handler(cursor, self._table, self._name, module_name)
        logs = (
            ('create_date', 'timestamp', 'TIMESTAMP',
                fields.DateTime._symbol_set, lambda *a: datetime.datetime.now()),
            ('write_date', 'timestamp', 'TIMESTAMP',
                fields.DateTime._symbol_set, None),
            ('create_uid', 'int4',
             'INTEGER REFERENCES res_user ON DELETE SET NULL',
             fields.Integer._symbol_set, lambda *a: 0),
            ('write_uid', 'int4',
             'INTEGER REFERENCES res_user ON DELETE SET NULL',
             fields.Integer._symbol_set, None),
            )
        for log in logs:
            table.add_raw_column(log[0], (log[1], log[2]), log[3],
                    default_fun=log[4], migrate=False)
        for field_name, field in self._columns.iteritems():
            default_fun = None
            if field_name in (
                    'id',
                    'write_uid',
                    'write_date',
                    'create_uid',
                    'create_date',
                    ):
                continue

            if field._classic_write:
                if field_name in self._defaults:
                    default_fun = self._defaults[field_name]

                    def unpack_wrapper(fun):
                        def unpack_result(*a):
                            try: # XXX ugly hack: some default fct try
                                 # to access the non-existing table
                                result = fun(*a)
                            except:
                                return None
                            clean_results = self.__clean_defaults(
                                {field_name: result})
                            return clean_results[field_name]
                        return unpack_result
                    default_fun = unpack_wrapper(default_fun)

                table.add_raw_column(field_name, field.sql_type(),
                        field._symbol_set, default_fun, field.size)

                if isinstance(field, (fields.Integer, fields.Float)):
                    table.db_default(field_name, 0)

                if isinstance(field, fields.Many2One):
                    if field._obj in ('res.user', 'res.group'):
                        ref = field._obj.replace('.','_')
                    else:
                        ref = self.pool.get(field._obj)._table
                    table.add_fk(field_name, ref, field.ondelete)

                table.index_action(
                        field_name, action=field.select and 'add' or 'remove')

                required = field.required
                if isinstance(field, (fields.Integer, fields.Float,
                    fields.Boolean)):
                    required = True
                table.not_null_action(
                    field_name, action=required and 'add' or 'remove')

            elif isinstance(field, fields.Many2Many):
                if field._obj in ('res.user', 'res.group'):
                    ref = field._obj.replace('.','_')
                else:
                    ref = self.pool.get(field._obj)._table
                table.add_m2m(field_name, ref, field._rel, field.origin,
                        field.target, field.ondelete_origin,
                        field.ondelete_target)

            elif not isinstance(field, (fields.One2Many, fields.Function)):
                raise Exception('Unknow field type !')

        for field_name, field in self._columns.iteritems():
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                self._rebuild_tree(cursor, 0, field_name, False, 0)

        for ident, constraint, msg in self._sql_constraints:
            table.add_constraint(ident, constraint)

    def __init__(self):
        super(ORM, self).__init__()
        self._rpc_allowed += [
                'read',
                'write',
                'create',
                'delete',
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
        self._order = [('id', 'ASC')]
        self._sql_error_messages = {}

        if not self._table:
            self._table = self._name.replace('.', '_')

        if not self._sequence:
            self._sequence = self._table+'_id_seq'

        for name in self._columns.keys() + self._inherit_fields.keys():
            if name in self._columns:
                field = self._columns[name]
            else:
                field = self._inherit_fields[name][2]
            if isinstance(field, (fields.Selection, fields.Reference)) \
                    and not isinstance(field.selection, (list, tuple)) \
                    and field.selection not in self._rpc_allowed:
                self._rpc_allowed.append(field.selection)
            if field.on_change:
                on_change = 'on_change_' + name
                if on_change not in self._rpc_allowed:
                    self._rpc_allowed.append(on_change)
            if field.on_change_with:
                on_change_with = 'on_change_with_' + name
                if on_change_with not in self._rpc_allowed:
                    self._rpc_allowed.append(on_change_with)


    def default_create_uid(self, cursor, user, context=None):
        "Default value for uid field"
        return int(user)

    def default_create_date(self, cursor, user, context=None):
        "Default value for create_date field"
        return datetime.datetime.today()

    def table_query(self, context=None):
        '''
        Return None if the table object is a real table in the database
        or return a tuple wiht the query for the table object and the arguments
        '''
        return None


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
                    data[fpos] = row2 or ''
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
        logger = logging.getLogger('import')

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
                            logger.warning("key '%s' not found " \
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
                                logger.warning(
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
                                    logger.warning(
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
                logger.error(exp)
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
        self.pool.get('ir.model.access').check(cursor, user, self._name, 'read',
                context=context)
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
                self._name, context=context)

        # all inherited fields + all non inherited fields
        # for which the attribute whose name is in load is True
        fields_pre = [x for x in fields_names if (x in self._columns \
                and getattr(self._columns[x], '_classic_write')) or \
                (x == '_timestamp')] + \
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
                    or '"' + x + '"' for x in fields_pre \
                    if x != '_timestamp']
            if '_timestamp' in fields_pre:
                if not self.table_query(context):
                    fields_pre2 += ['(CASE WHEN write_date IS NOT NULL ' \
                            'THEN write_date ELSE create_date END) ' \
                            'AS _timestamp']
                else:
                    fields_pre2 += ['now()::timestamp AS _timestamp']

            if len(ids) > cursor.IN_MAX:
                cursor.execute('SELECT id ' \
                        'FROM ' + table_query + '"' + self._table + '" ' \
                        'ORDER BY ' + \
                        ','.join([self._table + '.' + x[0] + ' ' + x[1]
                            for x in self._order]), table_args)

                i = 0
                ids_sorted = {}
                for row in cursor.fetchall():
                    ids_sorted[row[0]] = i
                    i += 1
                ids = ids[:]
                ids.sort(lambda x, y: ids_sorted[x] - ids_sorted[y])

            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                if domain1:
                    cursor.execute(('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM ' + table_query + '\"' + self._table +'\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join(['%s' for x in sub_ids]) + ')'\
                            ' AND (' + domain1 + ') ORDER BY ' + \
                            ','.join([self._table + '.' + x[0] + ' ' + x[1] \
                            for x in self._order])),
                            table_args + sub_ids + domain2)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                else:
                    cursor.execute('SELECT ' + \
                            ','.join(fields_pre2 + ['id']) + \
                            ' FROM ' + table_query + '\"' + self._table + '\" ' \
                            'WHERE id IN ' \
                                '(' + ','.join(['%s' for x in sub_ids]) + ')'\
                            ' ORDER BY ' + \
                            ','.join([self._table + '.' + x[0] + ' ' + x[1] \
                            for x in self._order]), table_args + sub_ids)
                res.extend(cursor.dictfetchall())
        else:
            res = [{'id': x} for x in ids]

        for field in fields_pre:
            if field == '_timestamp':
                continue
            if self._columns[field].translate:
                ids = [x['id'] for x in res]
                res_trans = self.pool.get('ir.translation')._get_ids(cursor,
                        self._name + ',' + field, 'model',
                        context.get('language') or 'en_US', ids)
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
        func_fields = {}
        for field in fields_post:
            if isinstance(self._columns[field], fields.Function) \
                    and not isinstance(self._columns[field], fields.Property):
                key = (self._columns[field]._fnct, self._columns[field]._arg)
                func_fields.setdefault(key, [])
                func_fields[key].append(field)
                continue
            # get the value of that field for all records/ids
            res2 = self._columns[field].get(cursor, self, ids, field, user,
                    context=context, values=res)
            for record in res:
                record[field] = res2[record['id']]
        for i in func_fields:
            field_list = func_fields[i]
            field = field_list[0]
            res2 = self._columns[field].get(cursor, self, ids, field_list, user,
                    context=context, values=res)
            for field in res2:
                for record in res:
                    record[field] = res2[field][record['id']]
        return res

    def _validate(self, cursor, user, ids, context=None):
        if context is None:
            context = {}
        context = context.copy()
        field_error = []
        field_err_str = []
        for field in self._constraints:
            if not getattr(self, field[0])(cursor, user, ids):
                self.raise_user_error(cursor, field[1], context=context)

        if not 'res.user' in self.pool.object_name_list():
            ctx_pref = {
            }
        else:
            user_obj = self.pool.get('res.user')
            ctx_pref = user_obj.get_preferences(cursor, user,
                context_only=True, context=context)

        def get_error_args(field_name):
            model_field_obj = self.pool.get('ir.model.field')
            error_args = (field_name, self._name)
            if model_field_obj:
                model_field_ids = model_field_obj.search(cursor,
                        user, [
                            ('name', '=', field_name),
                            ('model.model', '=', self._name),
                            ], context=context, limit=1)
                if model_field_ids:
                    model_field = model_field_obj.browse(cursor,
                            user, model_field_ids[0],
                            context=context)
                    error_args = (model_field.field_description,
                            model_field.model.name)
            return error_args

        context.update(ctx_pref)
        records = self.browse(cursor, user, ids, context=context)
        for field_name, field in self._columns.iteritems():
            # validate domain
            if field._type in ('many2one', 'many2many', 'one2many') \
                    and field._domain:
                relation_obj = self.pool.get(field._obj)
                if isinstance(field._domain, basestring):
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        domain = eval(field._domain, env)
                        relation_ids = []
                        if record[field_name]:
                            if field._type in ('many2one',):
                                relation_ids.append(record[field_name].id)
                            else:
                                relation_ids.extend(
                                        [x.id for x in record[field_name]])
                        if relation_ids and not relation_obj.search(cursor,
                                user, [
                                    'AND',
                                    [('id', 'in', relation_ids)],
                                    domain,
                                    ], context=context):
                            self.raise_user_error(cursor,
                                    'domain_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
                else:
                    relation_ids = []
                    for record in records:
                        if record[field_name]:
                            if field._type in ('many2one',):
                                relation_ids.append(record[field_name].id)
                            else:
                                relation_ids.extend(
                                        [x.id for x in record[field_name]])
                    if relation_ids:
                        find_ids = relation_obj.search(cursor, user, [
                            'AND',
                            [('id', 'in', relation_ids)],
                            field._domain,
                            ], context=context)
                        if not set(relation_ids) == set(find_ids):
                            self.raise_user_error(cursor,
                                    'domain_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
            # validate states required
            if field.states and 'required' in field.states:
                if isinstance(field.states['required'], basestring):
                    ctx = context.copy()
                    ctx.update(ctx_pref)
                    for record in records:
                        env = EvalEnvironment(record, self)
                        env.update(ctx)
                        env['current_date'] = datetime.datetime.today()
                        env['time'] = time
                        env['context'] = context
                        env['active_id'] = record.id
                        required = eval(field.states['required'], env)
                        if required and not record[field_name]:
                            self.raise_user_error(cursor,
                                    'required_validation_record',
                                    error_args=get_error_args(field_name),
                                    context=context)
                else:
                    if field.states['required']:
                        for record in records:
                            if not record[field_name]:
                                self.raise_user_error(cursor,
                                        'required_validation_record',
                                        error_args=get_error_args(field_name),
                                        context=context)

    def delete(self, cursor, user, ids, context=None):
        '''
        Remove the ids.
        '''
        if context is None:
            context = {}
        context = context.copy()
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        if self.table_query(context):
            return True

        if context.get('_timestamp', False):
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = '(id = %s AND ' \
                        '(CASE WHEN write_date IS NOT NULL ' \
                        'THEN write_date ELSE create_date END) ' \
                        ' > %s)'
                args = []
                for i in sub_ids:
                    if context['_timestamp'].get(self._name + ',' + str(i)):
                        args.append(i)
                        args.append(context['_timestamp'][
                            self._name + ',' +str(i)])
                if args:
                    cursor.execute("SELECT id " \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + ' OR '.join(
                                [clause for x in range(len(args)/2)]), args)
                    if cursor.rowcount:
                        raise Exception('ConcurrencyException',
                                'Records were modified in the meanwhile')
            for i in ids:
                if context['_timestamp'].get(self._name + ',' + str(i)):
                    del context['_timestamp'][self._name + ',' +str(i)]

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'delete', context=context)

        cursor.execute(
            "SELECT id FROM wkf_instance "\
                "WHERE res_id IN (" + ",".join(["%s" for i in ids]) + ") "\
                "AND res_type = %s AND state != 'complete'",
            ids + [self._name])
        if cursor.rowcount != 0:
            self.raise_user_error(cursor, 'delete_workflow_record',
                    context=context)

        wf_service = LocalService("workflow")
        for obj_id in ids:
            wf_service.trg_delete(user, self._name, obj_id, cursor,
                    context=context)

        if not self.check_xml_record(cursor, user, ids, None, context=context):
            self.raise_user_error(cursor, 'delete_xml_record',
                                  error_description='xml_record_desc',
                                  context=context)

        tree_ids = {}
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                cursor.execute('SELECT id FROM "' + self._table + '" '\
                        'WHERE "' + k + '" IN (' \
                            + ','.join(['%s' for x in ids]) + ')',
                            ids)
                tree_ids[k] = [x[0] for x in cursor.fetchall()]

        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name, context=context)
        if domain1:
            domain1 = ' AND (' + domain1 + ') '
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
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

        for k in tree_ids.keys():
            field = self._columns[k]
            if len(tree_ids[k]) == 1:
                self._update_tree(cursor, user, tree_ids[k][0], k,
                        field.left, field.right)
            else:
                self._rebuild_tree(cursor, 0, k, False, 0)

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
        cursor.execute('SELECT values ' \
                'FROM ir_model_data ' \
                'WHERE model = %s ' \
                    'AND db_id in (' + ','.join('%s' for x in ids)+ ') ',
                [self._name] + ids)
        if cursor.rowcount == 0:
            return True
        if values == None:
            return False
        for line in cursor.fetchall():
            if not line[0]:
                continue
            xml_values = eval(line[0], {
                'Decimal': Decimal,
                'datetime': datetime,
                })
            for key, val in values.iteritems():
                if key in xml_values and val != xml_values[key]:
                    return False
        return True

    def write(self, cursor, user, ids, vals, context=None):
        '''
        Update ids with the content of vals.
        vals is a dict with fields name as keys.
        '''
        if context is None:
            context = {}
        context = context.copy()
        if not ids:
            return True
        if self.table_query(context):
            return True

        vals = vals.copy()

        if isinstance(ids, (int, long)):
            ids = [ids]
        else:
            # _update_tree works if only one record has changed
            update_tree = False
            for k in self._columns:
                field = self._columns[k]
                if isinstance(field, fields.Many2One) \
                        and field._obj == self._name \
                        and field.left and field.right:
                    update_tree = True
            if update_tree:
                for object_id in ids:
                    self.write(cursor, user, object_id, vals, context=context)
                return True

        if context.get('_timestamp', False):
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                clause = '(id = %s AND ' \
                        '(CASE WHEN write_date IS NOT NULL ' \
                        'THEN write_date ELSE create_date END) ' \
                        ' > %s)'
                args = []
                for i in sub_ids:
                    if context['_timestamp'].get(self._name + ',' + str(i)):
                        args.append(i)
                        args.append(context['_timestamp'][
                            self._name + ',' +str(i)])
                if args:
                    cursor.execute("SELECT id " \
                            'FROM "' + self._table + '" ' \
                            'WHERE ' + ' OR '.join(
                                [clause for x in range(len(args)/2)]), args)
                    if cursor.rowcount:
                        raise Exception('ConcurrencyException',
                                'Records were modified in the meanwhile')
            for i in ids:
                if context['_timestamp'].get(self._name + ',' + str(i)):
                    del context['_timestamp'][self._name + ',' +str(i)]

        self.pool.get('ir.model.access').check(cursor, user, self._name,
                'write', context=context)

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
                            or (context.get('language') or 'en_US') == 'en_US':
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

        upd0.append('write_uid = %s')
        upd0.append('write_date = now()')
        upd1.append(user)

        if len(upd0):
            domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor,
                    user, self._name, context=context)
            if domain1:
                domain1 = ' AND (' + domain1 + ') '
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                ids_str = ','.join(['%s' for x in sub_ids])
                if domain1:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE id IN (' + ids_str + ') ' + domain1,
                            sub_ids + domain2)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                else:
                    cursor.execute('SELECT id FROM "' + self._table + '" ' \
                            'WHERE id IN (' + ids_str + ')', sub_ids)
                    if not cursor.rowcount == len({}.fromkeys(sub_ids)):
                        raise Exception('AccessError',
                                'You try to bypass an access rule ' \
                                        '(Document type: %s).' % \
                                        self._description)
                if domain1:
                    cursor.execute('UPDATE "' + self._table + '" ' \
                            'SET ' + ','.join(upd0) + ' ' \
                            'WHERE id IN (' + ids_str + ') ' + domain1,
                            upd1 + sub_ids + domain2)
                else:
                    cursor.execute('UPDATE "' + self._table + '" ' \
                            'SET ' + ','.join(upd0) + ' ' \
                            'WHERE id IN (' + ids_str + ') ', upd1 + sub_ids)

            for field in direct:
                if self._columns[field].translate:
                    self.pool.get('ir.translation')._set_ids(cursor, user,
                            self._name + ',' + field, 'model',
                            context.get('language') or 'en_US', ids,
                            vals[field])

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
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                ids_str = ','.join(['%s' for x in sub_ids])
                cursor.execute('SELECT DISTINCT "' + col + '" ' \
                        'FROM "' + self._table + '" WHERE id IN (' + ids_str + ')',
                        sub_ids)
                nids.extend([x[0] for x in cursor.fetchall()])

            vals2 = {}
            for val in updend:
                if self._inherit_fields[val][0] == table:
                    vals2[val] = vals[val]
            self.pool.get(table).write(cursor, user, nids, vals2,
                    context=context)

        self._validate(cursor, user, ids, context=context)

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                if field.left in vals or field.right in vals:
                    raise Exception('ValidateError', 'You can not update fields: ' \
                            '"%s", "%s"' % (field.left, field.right))
                if len(ids) == 1:
                    self._update_tree(cursor, user, ids[0], k,
                            field.left, field.right)
                else:
                    self._rebuild_tree(cursor, 0, k, False, 0)

        # Restart rule cache
        if self.pool.get('ir.rule.group').search(cursor, 0, [
            ('model.model', '=', self._name),
            ], context=context):
            self.pool.get('ir.rule').domain_get(cursor.dbname)

        wf_service = LocalService("workflow")
        for obj_id in ids:
            wf_service.trg_write(user, self._name, obj_id, cursor,
                    context=context)
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
            elif fld_def._type in ('boolean',):
                vals[field] = bool(defaults[field])
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
                'create', context=context)

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

        self._validate(cursor, user, [id_new], context=context)

        # Check for Modified Preorder Tree Traversal
        for k in self._columns:
            field = self._columns[k]
            if isinstance(field, fields.Many2One) \
                    and field._obj == self._name \
                    and field.left and field.right:
                self._update_tree(cursor, user, id_new, k, field.left, field.right)

        wf_service = LocalService("workflow")
        wf_service.trg_create(user, self._name, id_new, cursor, context=context)
        return id_new

    def _where_calc(self, cursor, user, args, active_test=True, context=None):
        if context is None:
            context = {}
        args = args[:]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if ('active' in self._columns or \
                'active' in self._inherit_fields.keys()) \
                and (active_test and context.get('active_test', True)):
            def process_args(args):
                i = 0
                active_found = False
                while i < len(args):
                    if isinstance(args[i], list):
                        args[i] = process_args(args[i])
                    if isinstance(args[i], tuple):
                        if args[i][0] == 'active':
                            active_found = True
                    i += 1
                if not active_found:
                    if args and ((isinstance(args[0], basestring) \
                            and args[0] == 'AND') \
                            or (not isinstance(args[0], basestring))):
                        args.append(('active', '=', 1))
                    else:
                        args = ['AND', args, ('active', '=', 1)]
                return args
            args = process_args(args)

        table_query = ''
        table_args = []
        if self.table_query(context):
            table_query, table_args = self.table_query(context)
            table_query = '(' + table_query + ') AS '

        tables = [table_query + '"' + self._table + '"']
        tables_args = table_args

        qu1, qu2 = self.__where_calc_oper(cursor, user, args, tables,
                tables_args, context=context)
        return qu1, qu2, tables, tables_args


    def __where_calc_oper(self, cursor, user, args, tables, tables_args,
            context=None):
        operator = 'AND'
        if len(args) and isinstance(args[0], basestring):
            if args[0] not in ('AND', 'OR'):
                raise Exception('ValidateError', 'Operator "%s" not supported' \
                        % args[0])
            operator = args[0]
            args = args[1:]
        tuple_args = []
        list_args = []
        for arg in args:
            #add test for xmlrpc that doesn't handle tuple
            if isinstance(arg, tuple) \
                    or (isinstance(arg, list) and len(arg) > 2 \
                    and arg[1] in OPERATORS):
                tuple_args.append(tuple(arg))
            elif isinstance(arg, list):
                list_args.append(arg)

        qu1, qu2 = self.__where_calc(cursor, user,
                tuple_args, tables, tables_args, context=context)
        if len(qu1):
            qu1 = (' ' + operator + ' ').join(qu1)
        else:
            qu1 = ''

        for args2 in list_args:
            qu1b, qu2b = self.__where_calc_oper(cursor,
                    user, args2, tables, tables_args, context=context)
            if not qu1b:
                qu1b = 'true'
            if qu1 and qu1b:
                qu1 += ' ' + operator + ' ' + qu1b
            elif qu1b:
                qu1 = qu1b
            qu2 += qu2b
        if qu1:
            qu1 = '(' + qu1 + ')'
        return qu1, qu2

    def __where_calc(self, cursor, user, args, tables, tables_args,
            context=None):
        if context is None:
            context = {}

        for arg in args:
            if arg[1] not in OPERATORS:
                raise Exception('ValidateError', 'Argument "%s" not supported' \
                        % arg[1])
        i = 0
        joins = []
        while i < len(args):
            table = self
            fargs = args[i][0].split('.', 1)
            if fargs[0] in self._inherit_fields:
                itable = self.pool.get(self._inherit_fields[fargs[0]][0])
                table_query = ''
                table_arg = []
                if itable.table_query(context):
                    table_query, table_args = self.table_query(context)
                    table_query = '(' + table_query + ') AS '
                table_join = 'LEFT JOIN ' + table_query + \
                        '"' + itable._table + '" ON ' \
                        '%s.id = %s.%s' % (itable._table, self._table,
                                self._inherits[itable._name])
                if table_join not in tables:
                    tables.append(table_join)
                    tables_args += table_arg
            field = table._columns.get(fargs[0], False)
            if not field:
                if not fargs[0] in self._inherit_fields:
                    raise Exception('ValidateError', 'Field "%s" doesn\'t ' \
                            'exist on "%s"' % (fargs[0], self._name))
                table = self.pool.get(self._inherit_fields[fargs[0]][0])
                field = table._columns.get(fargs[0], False)
            if len(fargs) > 1:
                if field._type == 'many2one':
                    args[i] = (fargs[0], 'inselect',
                            self.pool.get(field._obj).search(cursor, user,
                                [(fargs[1], args[i][1], args[i][2])],
                                context=context, query_string=True), table)
                    i += 1
                    continue
                else:
                    raise Exception('ValidateError', 'Clause on field "%s" ' \
                            'doesn\'t work on "%s"' % (args[i][0], self._name))
            if field._properties:
                arg = [args.pop(i)]
                j = i
                while j < len(args):
                    if args[j][0] == arg[0][0]:
                        arg.append(args.pop(j))
                    else:
                        j += 1
                if field._fnct_search:
                    args.extend(field.search(cursor, user, table,
                        arg[0][0], arg, context=context))
            elif field._type == 'one2many':
                field_obj = self.pool.get(field._obj)

                if isinstance(args[i][2], basestring):
                    # get the ids of the records of the "distant" resource
                    ids2 = [x[0] for x in field_obj.name_search(cursor, user,
                        args[i][2], [], args[i][1], context=context)]
                else:
                    ids2 = args[i][2]

                table_query = ''
                table_args = []
                if field_obj.table_query(context):
                    table_query, table_args = field_obj.table_query(context)
                    table_query = '(' + table_query + ') AS '

                if ids2 == True or ids2 == False:
                    query1 = 'SELECT "' + field._field + '" ' \
                            'FROM ' + table_query + '"' + field_obj._table + '" ' \
                            'WHERE "' + field._field + '" IS NOT NULL'
                    query2 = table_args
                    clause = 'inselect'
                    if ids2 == False:
                        clause = 'notinselect'
                    args[i] = ('id', clause, (query1, query2))
                elif not ids2:
                    args[i] = ('id', '=', '0')
                else:
                    if len(ids2) < cursor.IN_MAX:
                        query1 = 'SELECT "' + field._field + '" ' \
                                'FROM ' + table_query + '"' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join(['%s' for x in ids2]) + ')'
                        query2 = table_args + ids2
                        args[i] = ('id', 'inselect', (query1, query2))
                    else:
                        ids3 = []
                        for i in range(0, len(ids2), cursor.IN_MAX):
                            sub_ids2 = ids2[i:i + cursor.IN_MAX]
                            cursor.execute(
                                'SELECT "' + field._field + \
                                '" FROM ' + table_query + '"' + field_obj._table + '" ' \
                                'WHERE id IN (' + \
                                    ','.join(['%s' for x in sub_ids2]) + ')',
                                table_args + sub_ids2)

                            ids3.extend([x[0] for x in cursor.fetchall()])

                        args[i] = ('id', 'in', ids3)
                i += 1
            elif field._type == 'many2many':
                # XXX must find a solution for long id list
                if args[i][1] in ('child_of', 'not child_of'):
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
                        if len(args[i]) != 4:
                            raise Exception('Error', 'Programming error: ' \
                                    'child_of on field "%s" is not allowed!' % \
                                    (args[i][0],))
                        ids2 = self.pool.get(field._obj).search(cursor, user,
                                [(args[i][3], 'child_of', ids2)],
                                context=context)
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + field._rel + '" ' \
                                'WHERE "' + field.target + '" IN (' + \
                                    ','.join(['%s' for x in ids2]) + ') ' \
                                    'AND "' + field.origin + '" IS NOT NULL'
                        query2 = [str(x) for x in ids2]
                        if args[i][1] == 'child_of':
                            args[i] = ('id', 'inselect', (query1, query2))
                        else:
                            args[i] = ('id', 'notinselect', (query1, query2))
                    else:
                        if args[i][1] == 'child_of':
                            args[i] = ('id', 'in', ids2 + _rec_get(ids2,
                                table, args[i][0]))
                        else:
                            args[i] = ('id', 'not in', ids2 + _rec_get(ids2,
                                table, args[i][0]))
                else:
                    if isinstance(args[i][2], basestring):
                        res_ids = [x[0] for x in self.pool.get(field._obj
                            ).name_search(cursor, user, args[i][2], [],
                                args[i][1], context=context)]
                    else:
                        res_ids = args[i][2]
                    if res_ids == True or res_ids == False:
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + field._rel + '" '\
                                'WHERE "' + field.origin + '" IS NOT NULL'
                        query2 = []
                        clause = 'inselect'
                        if res_ids == False:
                            clause = 'notinselect'
                        args[i] = ('id', clause, (query1, query2))
                    elif not res_ids:
                        args[i] = ('id', '=', '0')
                    else:
                        query1 = 'SELECT "' + field.origin + '" ' \
                                'FROM "' + field._rel + '" ' \
                                'WHERE "' + field.target + '" IN (' + \
                                    ','.join(['%s' for x in res_ids]) + ')'
                        query2 = [str(x) for x in res_ids]
                        args[i] = ('id', 'inselect', (query1, query2))
                i += 1

            elif field._type == 'many2one':
                # XXX must find a solution for long id list
                if args[i][1] in ('child_of', 'not child_of'):
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
                        if len(args[i]) != 4:
                            raise Exception('Error', 'Programming error: ' \
                                    'child_of on field "%s" is not allowed!' % \
                                    (args[i][0],))
                        ids2 = self.pool.get(field._obj).search(cursor, user,
                                [(args[i][3], 'child_of', ids2)],
                                context=context)
                        if args[i][1] == 'child_of':
                            args[i] = (args[i][0], 'in', ids2, table)
                        else:
                            args[i] = (args[i][0], 'not in', ids2, table)
                    else:
                        if field.left and field.right:
                            cursor.execute('SELECT "' + field.left + '", ' \
                                        '"' + field.right + '" ' + \
                                    'FROM "' + self._table + '" ' + \
                                    'WHERE id IN ' + \
                                        '(' + ','.join(['%s' for x in ids2]) + ')',
                                        ids2)
                            clause = 'false '
                            for left, right in cursor.fetchall():
                                clause += 'OR '
                                clause += '( "' + field.left + '" >= ' + \
                                        str(left) + ' ' + \
                                        'AND "' + field.right + '" <= ' + \
                                        str(right) + ')'

                            query = 'SELECT id FROM "' + self._table + '" ' + \
                                    'WHERE ' + clause
                            if args[i][1] == 'child_of':
                                args[i] = ('id', 'inselect', (query, []))
                            else:
                                args[i] = ('id', 'notinselect', (query, []))
                        else:
                            if args[i][1] == 'child_of':
                                args[i] = ('id', 'in', ids2 + _rec_get(
                                    ids2, table, args[i][0]), table)
                            else:
                                args[i] = ('id', 'not in', ids2 + _rec_get(
                                    ids2, table, args[i][0]), table)
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
                    exprs = ['%s', '%s']
                    if args[i][1] in ('like', 'ilike', 'not like', 'not ilike'):
                        exprs = ['%% %s%%', '%s%%']
                    oper = 'OR'
                    if args[i][1] in ('not like', 'not ilike', '!='):
                        oper = 'AND'

                    if self._name == 'ir.model':
                        table_join = 'LEFT JOIN "ir_translation" ' \
                                'ON (ir_translation.name = ' \
                                        'ir_model.model||\',%s\' ' \
                                    'AND ir_translation.res_id = 0' \
                                    'AND ir_translation.lang = %%s ' \
                                    'AND ir_translation.type = \'model\' ' \
                                    'AND ir_translation.fuzzy = false)' % \
                                (args[i][0],)
                    elif self._name == 'ir.model.field':
                        if args[i][0] == 'field_description':
                            ttype = 'field'
                        else:
                            ttype = 'help'
                        table_join = 'LEFT JOIN "ir_model" ' \
                                'ON ir_model.id = ir_model_field.model ' \
                                'LEFT JOIN "ir_translation" ' \
                                'ON (ir_translation.name = ' \
                                        'ir_model.model||\',\'||%s.name ' \
                                    'AND ir_translation.res_id = 0' \
                                    'AND ir_translation = %%s ' \
                                    'AND ir_translation.type = \'%s\' ' \
                                    'AND ir_translation.fuzzy = false)' % \
                                (table._table, ttype)
                    else:
                        table_join = 'LEFT JOIN "ir_translation" ' \
                                'ON (ir_translation.res_id = %s.id ' \
                                    'AND ir_translation.name = \'%s,%s\' ' \
                                    'AND ir_translation.lang = %%s ' \
                                    'AND ir_translation.type = \'model\' ' \
                                    'AND ir_translation.fuzzy = false)' % \
                                (table._table, table._name, args[i][0])
                    table_join_args = [context.get('language') or 'en_US']

                    table_query = ''
                    table_args = []
                    if table.table_query(context):
                        table_query, table_args = table.table_query(context)
                        table_query = '(' + table_query  + ') AS '

                    trans_field = 'COALESCE(NULLIF(' \
                            'ir_translation.value, \'\'), ' \
                            + table._table + '.' + args[i][0] + ')'

                    query1 = '(SELECT ' + table._table + '.id ' \
                            'FROM ' + table_query + '"' + table._table + '" ' \
                            + table_join + ' ' \
                            'WHERE (' + trans_field + ' ' + \
                            args[i][1] + ' %s ' + oper + ' ' + trans_field + ' ' + \
                            args[i][1] + ' %s))'
                    query2 = table_args + table_join_args + [exprs[0] % args[i][2],
                            exprs[1] % args[i][2]]
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
            elif arg[1] in ('in', 'not in'):
                if len(arg[2]) > 0:
                    todel = []
                    for xitem in range(len(arg[2])):
                        if arg[2][xitem] == False \
                                and isinstance(arg[2][xitem],bool):
                            todel.append(xitem)
                    arg2 = arg[2][:]
                    for xitem in todel[::-1]:
                        del arg2[xitem]
                    #TODO fix max_stack_depth
                    if len(arg2):
                        if arg[0] == 'id':
                            qu1.append(('(%s.id ' + arg[1] + ' (%s))') % \
                                    (table._table,
                                        ','.join(['%s'] * len(arg2)),))
                        else:
                            qu1.append(('(%s.%s ' + arg[1] + ' (%s))') % \
                                    (table._table, arg[0], ','.join(
                                        [table._columns[arg[0]].\
                                                _symbol_set[0]] * len(arg2))))
                        if todel:
                            if table._columns[arg[0]]._type == 'boolean':
                                if arg[1] == 'in':
                                    qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                            '%s.%s = false)' % \
                                            (table._table, arg[0])
                                else:
                                    qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                            '%s.%s != false)' % \
                                            (table._table, arg[0])
                            else:
                                if arg[1] == 'in':
                                    qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                            '%s.%s IS NULL)' % \
                                            (table._table, arg[0])
                                else:
                                    qu1[-1] = '(' + qu1[-1] + ' OR ' \
                                            '%s.%s IS NOT NULL)' % \
                                            (table._table, arg[0])
                        qu2 += arg2
                    elif todel:
                        if table._columns[arg[0]]._type == 'boolean':
                            if arg[1] == 'in':
                                qu1.append('(%s.%s = false)' % \
                                        (table._table, arg[0]))
                            else:
                                qu1.append('(%s.%s != false)' % \
                                        (table._table, arg[0]))
                        else:
                            if arg[1] == 'in':
                                qu1.append('(%s.%s IS NULL)' % \
                                        (table._table, arg[0]))
                            else:
                                qu1.append('(%s.%s IS NOT NULL)' % \
                                        (table._table, arg[0]))
                else:
                    if arg[1] == 'in':
                        qu1.append(' false')
                    else:
                        qu1.append(' true')
            else:
                if (arg[2] is False) and (arg[1] == '='):
                    if table._columns[arg[0]]._type == 'boolean':
                        qu1.append('(%s.%s = false)' % \
                                (table._table, arg[0]))
                    else:
                        qu1.append('(%s.%s IS NULL)' % \
                                (table._table, arg[0]))
                elif (arg[2] is False) and (arg[1] == '!='):
                    qu1.append('(%s.%s IS NOT NULL)' % \
                            (table._table, arg[0]))
                else:
                    if arg[0] == 'id':
                        qu1.append('(%s.%s %s %%s)' % \
                                (table._table, arg[0], arg[1]))
                        qu2.append(arg[2])
                    else:
                        add_null = False
                        if arg[1] in ('like', 'ilike', 'not like', 'not ilike'):
                            qu2.append('%% %s%%' % arg[2])
                            qu2.append('%s%%' % arg[2])
                            if not arg[2]:
                                add_null = True
                        else:
                            if arg[0] in table._columns:
                                qu2.append(table._columns[arg[0]].\
                                        _symbol_set[1](arg[2]))
                        if arg[0] in table._columns:
                            if arg[1] in ('like', 'ilike'):
                                qu1.append('(%s.%s %s %s OR %s.%s %s %s)' % \
                                        (table._table, arg[0], arg[1], '%s',
                                            table._table, arg[0], arg[1], '%s'))
                            elif arg[1] in ('not like', 'not ilike'):
                                qu1.append('(%s.%s %s %s AND %s.%s %s %s)' % \
                                        (table._table, arg[0], arg[1], '%s',
                                            table._table, arg[0], arg[1], '%s'))
                            else:
                                qu1.append('(%s.%s %s %s)' % (table._table,
                                    arg[0], arg[1],
                                    table._columns[arg[0]]._symbol_set[0]))
                        else:
                            if arg[1] in ('like', 'ilike'):
                                qu1.append('(%s.%s %s \'%s\' or %s.%s %s \'%s\')' % \
                                        (table._table, arg[0], arg[1], arg[2],
                                            table._table, arg[0], arg[1], arg[2]))
                            elif arg[1] in ('not like', 'not ilike'):
                                qu1.append('(%s.%s %s \'%s\' and %s.%s %s \'%s\')' % \
                                        (table._table, arg[0], arg[1], arg[2],
                                            table._table, arg[0], arg[1], arg[2]))
                            else:
                                qu1.append('(%s.%s %s \'%s\')' % \
                                        (table._table, arg[0], arg[1], arg[2]))

                        if add_null:
                            qu1[-1] = '('+qu1[-1]+' OR '+arg[0]+' is null)'

        return qu1, qu2

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
        tables_args = {}
        field_name = None
        table_name = None
        link_field = None

        if context is None:
            context = {}

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
                    order_by, tables, tables_args = obj._order_calc(cursor,
                            user, field_name, otype, context=context)
                    if table_name == self._table:
                        table_join = 'LEFT JOIN "' + table_name + '" AS ' \
                                '"' + table_name + '.' + link_field + '" ON ' \
                                '"%s.%s".id = %s.%s' % (table_name, link_field,
                                        self._table, link_field)
                        for i in range(len(order_by)):
                            if table_name in order_by[i]:
                                order_by[i] = order_by[i].replace(table_name,
                                        '"' + table_name + '.' + \
                                                link_field + '"')
                    else:
                        table_join = 'LEFT JOIN "' + table_name + '" ON ' \
                                '%s.id = %s.%s' % (table_name, self._table,
                                        link_field)
                    if table_join not in tables:
                        tables.insert(0, table_join)
                    return order_by, tables, tables_args

                obj2 = None
                if obj._rec_name in obj._inherit_fields.keys():
                    obj2 = self.pool.get(
                            obj._inherit_fields[obj._rec_name][0])
                    field_name = obj._rec_name

                if obj._order_name in obj._inherit_fields.keys():
                    obj2 = self.pool.get(
                            obj._inherit_fields[obj._order_name][0])
                    field_name = obj._order_name

                if obj2 and field_name:
                    table_name2 = obj2._table
                    link_field2 = obj._inherits[obj2._name]
                    order_by, tables, tables_args = obj2._order_calc(cursor,
                            user, field_name, otype, context=context)

                    table_join = 'LEFT JOIN "' + table_name + '" ON ' \
                            '%s.id = %s.%s' % \
                            (table_name, self._table, link_field)
                    if table_join not in tables:
                        tables.insert(0, table_join)

                    table_join2 = 'LEFT JOIN "' + table_name2 + '" ON ' \
                            '%s.id = %s.%s' % \
                            (table_name2, obj._table, link_field2)
                    if table_join2 not in tables:
                        tables.insert(1, table_join2)
                    return order_by, tables, tables_args

            if field_name in self._columns \
                    and self._columns[field_name].translate:
                translation_table = 'ir_translation_%s_%s' % \
                        (table_name, field_name)
                if self._name == 'ir.model':
                    table_join = 'LEFT JOIN "ir_translation" ' \
                            'AS "%s" ON ' \
                            '(%s.name = ir_model.model||\',%s\' ' \
                                'AND %s.res_id = 0 ' \
                                'AND %s.lang = %%s ' \
                                'AND %s.type = \'model\' ' \
                                'AND %s.fuzzy = false)' % \
                            (translation_table, translation_table, field_name,
                                    translation_table, translation_table,
                                    translation_table, translation_table)
                elif self._name == 'ir.model.field':
                    if field_name == 'field_description':
                        ttype = 'field'
                    else:
                        ttype = 'help'
                    table_join = 'LEFT JOIN "ir_model" ON ' \
                            'ir_model.id = ir_model_field.model'
                    if table_join not in tables:
                        tables.append(table_join)
                    table_join = 'LEFT JOIN "ir_translation" ' \
                            'AS "%s" ON ' \
                            '(%s.name = ir_model.model||\',\'||%s.name ' \
                                'AND %s.res_id = 0 ' \
                                'AND %s.lang = %%s ' \
                                'AND %s.type = \'%s\' ' \
                                'AND %s.fuzzy = false)' % \
                            (translation_table, translation_table, table_name,
                                    translation_table, translation_table,
                                    translation_table, ttype, translation_table)
                else:
                    table_join = 'LEFT JOIN "ir_translation" ' \
                            'AS "%s" ON ' \
                            '(%s.res_id = %s.id ' \
                                'AND %s.name = \'%s,%s\' ' \
                                'AND %s.lang = %%s ' \
                                'AND %s.type = \'model\' ' \
                                'AND %s.fuzzy = false)' % \
                            (translation_table, translation_table, table_name,
                                    translation_table, self._name, field_name,
                                    translation_table, translation_table,
                                    translation_table)
                if table_join not in tables:
                    tables.append(table_join)
                    tables_args[table_join] = [context.get('language') or 'en_US']
                order_by.append('COALESCE(NULLIF(' \
                        + translation_table + '.value, \'\'), ' \
                        + table_name + '.' + field_name + ') ' + otype)
                return order_by, tables, tables_args

            if field_name in self._columns \
                    and self._columns[field_name]._type == 'selection' \
                    and self._columns[field_name].order_field is None:
                selections = self.fields_get(cursor, user, [field_name],
                        context=context)[field_name]['selection']
                if not isinstance(selections, (tuple, list)):
                    selections = getattr(self,
                            self._columns[field_name].selection)(cursor,
                                    user, context=context)
                order = 'CASE ' + table_name + '.' + field_name
                for selection in selections:
                    order += ' WHEN \'%s\' THEN \'%s\'' % selection
                order += ' ELSE ' + table_name + '.' + field_name + ' END'
                order_by.append(order + ' ' + otype)
                return order_by, tables, tables_args

            if field_name:
                if '%(table)s' in field_name or '%(order)s' in field_name:
                    order_by.append(field_name % {
                        'table': table_name,
                        'order': otype,
                        })
                else:
                    order_by.append(table_name + '.' + field_name + ' ' + otype)
                return order_by, tables, tables_args

        if field in self._inherit_fields.keys():
            obj = self.pool.get(self._inherit_fields[field][0])
            table_name = obj._table
            link_field = self._inherits[obj._name]
            order_by, tables, tables_args = obj._order_calc(cursor, user, field,
                    otype, context=context)
            table_join = 'LEFT JOIN "' + table_name + '" ON ' \
                    '%s.id = %s.%s' % \
                    (table_name, self._table, link_field)
            if table_join not in tables:
                tables.insert(0, table_join)
            return order_by, tables, tables_args

        raise Exception('Error', 'Wrong field name (%s) in order!' \
                % field)

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        '''
        Return a list of id that match the clause defined in args.

        :param cursor: the database cursor
        :param user: the user id
        :param args: a list of tuples or lists
            lists are construct like this:
                ['operator', args, args, ...]
                operator can be 'AND' or 'OR', if it is missing the
                default value will be 'AND'
            tuples are construct like this:
                ('field name', 'operator', value)
                field name: is the name of a field of the object
                    or a relational field by using '.' as separator.
                operator must be in OPERATORS
        :param offset: an integer to specify the offset in the result
        :param limit: an integer to limit the number of ids return
        :param order: a list of tupe that are construct like this:
            ('field name', 'DESC|ASC')
            it allow to specify the order of the ids in the return list
        :param count: a boolean to return just the len of the list
        :param query_string: a boolean to return a tuple with
            the SQL query string and the arguments.
        :return: a list of ids
        '''
        (qu1, qu2, tables, tables_args) = self._where_calc(cursor, user, args,
                context=context)

        order_by = []
        for field, otype in (order or self._order):
            if otype.upper() not in ('DESC', 'ASC'):
                raise Exception('Error', 'Wrong order type (%s)!' % otype)
            order_by2, tables2, tables2_args = self._order_calc(cursor, user,
                    field, otype, context=context)
            order_by += order_by2
            for table in tables2:
                if table not in tables:
                    tables.append(table)
                    if tables2_args.get(table):
                        tables_args.extend(tables2_args.get(table))

        order_by = ','.join(order_by)

        limit_str = limit and (type(limit) in (float, int, long))\
                    and ' LIMIT %d' % limit or ''
        offset_str = offset and (type(offset) in (float, int, long))\
                     and ' OFFSET %d' % offset or ''


        # construct a clause for the rules :
        domain1, domain2 = self.pool.get('ir.rule').domain_get(cursor, user,
                self._name, context=context)
        if domain1:
            if qu1:
                qu1 += ' AND ' + domain1
            else:
                qu1 = domain1
            qu2 += domain2

        if count:
            cursor.execute('SELECT COUNT(%s.id) FROM ' % self._table +
                    ' '.join(tables) + ' WHERE ' + (qu1 or 'True') +
                    limit_str + offset_str, tables_args + qu2)
            res = cursor.fetchall()
            return res[0][0]
        # execute the "main" query to fetch the ids we were searching for
        query_str = 'SELECT %s.id FROM ' % self._table + \
                ' '.join(tables) + ' WHERE ' + (qu1 or 'True') + \
                ' ORDER BY ' + order_by + limit_str + offset_str
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
            args = ['AND', args, (self._rec_name, operator, name)]
        ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        '''
        Duplicate the record in ids.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids or an id
        :param default: a dictionnary with field name as keys and
            new value for the field as value
        :param context: the context
        :return: a list of new ids or the new id
        '''
        lang_obj = self.pool.get('ir.lang')
        if default is None:
            default = {}
        if context is None:
            context = {}

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if 'state' not in default:
            if 'state' in self._defaults:
                default['state'] = self._defaults['state'](cursor, user,
                        context)

        def convert_data(fields, data):
            for field_name in fields:
                ftype = fields[field_name]['type']

                if field_name in (
                    'create_date',
                    'create_uid',
                    'write_date',
                    'write_uid',
                    ):
                    del data[field_name]

                if field_name in default:
                    data[field_name] = default[field_name]
                elif ftype == 'function':
                    del data[field_name]
                elif ftype == 'many2one':
                    try:
                        data[field_name] = data[field_name] and \
                                data[field_name][0]
                    except:
                        pass
                elif ftype in ('one2many',):
                    res = []
                    rel = self.pool.get(fields[field_name]['relation'])
                    if data[field_name]:
                        data[field_name] = [('add', rel.copy(cursor, user,
                            data[field_name], context=context))]
                    else:
                        data[field_name] = False
                elif ftype == 'many2many':
                    if data[field_name]:
                        data[field_name] = [('set', data[field_name])]
            if 'id' in data:
                del data['id']
            for i in self._inherits:
                if self._inherits[i] in data:
                    del data[self._inherits[i]]

        new_ids = []
        datas = self.read(cursor, user, ids, context=context)
        fields = self.fields_get(cursor, user, context=context)
        for data in datas:
            convert_data(fields, data)
            new_ids.append(self.create(cursor, user, data, context=context))

        fields_translate = {}
        for field_name, field in fields.iteritems():
            if field_name in self._columns and \
                    self._columns[field_name].translate:
                fields_translate[field_name] = field
            elif field_name in self._inherit_fields and \
                    self._inherit_fields[field_name][2].translate:
                fields_translate[field_name] = field

        if fields_translate:
            lang_ids = lang_obj.search(cursor, user, [
                ('translatable', '=', True),
                ], context=context)
            if lang_ids:
                lang_ids += lang_obj.search(cursor, user, [
                    ('code', '=', 'en_US'),
                    ], context=context)
                langs = lang_obj.browse(cursor, user, lang_ids, context=context)
                for lang in langs:
                    ctx = context.copy()
                    ctx['language'] = lang.code
                    datas = self.read(cursor, user, ids,
                            fields_names=fields_translate.keys() + ['id'],
                            context=ctx)
                    for data in datas:
                        data_id = data['id']
                        convert_data(fields_translate, data)
                        self.write(cursor, user, data_id, data, context=ctx)
        if int_id:
            return new_ids[0]
        return new_ids

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
            for i in range(0, len(ids_parent), cursor.IN_MAX):
                sub_ids_parent = ids_parent[i:i + cursor.IN_MAX]
                cursor.execute('SELECT distinct "' + parent + '" ' +
                    'FROM "' + self._table + '" ' +
                    'WHERE id IN ' \
                        '(' + ','.join(['%s' for x in sub_ids_parent]) + ')',
                        sub_ids_parent)
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

        child_ids = self.search(cursor, 0, [
            (parent, '=', parent_id),
            ])

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
        Remarks:
            - the value (right - left - 1) / 2 will not give
                the number of children node
            - the order of the tree respects the default _order
        '''
        cursor.execute('SELECT "' + left + '", "' + right + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id = %s', (object_id,))
        if not cursor.rowcount:
            return
        old_left, old_right = cursor.fetchone()
        if old_left == old_right:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + right + '" = "' + right + '" + 1 ' \
                    'WHERE id = %s', (object_id,))
            old_right += 1

        parent_right = 1

        cursor.execute('SELECT "' + field_name + '" ' \
                'FROM "' + self._table + '" ' \
                'WHERE id = %s', (object_id,))
        parent_id = cursor.fetchone()[0] or False

        if parent_id:
            cursor.execute('SELECT "' + right + '" ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (parent_id,))
            parent_right = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT MAX("' + right + '") ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE "' + field_name + '" IS NULL')
            if cursor.rowcount:
                parent_right = cursor.fetchone()[0] + 1

        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                (old_left, old_right))
        child_ids = [x[0] for x in cursor.fetchall()]

        # ids for left update
        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + left + '" >= %s ' \
                    'AND id NOT IN (' + ','.join(['%s' for x in child_ids]) + ')',
                    [parent_right] + child_ids)
        left_ids = [x[0] for x in cursor.fetchall()]

        # ids for right update
        cursor.execute('SELECT id FROM "' + self._table + '" ' \
                'WHERE "' + right + '" >= %s ' \
                    'AND id NOT IN (' + ','.join(['%s' for x in child_ids]) + ')',
                    [parent_right] + child_ids)
        right_ids = [x[0] for x in cursor.fetchall()]

        if left_ids:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + ' \
                        + str(old_right - old_left + 1) + ' ' \
                    'WHERE id IN (' + ','.join(['%s' for x in left_ids]) + ')',
                    left_ids)
        if right_ids:
            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + right + '" = "' + right + '" + ' \
                        + str(old_right - old_left + 1) + ' ' \
                    'WHERE id IN (' + ','.join(['%s' for x in right_ids]) + ')',
                    right_ids)

        cursor.execute('UPDATE "' + self._table + '" ' \
                'SET "' + left + '" = "' + left + '" + ' \
                        + str(parent_right - old_left) + ', ' \
                    '"' + right + '" = "' + right + '" + ' \
                        + str(parent_right - old_left) + ' ' \
                'WHERE id IN (' + ','.join(['%s' for x in child_ids]) + ')',
                child_ids)

        # Use root user to by-pass rules
        brother_ids = self.search(cursor, 0, [
            (field_name, '=', parent_id),
            ])
        if brother_ids[-1] != object_id:
            next_id = brother_ids[brother_ids.index(object_id) + 1]
            cursor.execute('SELECT "' + left + '",  "' + right + '" ' \
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (next_id,))
            next_left, next_right = cursor.fetchone()
            cursor.execute('SELECT "' + left + '", "' + right + '" '\
                    'FROM "' + self._table + '" ' \
                    'WHERE id = %s', (object_id,))
            current_left, current_right = cursor.fetchone()


            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" + ' \
                            + str(old_right - old_left + 1) + ', ' \
                        '"' + right + '" = "' + right + '" + ' \
                            + str(old_right - old_left + 1) + ' ' \
                    'WHERE "' + left + '" >= %s AND "' + right + '" <= %s',
                    (next_left, current_left))

            cursor.execute('UPDATE "' + self._table + '" ' \
                    'SET "' + left + '" = "' + left + '" - ' \
                            + str(current_left - next_left) + ', ' \
                        '"' + right + '" = "' + right + '" - ' \
                            + str(current_left - next_left) + ' ' \
                    'WHERE id in (' + ','.join(['%s' for x in child_ids]) + ')',
                    child_ids)
