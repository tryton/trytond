#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

class BrowseRecordList(list):
    '''
    A list of BrowseRecord
    '''
    #TODO: execute an object method on BrowseRecordList

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
                    [x[0] for x in ffields], context=self._context)

            # create browse records for 'remote' objects
            for data in datas:
                for i, j in ffields:
                    if not j._obj in self._table.pool.object_name_list():
                        continue
                    obj = self._table.pool.get(j._obj)
                    if j._type in ('many2one',):
                        if data[i]:
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
                            self._user,
                            isinstance(x, (list, tuple)) and x[0] or x, obj,
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
