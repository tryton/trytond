"""
 Fields:
      - simple
      - relations (one2many, many2one, many2many)
      - function

 Fields Attributes:
   _classic_read: is a classic sql fields
   _type   : field type
   readonly
   required
   size

 Relationals fields

 Values: (0, 0,  { fields })    create
         (1, ID, { fields })    modification
         (2, ID)                remove (delete)
         (3, ID)                unlink one (target id or target of relation)
         (4, ID)                link
         (5, ID)                unlink all (only valid for one2many)
         (6, ?, ids)            set a list of links
"""

import psycopg2
import warnings
import __builtin__
import sha

def _symbol_f(symb):
    if symb == None or symb == False:
        return None
    elif isinstance(symb, unicode):
        return symb.encode('utf-8')
    return str(symb)

class Column(object):
    _classic_read = True
    _classic_write = True
    _properties = False
    _type = 'unknown'
    _obj = None
    _symbol_c = '%s'
    _symbol_f = _symbol_f
    _symbol_set = (_symbol_c, _symbol_f)
    _symbol_get = None

    def __init__(self, string='unknown', required=False, readonly=False,
            domain=None, context='', states=None, priority=0,
            change_default=False, size=None, ondelete="set null",
            translate=False, select=False, on_change=None, **args):
        self.states = states or {}
        self.string = string
        self.readonly = readonly
        self.required = required
        self.size = size
        self.help = args.get('help', '')
        self.priority = priority
        self.change_default = change_default
        self.ondelete = ondelete
        self.translate = translate
        self._domain = domain or []
        self._context = context
        self.group_name = False
        self.view_load = 0
        self.select = select
        self.on_change = on_change
        for i in args:
            if args[i]:
                setattr(self, i, args[i])

    def set(self, cursor, obj, obj_id, name, value, user=None, context=None):
        raise Exception('undefined get method!')

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        raise Exception('undefined get method!')

    def sql_type(self):
        raise Exception('undefined sql_type method!')


class Boolean(Column):
    _type = 'boolean'
    _symbol_c = '%s'
    _symbol_f = lambda x: x and 'True' or 'False'
    _symbol_set = (_symbol_c, _symbol_f)

    def sql_type(self):
        return ('bool', 'bool')

boolean = Boolean


class Integer(Column):
    _type = 'integer'
    _symbol_c = '%s'
    _symbol_f = lambda x: int(x or 0)
    _symbol_set = (_symbol_c, _symbol_f)

    def sql_type(self):
        return ('int4', 'int4')

integer = Integer


class Reference(Column):
    _type = 'reference'

    def __init__(self, string, selection, size, **args):
        Column.__init__(self, string=string, size=size, selection=selection,
                **args)

    def sql_type(self):
        return ('varchar', 'varchar(%d)' % (self.size,))

reference = Reference


class Char(Column):
    _type = 'char'

    def __init__(self, string, size, **args):
        Column.__init__(self, string=string, size=size, **args)
        self._symbol_set = (self._symbol_c, self._symbol_set_char)

    def _symbol_set_char(self, symb):
        """
        takes a string (encoded in utf8)
        and returns a string (encoded in utf8)
        """
        #TODO we need to remove the "symb==False" from the next line BUT
        #TODO for now too many things rely on this broken behavior
        #TODO the symb==None test should be common to all data types
        if symb == None or symb == False:
            return None

        # we need to convert the string to a unicode object to be able
        # to evaluate its length (and possibly truncate it) reliably
        if isinstance(symb, str):
            u_symb = unicode(symb, 'utf8')
        elif isinstance(symb, unicode):
            u_symb = symb
        else:
            u_symb = unicode(symb)
        return u_symb.encode('utf8')

    def sql_type(self):
        if self.size:
            return ('varchar', 'varchar(%d)' % (self.size,))
        else:
            return ('varchar', 'varchar')

char = Char


class Sha(Column):
    _type = 'sha'

    def __init__(self, string, **args):
        Column.__init__(self, string=string, size=40, **args)
        self._symbol_f = lambda x: x and sha.new(x).hexdigest() or ''
        self._symbol_set = (self._symbol_c, self._symbol_f)

    def sql_type(self):
        return ('varchar', 'varchar(40)')


class Text(Column):
    _type = 'text'

    def sql_type(self):
        return ('text', 'text')

text = Text


class Float(Column):
    _type = 'float'
    _symbol_c = '%s'
    _symbol_f = lambda x: __builtin__.float(x or 0.0)
    _symbol_set = (_symbol_c, _symbol_f)

    def __init__(self, string='unknown', digits=None, **args):
        Column.__init__(self, string=string, **args)
        self.digits = digits

    def sql_type(self):
        return ('float8', 'float8')

