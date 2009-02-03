#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Many2One(Field):
    _type = 'many2one'

    def __init__(self, model_name, string='', left=None, right=None,
            ondelete='SET NULL', **args):
        super(Many2One, self).__init__(string=string, **args)
        self.model_name = model_name
        self.left = left
        self.right = right
        self.ondelete = ondelete

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name]
        for i in ids:
            res.setdefault(i, '')
        try:
            model = model.pool.get(self.model_name)
        except KeyError:
            return res
        record_names = {}
        for record_id, name in model.name_get(cursor, user,
                [isinstance(x, (list, tuple)) and x[0] or x
                    for x in res.values() if x],
                context=context):
            record_names[record_id] = name

        for i in res.keys():
            if res[i] and res[i] in record_names:
                res[i] = (res[i], record_names[res[i]])
            else:
                res[i] = False
        return res
