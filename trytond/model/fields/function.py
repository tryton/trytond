#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field
from trytond.model.fields.float import digits_validate
from trytond.model.fields.one2many import add_remove_validate
from trytond.pyson import PYSON
import inspect


class Function(Field):
    '''
    Define function field (any).
    '''
    _type = 'float'

    def __init__(self, fnct, arg=None, fnct_inv='', fnct_inv_arg=None,
            type='float', fnct_search='', model_name=None, selection=None,
            digits=None, relation=None, add_remove=None, datetime_field=None,
            string='', help='', required=False, readonly=False, domain=None,
            states=None, priority=0, change_default=False, translate=False,
            select=0, on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None):
        '''
        :param fnct: The name of the function.
        :param arg: Argument for the function.
        :param fnct_inv: The name of the function to write.
        :param fnct_inv_arg: Argument for the function to write.
        :param type: The type of field.
        :param fnct_search: The name of the function to search.
        :param model_name: See Many2One.
        :param selection: See Selection.
        :param digits: See Float.
        :param relation: Like model_name.
        :param add_remove: See Many2One.
        :param datetime_field: The name of the field that contains the datetime
            value to read the target records.
        '''
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(Function, self).__init__(string=string, help=help,
                required=required, readonly=readonly, domain=domain,
                states=states, priority=priority, change_default=change_default,
                translate=translate, select=select, on_change=on_change,
                on_change_with=on_change_with, depends=depends,
                order_field=order_field, context=context)
        self.model_name = model_name
        self.fnct = fnct
        self.arg = arg
        self.fnct_inv = fnct_inv
        self.fnct_inv_arg = fnct_inv_arg
        if not self.fnct_inv:
            self.readonly = True
        self._type = type
        self.fnct_search = fnct_search
        self.selection = selection
        self.__digits = None
        self.digits = digits
        if relation:
            self.model_name = relation
        self.__add_remove = None
        self.add_remove = add_remove
        self.datetime_field = datetime_field

    __init__.__doc__ += Field.__init__.__doc__

    def _get_digits(self):
        return self.__digits

    def _set_digits(self, value):
        digits_validate(value)
        self.__digits = value

    digits = property(_get_digits, _set_digits)

    def _get_add_remove(self):
        return self.__add_remove

    def _set_add_remove(self, value):
        add_remove_validate(value)
        self.__add_remove = value

    add_remove = property(_get_add_remove, _set_add_remove)

    def search(self, cursor, user, model, name, args, context=None):
        '''
        Call the fnct_search.

        :param cursor: The database cursor.
        :param user: The user id.
        :param model: The model.
        :param name: The name of the field.
        :param args: The search domain. See ModelStorage.search
        :param context: The context.
        :return: New list of domain.
        '''
        if not self.fnct_search:
            model.raise_user_error(cursor, 'search_function_missing',
                    name, context=context)
        return getattr(model, self.fnct_search)(cursor, user, name, args,
                context=context)

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        '''
        Call the fnct.
        If the function has ``names`` in the function definition then
        it will call it with a list of name.

        :param cursor: The database cursor.
        :param user: The user id.
        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field or a list of name field.
        :param values:
        :param context: The contest.
        :return: a dictionary with ids as key and values as value or
            a dictionary with name as key and a dictionary as value if
            name is a list of field name.
        '''
        if isinstance(name, list):
            names = name
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(getattr(model, self.fnct))[0]:
                return getattr(model, self.fnct)(cursor, user, ids, names,
                        self.arg, context=context)
            res = {}
            for name in names:
                res[name] = getattr(model, self.fnct)(cursor, user, ids, name,
                        self.arg, context=context)
            return res
        else:
            # Test is the function works with a list of names
            if 'names' in inspect.getargspec(getattr(model, self.fnct))[0]:
                name = [name]
            return getattr(model, self.fnct)(cursor, user, ids, name, self.arg,
                    context=context)


    def set(self, cursor, user, record_id, model, name, value, context=None):
        '''
        Call the fnct_inv.

        :param cursor: The database cursor.
        :param user: The user id.
        :param record_id: The record id.
        :param model: The model.
        :param name: The name of the field.
        :param value: The value to set.
        :param context: The context.
        '''
        if self.fnct_inv:
            getattr(model, self.fnct_inv)(cursor, user, record_id, name, value,
                    self.fnct_inv_arg, context=context)