float = Float


class Numeric(Float):
    _type = 'numeric'

    def __init__(self, string='unknown', digits=None, **args):
        Float.__init__(self, string=string, digits=digits, **args)
        if self.digits:
            self._symbol_f = lambda x: round(x, self.digits[1])
            self._symbol_set = (self._symbol_c, self._symbol_f)

    def sql_type(self):
        return ('numeric', 'numeric')

numeric = Numeric


class Date(Column):
    _type = 'date'

    def sql_type(self):
        return ('date', 'date')

date = Date


class DateTime(Column):
    _type = 'datetime'

    def sql_type(self):
        return ('timestamp', 'timestamp')

datetime = DateTime


class Time(Column):
    _type = 'time'

    def sql_type(self):
        return ('time', 'time')

time = Time


class Binary(Column):
    _type = 'binary'
    _symbol_c = '%s'
    _symbol_f = lambda symb: symb and psycopg2.Binary(symb) or None
    _symbol_set = (_symbol_c, _symbol_f)

    def sql_type(self):
        return ('bytea', 'bytea')

binary = Binary


class Selection(Column):
    _type = 'selection'

    def __init__(self, selections, string='unknown', **args):
        """
        selections is a list of (key, string)
            or the name of the object function that return the list
        """
        Column.__init__(self, string=string, selection=selections, **args)

    def sql_type(self):
        return ('varchar', 'varchar')

selection = Selection


class One2One(Column):
    _classic_read = False
    _classic_write = True
    _type = 'one2one'

    def __init__(self, obj, string='unknown', **args):
        warnings.warn("The one2one field doesn't work anymore",
                DeprecationWarning)
        Column.__init__(self, string=string, **args)
        self._obj = obj

    def set(self, cursor, obj_src, src_id, field, act, user=None, context=None):
        if context is None:
            context = {}
        obj = obj_src.pool.get(self._obj)
        if act[0] == 0:
            id_new = obj.create(cursor, user, act[1])
            cursor.execute('UPDATE "' + obj_src._table + '" ' \
                    'SET "' + field + '" = %s ' \
                    'WHERE id = %s', (id_new, src_id))
        else:
            cursor.execute('SELECT "' + field + '" ' \
                    'FROM "' + obj_src._table + '" ' \
                    'WHERE id = %s', (act[0],))
            (obj_id,) = cursor.fetchone()
            obj.write(cursor, user, [obj_id] , act[1], context=context)

one2one = One2One


class Many2One(Column):
    _classic_read = False
    _classic_write = True
    _type = 'many2one'

    def __init__(self, obj, string='unknown', **args):
        Column.__init__(self, string=string, **args)
        self._obj = obj

    # TODO: speed improvement
    # name is the name of the relation field
    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name]
        for i in ids:
            res.setdefault(i, '')
        obj = obj.pool.get(self._obj)
        obj_names = {}
        for obj_id, name in obj.name_get(cursor, user,
                [ x for x in res.values() if x],
                context=context):
            obj_names[obj_id] = name

        for i in res.keys():
            if res[i] and res[i] in obj_names:
                res[i] = (res[i], obj_names[res[i]])
            else:
                res[i] = False
        return res

    def set(self, cursor, obj_src, obj_id, field, values, user=None,
            context=None):
        if context is None:
            context = {}
        obj = obj_src.pool.get(self._obj)
        table = obj_src.pool.get(self._obj)._table
        if type(values) == type([]):
            for act in values:
                if act[0] == 0:
                    id_new = obj.create(cursor, act[2])
                    cursor.execute('UPDATE "' + obj_src._table + '" ' \
                            'SET "' + field + '" = %s ' \
                            'WHERE id = %s', (id_new, obj_id))
                elif act[0] == 1:
                    obj.write(cursor, [act[1]], act[2], context=context)
                elif act[0] == 2:
                    cursor.execute('DELETE FROM "' + table + '" ' \
                            'WHERE id = %s', (act[1],))
                elif act[0] == 3 or act[0] == 5:
                    cursor.execute('UPDATE "' + obj_src._table + '" ' \
                            'SET "' + field + '" = NULL ' \
                            'WHERE id = %s', (obj_id,))
                elif act[0] == 4:
                    cursor.execute('UPDATE "' + obj_src._table + '" ' \
                            'SET "' + field + '" = %s ' \
                            'WHERE id = %s', (act[1], obj_id))
        else:
            if values:
                cursor.execute('UPDATE "' + obj_src._table + '" ' \
                        'SET "' + field + '" = %s ' \
                        'WHERE id = %s', (values, obj_id))
            else:
                cursor.execute('UPDATE "' + obj_src._table + '" ' \
                        'SET "' + field + '" = NULL ' \
                        'WHERE id = %s', (obj_id,))

    def sql_type(self):
        return ('int4', 'int4')

