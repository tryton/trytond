#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.function import Function
from trytond.model.fields.field import Field


class Property(Function):
    '''
    Define property field that is stored in ir.property (any)
    '''

    def __init__(self, type='float', fnct_search='', model_name=None,
            selection=None, digits=None, relation=None, add_remove=None,
            string='', help='', required=False, readonly=False, domain=None,
            states=None, priority=0, change_default=False, translate=False,
            select=0, on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None):
        '''
        :param type: The type of field.
        :param fnct_search: The name of the function to search.
        :param model_name: See Many2One.
        :param selection: See Selection.
        :param digits: See Float.
        :param relation: Like model_name.
        :param add_remove: See Many2One.
        '''
        super(Property, self).__init__('', type=type, fnct_search=fnct_search,
                model_name=model_name, selection=selection, digits=digits,
                relation=relation, add_remove=add_remove, string=string,
                help=help, required=required, readonly=readonly, domain=domain,
                states=states, priority=priority, change_default=change_default,
                translate=translate, select=select, on_change=on_change,
                on_change_with=on_change_with, depends=depends,
                order_field=order_field, context=context)
        self.readonly = False
    __init__.__doc__ += Field.__init__.__doc__

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        '''
        Retreive the property.

        :param cursor: The database cursor.
        :param user: The user id.
        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field or a list of name field.
        :param values:
        :param context: The contest.
        :return: a dictionary with ids as key and values as value
        '''
        property_obj = model.pool.get('ir.property')
        res = property_obj.get(cursor, user, name, model._name, ids,
                context=context)
        return res


    def set(self, cursor, user, record_id, model, name, value, context=None):
        '''
        Set the property.

        :param cursor: The database cursor.
        :param user: The user id.
        :param record_id: The record id.
        :param model: The model.
        :param name: The name of the field.
        :param value: The value to set.
        :param context: The context.
        '''
        property_obj = model.pool.get('ir.property')
        return property_obj.set(cursor, user, name, model._name, record_id,
                (value and (self.model_name or '')  + ',' + str(value)) or False,
                context=context)
