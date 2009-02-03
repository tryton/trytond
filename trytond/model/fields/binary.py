#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Binary(Field):
    _type = 'binary'

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        if values is None:
            values = {}
        res = {}
        for i in values:
            res[i['id']] = i[name] and str(i[name]) or None
        for i in ids:
            res.setdefault(i, None)
        return res