many2one = Many2One


class One2Many(Column):
    _classic_read = False
    _classic_write = False
    _type = 'one2many'

    def __init__(self, obj, field, string='unknown', limit=None, **args):
        Column.__init__(self, string=string, **args)
        self._obj = obj
        self._field = field
        self._limit = limit
        #one2many can't be used as condition for defaults
        assert(self.change_default != True)

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        for i in ids:
            res[i] = []
        ids2 = obj.pool.get(self._obj).search(cursor, user,
                [(self._field, 'in', ids)], offset=offset,
                limit=self._limit, context=context)
        for i in obj.pool.get(self._obj)._read_flat(cursor, user, ids2,
                [self._field], context=context, load='_classic_write'):
            res[i[self._field]].append( i['id'] )
        return res

    def set(self, cursor, obj, obj_id, field, values, user=None, context=None):
        if context is None:
            context = {}
        if not values:
            return
        _table = obj.pool.get(self._obj)._table
        obj = obj.pool.get(self._obj)
        for act in values:
            if act[0] == 0:
                act[2][self._field] = obj_id
                obj.create(cursor, user, act[2], context=context)
            elif act[0] == 1:
                obj.write(cursor, user, [act[1]] , act[2], context=context)
            elif act[0] == 2:
                obj.unlink(cursor, user, [act[1]], context=context)
            elif act[0] == 3:
                cursor.execute('UPDATE "' + _table + '" ' \
                        'SET "' + self._field + '" = NULL ' \
                        'WHERE id = %s', (act[1],))
            elif act[0] == 4:
                cursor.execute('UPDATE "' + _table + '" ' \
                        'SET "' + self._field + '" = %s ' \
                        'WHERE id = %s', (obj_id, act[1]))
            elif act[0] == 5:
                cursor.execute('UPDATE "' + _table + '" ' \
                        'SET "' + self._field + '" = NULL ' \
                        'WHERE "' + self._field + '" = %s', (obj_id,))
            elif act[0] == 6:
                if not act[2]:
                    ids2 = [0]
                else:
                    ids2 = act[2]
                cursor.execute('UPDATE "' + _table + '" ' \
                        'SET "' + self._field + '" = NULL ' \
                        'WHERE "' + self._field + '" = %s ' \
                            'AND id not IN (' + \
                                ','.join([str(x) for x in ids2]) + ')',
                                (obj_id,))
                if act[2]:
                    cursor.execute('UPDATE "' + _table + '" ' \
                            'SET "' + self._field + '" = %s ' \
                            'WHERE id IN (' + \
                                ','.join([str(x) for x in act[2]]) + ')',
                                (obj_id,))

one2many = One2Many


