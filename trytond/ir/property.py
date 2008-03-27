"Properties"
from trytond.osv import OSV, fields


class Property(OSV):
    "Property"
    _name = 'ir.property'
    _description = __doc__
    name = fields.Char('Name', size=128)
    value = fields.Reference('Value', selection='models_get2', size=128)
    res = fields.Reference('Resource', selection='models_get', size=128)
    field = fields.Many2One('ir.model.field', 'Field',
       ondelete='cascade', required=True)

    def models_get2(self, cursor, user, context=None):
        model_field_obj = self.pool.get('ir.model.field')
        #TODO add domain for only reference fields
        ids = model_field_obj.search(cursor, user, [])
        res = []
        done = {}
        for model_field in model_field_obj.browse(cursor, user, ids,
                context=context):
            if model_field.relation not in done:
                res.append([model_field.relation, model_field.relation])
                done[model_field.relation] = True
        return res

    def models_get(self, cursor, user, context=None):
        model_field_obj = self.pool.get('ir.model.field')
        #TODO add domain for only reference fields
        ids = model_field_obj.search(cursor, user, [])
        res = []
        done = {}
        for model_field in model_field_obj.browse(cursor, user, ids,
                context=context):
            if model_field.model.id not in done:
                res.append([model_field.model.model,
                    model_field.model.name])
                done[model_field.model.id] = True
        return res

    def unlink(self, cursor, user, ids, context=None):
        if ids:
            cursor.execute('DELETE FROM ir_model_field ' \
                    'WHERE id IN (' \
                        'SELECT field FROM ir_property ' \
                        'WHERE (field IS NOT NULL) ' \
                            'AND (id IN (' + ','.join([str(x) for x in ids]) + \
                            ')))')
        res = super(Property, self).unlink(cursor, user, ids, context)
        return res

    def get(self, cursor, user, name, model, res_ids=None, context=None):
        """
        Return property value for each res_ids
        name: property name
        model: object name
        """
        model_field_obj = self.pool.get('ir.model.field')
        res = {}

        field_id = model_field_obj.search(cursor, user, [
            ('name', '=', name),
            ('model.model', '=', model),
            ], limit=1, context=context)[0]

        default_id = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', '=', False),
            ], limit=1, context=context)
        default_val = False
        if default_id:
            value = self.browse(cursor, user, default_id[0],
                    context=context).value
            default_val = (value and int(value.split(',')[1])) or False

        if not res_ids:
            return default_val

        for obj_id in res_ids:
            res[obj_id] = default_val

        property_ids = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', 'in', [model + ',' + str(obj_id) \
                    for obj_id in  res_ids]),
            ])
        for prop in self.browse(cursor, user, property_ids):
            res[int(prop.res.split(',')[1])] = (prop.value and \
                    int(prop.value.split(',')[1])) or False

        return res

    def set(self, cursor, user, name, model, res_id, val, context=None):
        """
        Set property value for res_id
        """
        model_field_obj = self.pool.get('ir.model.field')
        field_id = model_field_obj.search(cursor, user, [
            ('name', '=', name),
            ('model.model', '=', model),
            ], limit=1, context=context)[0]

        property_ids = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', '=', name + ',' + str(res_id)),
            ], context=context)
        self.unlink(cursor, user, property_ids, context=context)

        default_id = self.search(cursor, user, [
            ('field', '=', field_id),
            ('res', '=', False),
            ], limit=1, context=context)
        default_val = False
        if default_id:
            default_val = self.browse(cursor, user, default_id[0],
                    context=context).value

        res = False
        if (val != default_val):
            res = self.create(cursor, user, {
                'name': name,
                'value': val,
                'res': model + ',' + str(res_id),
                'field': field_id,
            }, context=context)
        return res

Property()
