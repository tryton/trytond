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

    def get(self, cursor, user, name, model, res_id=False, context=None):
        cursor.execute('SELECT id FROM ir_model_fields ' \
                'WHERE name = %s AND model = %s', (name, model))
        res = cursor.fetchone()
        if res:
            nid = self.search(cursor, user, [
                ('fields_id', '=', res[0]),
                ('res_id', '=', res_id),
                ])
            if nid:
                val = self.browse(cursor, user, nid[0], context).value
                return (val and int(val.split(',')[1])) or False
        return False

Property()
