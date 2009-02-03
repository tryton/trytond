#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.function import Function


class Property(Function):

    def __init__(self, **args):
        super(Property, self).__init__('', **args)
        self.readonly = False

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        property_obj = model.pool.get('ir.property')
        res = property_obj.get(cursor, user, name, model._name, ids,
                context=context)

        if self.model_name:
            model = model.pool.get(self.model_name)
            record_names = {}
            for record_id, record_name in model.name_get(cursor, user,
                    [x for x in res.values() if x], context=context):
                record_names[record_id] = record_name
            for i in ids:
                if res.get(i) and res[i] in record_names:
                    res[i] = (res[i], record_names[res[i]])
                else:
                    res[i] = False
        return res


    def set(self, cursor, user, record_id, model, name, value, context=None):
        property_obj = model.pool.get('ir.property')
        return property_obj.set(cursor, user, name, model._name, record_id,
                (value and (self.model_name or '')  + ',' + str(value)) or False,
                context=context)