class Many2Many(Column):
    _classic_read = False
    _classic_write = False
    _type = 'many2many'

    def __init__(self, obj, rel, id1, id2, string='unknown', limit=None,
            **args):
        Column.__init__(self, string=string, **args)
        self._obj = obj
        self._rel = rel
        self._id1 = id1
        self._id2 = id2
        self._limit = limit

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        if context is None:
            context = {}
        if values is None:
            values = {}
        res = {}
        if not ids:
            return res
        for i in ids:
            res[i] = []
        ids_s = ','.join([str(x) for x in ids])
        limit_str = self._limit is not None and ' limit %s' % self._limit or ''
        obj = obj.pool.get(self._obj)

        domain1, domain2 = obj.pool.get('ir.rule').domain_get(cursor,
                user, obj._name)
        if domain1:
            domain1 = ' and '+domain1

        cursor.execute('SELECT ' + self._rel + '.' + self._id2 + ', ' + \
                    self._rel + '.' + self._id1 + ' ' \
                'FROM "' + self._rel + '" , "' + obj._table + '" ' \
                'WHERE ' + \
                    self._rel + '.' + self._id1 + ' IN (' + ids_s + ') ' \
                    'AND ' + self._rel + '.' + self._id2 + ' = ' + \
                        obj._table + '.id ' + domain1 + \
                limit_str + ' ORDER BY ' + obj._table + '.' + obj._order + \
                ' offset %s', domain2 + [offset])
        for i in cursor.fetchall():
            res[i[1]].append(i[0])
        return res

    def set(self, cursor, obj, obj_id, name, values, user=None, context=None):
        if context is None:
            context = {}
        if not values:
            return
        obj = obj.pool.get(self._obj)
        for act in values:
            if act[0] == 0:
                idnew = obj.create(cursor, user, act[2])
                cursor.execute('INSERT INTO "' + self._rel + '" ' \
                        '(' + self._id1 + ', ' + self._id2 + ') ' \
                        'VALUES (%s, %s)', (obj_id, idnew))
            elif act[0] == 1:
                obj.write(cursor, user, [act[1]] , act[2], context=context)
            elif act[0] == 2:
                obj.unlink(cursor, user, [act[1]], context=context)
            elif act[0] == 3:
                cursor.execute('DELETE FROM "' + self._rel + '" ' \
                        'WHERE "' + self._id1 + '" = %s ' \
                            'AND "'+ self._id2 + '" = %s', (obj_id, act[1]))
            elif act[0] == 4:
                cursor.execute('INSERT INTO "' + self._rel + '" ' \
                        '(' + self._id1 + ', ' + self._id2 + ') ' \
                        'VALUES (%s, %s)', (obj_id, act[1]))
            elif act[0] == 5:
                cursor.execute('UPDATE "' + self._rel + '" ' \
                        'SET "' + self._id2 + '" = NULL ' \
                        'WHERE "' + self._id2 + '" = %s', (obj_id,))
            elif act[0] == 6:
                domain1, domain2 = obj.pool.get('ir.rule').domain_get(cursor,
                        user, obj._name)
                if domain1:
                    domain1 = ' AND ' + domain1
                cursor.execute('DELETE FROM "' + self._rel + '" ' \
                        'WHERE "' + self._id1 + '" = %s ' \
                            'AND "' + self._id2 + '" IN (' \
                            'SELECT ' + self._rel + '.' + self._id2 + ' ' \
                            'FROM "' + self._rel + '", "' + obj._table + '" ' \
                            'WHERE ' + self._rel + '.' + self._id1 + ' = %s ' \
                                'AND ' + self._rel + '.' + self._id2 + ' = ' + \
                                obj._table + '.id ' + domain1 + ')',
                                [obj_id, obj_id] + domain2)

                for act_nbr in act[2]:
                    cursor.execute('INSERT INTO "' + self._rel + '" ' \
                            '(' + self._id1 + ', ' + self._id2 + ') ' \
                            'VALUES (%s, %s)', (obj_id, act_nbr))

many2many = Many2Many


class Function(Column):
    _classic_read = False
    _classic_write = False
    _properties = True

    def __init__(self, fnct, arg=None, fnct_inv='', fnct_inv_arg=None,
            type='float', fnct_search='', obj=None, **args):
        Column.__init__(self, **args)
        self._obj = obj
        self._fnct = fnct
        self._fnct_inv = fnct_inv
        self._arg = arg
        if 'relation' in args:
            self._obj = args['relation']
        self._fnct_inv_arg = fnct_inv_arg
        if not fnct_inv:
            self.readonly = 1
        self._type = type
        self._fnct_search = fnct_search
        self._symbol_c = eval(self._type)._symbol_c
        self._symbol_f = eval(self._type)._symbol_f
        self._symbol_set = (self._symbol_c, self._symbol_f)

    def search(self, cursor, user, obj, name, args, context=None):
        if not self._fnct_search:
            return []
        return getattr(obj, self._fnct_search)(cursor, user, name, args,
                context=context)

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        return getattr(obj, self._fnct)(cursor, user, ids, name, self._arg,
                context=context)

    def set(self, cursor, obj, obj_id, name, value, user=None, context=None):
        if self._fnct_inv:
            getattr(obj, self._fnct_inv)(cursor, user, obj_id, name, value,
                    self._fnct_inv_arg, context=context)

function = Function


class Property(Function):

    def _fnct_write(self, obj, cursor, user, obj_id, prop, id_val, val,
            context=None):
        property_obj = obj.pool.get('ir.property')
        return property_obj.set(cursor, user, prop, obj._name, obj_id,
                (id_val and val + ',' + str(id_val)) or False, context=context)

    def _fnct_read(self, obj, cursor, user, ids, prop, arg, context=None):
        property_obj = obj.pool.get('ir.property')
        res = property_obj.get(cursor, user, prop, obj._name, ids,
                context=context)

        obj = obj.pool.get(self._obj)
        names = obj.name_get(cursor, user, res.values(), context=context)
        for i in res.keys():
            if res[i] and res[i] in names:
                res[i] = (res[i], names[res[i]])
            else:
                res[i] = False
        return res

    def __init__(self, obj_prop, **args):
        function.__init__(self, '', False, self._fnct_write,
                (obj_prop, ), **args)

    def get(self, cursor, obj, ids, name, user=None, offset=0, context=None,
            values=None):
        return self._fnct_read(obj, cursor, user, ids, name, self._arg,
                context=context)

    def set(self, cursor, obj, obj_id, name, value, user=None, context=None):
        self._fnct_write(obj, cursor, user, obj_id, name, value,
                    self._fnct_inv_arg, context=context)

property = Property
