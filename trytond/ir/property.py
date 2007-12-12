"Properties"
from trytond.osv import OSV, fields


class Property(OSV):
    "Property"
    _name = 'ir.property'
    _description = __doc__

    def _models_get2(self, cursor, user, context=None):
        model_fields_obj = self.pool.get('ir.model.fields')
        ids = model_fields_obj.search(cursor, user, [('view_load', '=', 1)])
        res = []
        done = {}
        for model_field in model_fields_obj.browse(cursor, user, ids,
                context=context):
            if model_field.relation not in done:
                res.append([model_field.relation, model_field.relation])
                done[model_field.relation] = True
        return res

    def _models_get(self, cursor, user, context=None):
        model_fields_obj = self.pool.get('ir.model.fields')
        ids = model_fields_obj.search(cursor, user, [('view_load', '=', 1)])
        res = []
        done = {}
        for model_field in model_fields_obj.browse(cursor, user, ids,
                context=context):
            if model_field.model_id.id not in done:
                res.append([model_field.model_id.model,
                    model_field.model_id.name])
                done[model_field.model_id.id] = True
        return res

    _columns = {
        'name': fields.char('Name', size=128),
        'value': fields.reference('Value', selection=_models_get2, size=128),
        'res_id': fields.reference('Resource', selection=_models_get, size=128),
        #'company_id': fields.many2one('res.company', 'Company'),
        'fields_id': fields.many2one('ir.model.fields', 'Fields',
            ondelete='cascade', required=True)
    }

    def unlink(self, cursor, user, ids, context=None):
        if ids:
            cursor.execute('DELETE FROM ir_model_fields ' \
                    'WHERE id IN (' \
                        'SELECT fields_id FROM ir_property ' \
                        'WHERE (fields_id IS NOT NULL) ' \
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
        model_fields_obj = self.pool.get('ir.model.fields')
        res = {}

        fields_id = model_fields_obj.search(cursor, user, [
            ('name', '=', name),
            ('model', '=', model),
            ], limit=1, context=context)[0]

        default_id = self.search(cursor, user, [
            ('fields_id', '=', fields_id),
            ('res_id', '=', False),
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
            ('fields_id', '=', fields_id),
            ('res_id', 'in', [name + ',' + str(obj_id) \
                    for obj_id in  res_ids]),
            ])
        for prop in self.browse(cursor, user, property_ids):
            res[int(prop.res_id.split(',')[1])] = (prop.value and \
                    int(prop.value.split(',')[1])) or False

        return res

    def set(self, cursor, user, name, model, res_id, val, context=None):
        """
        Set property value for res_id
        """
        model_fields_obj = self.pool.get('ir.model.fields')
        fields_id = model_fields_obj.search(cursor, user, [
            ('name', '=', name),
            ('model', '=', model),
            ], limit=1, context=context)[0]

        property_ids = self.search(cursor, user, [
            ('fields_id', '=', fields_id),
            ('res_id', '=', name + ',' + str(res_id)),
            ], context=context)
        self.unlink(cursor, property_ids, context=context)

        default_id = self.search(cursor, user, [
            ('fields_id', '=', fields_id),
            ('res_id', '=', False),
            ], limit=1, context=context)
        default_id = False
        if default_id:
            default_val = self.browse(cursor, user, default_id[0],
                    context=context).value

#        company_id = obj.pool.get('res.users').company_get(cursor, user, user)
        res = False
        if (val != default_val):
            res = self.create(cursor, user, {
                'name': name,
                'value': val,
                'res_id': model + ',' + str(res_id),
#                'company_id': company_id,
                'fields_id': fields_id,
            }, context=context)
        return res

Property()
