#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class One2Many(Field):
    _type = 'one2many'

    def __init__(self, model_name, field, string='', order_field=None,
            add_remove=None, **args):
        super(One2Many, self).__init__(string=string, **args)
        self.model_name = model_name
        self.field = field
        self.add_remove = add_remove

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        res = {}
        for i in ids:
            res[i] = []
        ids2 = []
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            ids2 += model.pool.get(self.model_name).search(cursor, user,
                    [(self.field, 'in', sub_ids)], context=context)
        for i in model.pool.get(self.model_name).read(cursor, user, ids2,
                [self.field], context=context):
            res[i[self.field]].append(i['id'])
        for val in res.values():
            val.sort(lambda x, y: cmp(ids2.index(x), ids2.index(y)))
        return res

    def set(self, cursor, user, record_id, model, name, values, context=None):
        if not values:
            return
        model = model.pool.get(self.model_name)
        for act in values:
            if act[0] == 'create':
                act[1][self.field] = record_id
                model.create(cursor, user, act[1], context=context)
            elif act[0] == 'write':
                act[2][self.field] = record_id
                model.write(cursor, user, act[1] , act[2], context=context)
            elif act[0] == 'delete':
                model.delete(cursor, user, act[1], context=context)
            elif act[0] == 'unlink':
                if isinstance(act[1], (int, long)):
                    ids = [act[1]]
                else:
                    ids = list(act[1])
                if not ids:
                    continue
                ids = model.search(cursor, user, [
                    (self.field, '=', record_id),
                    ('id', 'in', ids),
                    ], context=context)
                model.write(cursor, user, ids, {
                    self.field: False,
                    }, context=context)
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    ids = [act[1]]
                else:
                    ids = list(act[1])
                if not ids:
                    continue
                ids = model.write(cursor, user, ids, {
                    self.field: record_id,
                    }, context=context)
            elif act[0] == 'unlink_all':
                ids = model.search(cursor, user, [
                    (self.field, '=', record_id),
                    ], context=context)
                model.write(cursor, user, ids, {
                    self.field: False,
                    }, context=context)
            elif act[0] == 'set':
                if not act[1]:
                    ids = [0]
                else:
                    ids = list(act[1])
                ids2 = model.search(cursor, user, [
                    (self.field, '=', record_id),
                    ('id', 'not in', ids),
                    ], context=context)
                model.write(cursor, user, ids2, {
                    self.field: False,
                    }, context=context)
                if act[1]:
                    model.write(cursor, user, ids, {
                        self.field: record_id,
                        }, context=context)
            else:
                raise Exception('Bad arguments')
