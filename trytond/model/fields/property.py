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
        return res


    def set(self, cursor, user, record_id, model, name, value, context=None):
        property_obj = model.pool.get('ir.property')
        return property_obj.set(cursor, user, name, model._name, record_id,
                (value and (self.model_name or '')  + ',' + str(value)) or False,
                context=context)
