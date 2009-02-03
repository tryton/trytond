#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field
import inspect


class Function(Field):
    _type = 'float'

    def __init__(self, fnct, arg=None, fnct_inv='', fnct_inv_arg=None,
            type='float', fnct_search='', model_name=None, selection=None,
            digits=None, relation=None, add_remove=None, **args):
        super(Function, self).__init__(**args)
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
        self.digits = digits
        if relation:
            self.model_name = relation
        self.add_remove = add_remove

    def search(self, cursor, user, model, name, args, context=None):
        if not self.fnct_search:
            return []
        return getattr(model, self.fnct_search)(cursor, user, name, args,
                context=context)

    def get(self, cursor, user, ids, model, name, values=None, context=None):
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


    def set(self, cursor, user, record_id, model, name, values, context=None):
        if self.fnct_inv:
            getattr(model, self.fnct_inv)(cursor, user, record_id, name, values,
                    self.fnct_inv_arg, context=context)
