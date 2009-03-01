#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Many2Many(Field):
    '''
    Define many2many field (``list``)
    '''
    _type = 'many2many'

    def __init__(self, model_name, relation_name, origin, target, string='',
            order=None, ondelete_origin='CASCADE', ondelete_target='RESTRICT',
            help='', required=False, readonly=False, domain=None, states=None,
            priority=0, change_default=False, translate=False, select=0,
            on_change=None, on_change_with=None, depends=None, order_field=None,
            context=None):
        '''
        :param model_name: The name of the targeted model.
        :param relation_name: The name of the table that store the link.
        :param origin: The name of the field to store origin ids.
        :param target: The name of the field to store target ids.
        :param order:  a list of tuple that are constructed like this:
            ``('field name', 'DESC|ASC')``
            it allow to specify the order of result
        :param ondelete_origin: Define the behavior of the origin record when
            the target record is deleted. (``CASCADE``, ``NO ACTION``, ``RESTRICT``,
            ``SET DEFAULT``, ``SET NULL``)
        :param ondelete_target: Same as ondelete_origin but for the target.
        '''
        super(Many2Many, self).__init__(string=string, help=help,
                required=required, readonly=readonly, domain=domain,
                states=states, priority=priority, change_default=change_default,
                translate=translate, select=select, on_change=on_change,
                on_change_with=on_change_with, depends=depends,
                order_field=order_field, context=context)
        self.model_name = model_name
        self.relation_name = relation_name
        self.origin = origin
        self.target = target
        self.order = order
        self.ondelete_origin = ondelete_origin
        self.ondelete_target = ondelete_target
    __init__.__doc__ += Field.__init__.__doc__

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        '''
        Return target records ordered.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids
        :param model: a string with the name of the model
        :param name: a string with the name of the field
        :param values: a dictionary with the readed values
        :param context: the context
        :return: a dictionary with ids as key and values as value
        '''
        if values is None:
            values = {}
        res = {}
        if not ids:
            return res
        for i in ids:
            res[i] = []
        ids_s = ','.join([str(x) for x in ids])
        model = model.pool.get(self.model_name)

        domain1, domain2 = model.pool.get('ir.rule').domain_get(cursor,
                user, model._name, context=context)
        if domain1:
            domain1 = ' and ' + domain1

        #TODO fix order: can have many fields
        cursor.execute('SELECT ' + self.relation_name + '.' + self.target + ', ' + \
                    self.relation_name + '.' + self.origin + ' ' \
                'FROM "' + self.relation_name + '" , "' + model._table + '" ' \
                'WHERE ' + \
                    self.relation_name + '.' + self.origin + ' IN (' + ids_s + ') ' \
                    'AND ' + self.relation_name + '.' + self.target + ' = ' + \
                        model._table + '.id ' + domain1 + \
                ' ORDER BY ' + \
                ','.join([model._table + '.' + x[0] + ' ' + x[1] \
                for x in (self.order or model._order)]), domain2)
        for i in cursor.fetchall():
            res[i[1]].append(i[0])
        return res

    def set(self, cursor, user, record_id, model, name, values, context=None):
        '''
        Set the values.

        :param cursor: The database cursor
        :param user: The user id
        :param record_id: The record id
        :param model: A string with the name of the model
        :param name: A string with the name of the field
        :param values: A list of tuple:
            (``create``, ``{<field name>: value}``),
            (``write``, ``<ids>``, ``{<field name>: value}``),
            (``delete``, ``<ids>``),
            (``unlink``, ``<ids>``),
            (``add``, ``<ids>``),
            (``unlink_all``),
            (``set``, ``<ids>``)
        :param context: The context
        '''
        if not values:
            return
        model = model.pool.get(self.model_name)
        for act in values:
            if act[0] == 'create':
                idnew = model.create(cursor, user, act[1], context=context)
                cursor.execute('INSERT INTO "' + self.relation_name + '" ' \
                        '(' + self.origin + ', ' + self.target + ') ' \
                        'VALUES (%s, %s)', (record_id, idnew))
            elif act[0] == 'write':
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
                cursor.execute('DELETE FROM "' + self.relation_name + '" ' \
                        'WHERE "' + self.origin + '" = %s ' \
                            'AND "'+ self.target + '" IN (' \
                                + ','.join(['%s' for x in ids]) + ')',
                        [record_id] + ids)
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    ids = [act[1]]
                else:
                    ids = list(act[1])
                if not ids:
                    continue
                cursor.execute('SELECT "' + self.target + '" ' \
                        'FROM "' + self.relation_name + '" ' \
                        'WHERE "' + self.origin + '" = %s ' \
                            'AND "' + self.target + '" IN (' + \
                                ','.join(['%s' for x in ids]) + ')',
                        [record_id] + ids)
                existing_ids = []
                for row in cursor.fetchall():
                    existing_ids.append(row[0])
                new_ids = [x for x in ids if x not in existing_ids]
                for new_id in new_ids:
                    cursor.execute('INSERT INTO "' + self.relation_name + '" ' \
                            '("' + self.origin + '", "' + self.target + '") ' \
                            'VALUES (%s, %s)', (record_id, new_id))
            elif act[0] == 'unlink_all':
                cursor.execute('UPDATE "' + self.relation_name + '" ' \
                        'SET "' + self.target + '" = NULL ' \
                        'WHERE "' + self.target + '" = %s', (record_id,))
            elif act[0] == 'set':
                if not act[1]:
                    ids = []
                else:
                    ids = list(act[1])
                domain1, domain2 = model.pool.get('ir.rule').domain_get(cursor,
                        user, model._name, context=context)
                if domain1:
                    domain1 = ' AND ' + domain1
                cursor.execute('DELETE FROM "' + self.relation_name + '" ' \
                        'WHERE "' + self.origin + '" = %s ' \
                            'AND "' + self.target + '" IN (' \
                            'SELECT ' + self.relation_name + '.' + self.target + ' ' \
                            'FROM "' + self.relation_name + '", "' + model._table + '" ' \
                            'WHERE ' + self.relation_name + '.' + self.origin + ' = %s ' \
                                'AND ' + self.relation_name + '.' + self.target + ' = ' + \
                                model._table + '.id ' + domain1 + ')',
                                [record_id, record_id] + domain2)

                for new_id in ids:
                    cursor.execute('INSERT INTO "' + self.relation_name + '" ' \
                            '("' + self.origin + '", "' + self.target + '") ' \
                            'VALUES (%s, %s)', (record_id, new_id))
            else:
                raise Exception('Bad arguments')
