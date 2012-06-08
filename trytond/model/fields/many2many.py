#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import chain
from trytond.model.fields.field import Field
from trytond.transaction import Transaction
from trytond.pool import Pool


class Many2Many(Field):
    '''
    Define many2many field (``list``).
    '''
    _type = 'many2many'

    def __init__(self, relation_name, origin, target, string='', order=None,
            datetime_field=None, help='', required=False, readonly=False,
            domain=None, states=None, on_change=None, on_change_with=None,
            depends=None, order_field=None, context=None, loading='lazy'):
        '''
        :param relation_name: The name of the relation model
            or the name of the target model for ModelView only.
        :param origin: The name of the field to store origin ids.
        :param target: The name of the field to store target ids.
        :param order:  a list of tuples that are constructed like this:
            ``('field name', 'DESC|ASC')``
            allowing to specify the order of result
        :param datetime_field: The name of the field that contains the datetime
            value to read the target records.
        '''
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(Many2Many, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, order_field=order_field, context=context,
            loading=loading)
        self.relation_name = relation_name
        self.origin = origin
        self.target = target
        self.order = order
        self.datetime_field = datetime_field
    __init__.__doc__ += Field.__init__.__doc__

    def get(self, ids, model, name, values=None):
        '''
        Return target records ordered.

        :param ids: a list of ids
        :param model: a string with the name of the model
        :param name: a string with the name of the field
        :param values: a dictionary with the read values
        :return: a dictionary with ids as key and values as value
        '''
        if values is None:
            values = {}
        res = {}
        if not ids:
            return res
        for i in ids:
            res[i] = []

        if self.order is None:
            order = [(self.target, 'ASC')]
        else:
            order = self.order

        relation_obj = Pool().get(self.relation_name)
        if self.origin in relation_obj._columns:
            origin_field = relation_obj._columns[self.origin]
        else:
            origin_field = relation_obj._inherit_fields[self.origin][2]

        relation_ids = []
        for i in range(0, len(ids), Transaction().cursor.IN_MAX):
            sub_ids = ids[i:i + Transaction().cursor.IN_MAX]
            if origin_field._type == 'reference':
                references = ['%s,%s' % (model._name, x) for x in sub_ids]
                clause = [(self.origin, 'in', references)]
            else:
                clause = [(self.origin, 'in', sub_ids)]
            clause += [(self.target + '.id', '!=', None)]
            relation_ids.append(relation_obj.search(clause, order=order))
        relation_ids = list(chain(*relation_ids))

        for relation in relation_obj.browse(relation_ids):
            if origin_field._type == 'reference':
                _, origin_id = relation[self.origin].split(',')
                origin_id = int(origin_id)
            else:
                origin_id = relation[self.origin].id
            res[origin_id].append(relation[self.target].id)
        return res

    def set(self, ids, model, name, values):
        '''
        Set the values.

        :param ids: A list of ids
        :param model: A string with the name of the model
        :param name: A string with the name of the field
        :param values: A list of tuples:
            (``create``, ``{<field name>: value}``),
            (``write``, ``<ids>``, ``{<field name>: value}``),
            (``delete``, ``<ids>``),
            (``delete_all``),
            (``unlink``, ``<ids>``),
            (``add``, ``<ids>``),
            (``unlink_all``),
            (``set``, ``<ids>``)
        '''
        pool = Pool()
        if not values:
            return
        relation_obj = pool.get(self.relation_name)
        target_obj = self.get_target()

        if self.origin in relation_obj._columns:
            origin_field = relation_obj._columns[self.origin]
        else:
            origin_field = relation_obj._inherit_fields[self.origin][2]

        def search_clause(ids):
            if origin_field._type == 'reference':
                references = ['%s,%s' % (model._name, x) for x in ids]
                return (self.origin, 'in', references)
            else:
                return (self.origin, 'in', ids)

        def field_value(record_id):
            if origin_field._type == 'reference':
                return '%s,%s' % (model._name, record_id)
            else:
                return record_id

        for act in values:
            if act[0] == 'create':
                for record_id in ids:
                    relation_obj.create({
                            self.origin: field_value(record_id),
                            self.target: target_obj.create(act[1]),
                            })
            elif act[0] == 'write':
                target_obj.write(act[1], act[2])
            elif act[0] == 'delete':
                target_obj.delete(act[1])
            elif act[0] == 'delete_all':
                relations = relation_obj.browse(relation_obj.search([
                            search_clause(ids),
                            ]))
                target_obj.delete([r[self.target].id for r in relations
                        if r[self.target].id])
            elif act[0] == 'unlink':
                if isinstance(act[1], (int, long)):
                    target_ids = [act[1]]
                else:
                    target_ids = list(act[1])
                if not target_ids:
                    continue
                relation_ids = []
                for i in range(0, len(target_ids),
                        Transaction().cursor.IN_MAX):
                    sub_ids = target_ids[i:i + Transaction().cursor.IN_MAX]
                    relation_ids += relation_obj.search([
                            search_clause(ids),
                            (self.target, 'in', sub_ids),
                            ])
                relation_obj.delete(relation_ids)
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    target_ids = [act[1]]
                else:
                    target_ids = list(act[1])
                if not target_ids:
                    continue
                existing_ids = []
                for i in range(0, len(target_ids),
                        Transaction().cursor.IN_MAX):
                    sub_ids = target_ids[i:i + Transaction().cursor.IN_MAX]
                    relation_ids = relation_obj.search([
                            search_clause(ids),
                            (self.target, 'in', sub_ids),
                            ])
                    for relation in relation_obj.browse(relation_ids):
                        existing_ids.append(relation[self.target].id)
                for new_id in (x for x in target_ids if x not in existing_ids):
                    for record_id in ids:
                        relation_obj.create({
                                self.origin: field_value(record_id),
                                self.target: new_id,
                                })
            elif act[0] == 'unlink_all':
                target_ids = relation_obj.search([
                        search_clause(ids),
                        (self.target + '.id', '!=', None),
                        ])
                relation_obj.delete(target_ids)
            elif act[0] == 'set':
                if not act[1]:
                    target_ids = []
                else:
                    target_ids = list(act[1])
                target_ids2 = relation_obj.search([
                        search_clause(ids),
                        (self.target + '.id', '!=', None),
                        ])
                relation_obj.delete(target_ids2)

                for new_id in target_ids:
                    for record_id in ids:
                        relation_obj.create({
                                self.origin: field_value(record_id),
                                self.target: new_id,
                                })
            else:
                raise Exception('Bad arguments')

    def get_target(self):
        '''
        Return the target model.

        :return: A Model
        '''
        relation_obj = Pool().get(self.relation_name)
        if not self.target:
            return relation_obj
        if self.target in relation_obj._columns:
            target_obj = Pool().get(
                    relation_obj._columns[self.target].model_name)
        else:
            target_obj = Pool().get(
                    relation_obj._inherit_fields[self.target][2].model_name)
        return target_obj
