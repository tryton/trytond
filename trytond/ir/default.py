"Default"
from trytond.osv import fields, OSV
from decimal import Decimal


class Default(OSV):
    "Default"
    _name = 'ir.default'
    _description = __doc__
    _rec_name = 'value'
    model = fields.Many2One('ir.model', 'Model', required=True,
       ondelete='cascade')
    field = fields.Many2One('ir.model.field', 'Field', required=True,
       ondelete='cascade')
    value = fields.Text('Value')
    clause = fields.Text('Clause')
    user = fields.Many2One('res.user', 'User', ondelete='cascade')

    def __init__(self):
        super(Default, self).__init__()
        self._rpc_allowed += ['get_default', 'set_default']

    def get_default(self, cursor, user, model, clause, context=None):
        res = {}
        test_user = user
        test_clause = clause
        default_ids = []
        while True:
            default_ids += self.search(cursor, user, [
                ('model.model', '=', model),
                ('clause', '=', test_clause),
                ('user', '=', test_user),
                ], context=context)
            if test_user:
                test_user = False
                continue
            if test_clause:
                test_clause = False
                continue
            break
        ctx = {}
        ctx['Decimal'] = Decimal
        for default in self.browse(cursor, user, default_ids, context=context):
            if default.field.name not in res:
                res[default.field.name] = eval(default.value)
        return res

    def set_default(self, cursor, user, model, field, clause, value,
            user_default, context=None):
        model_obj = self.pool.get('ir.model')
        field_obj = self.pool.get('ir.model.field')
        model_id = model_obj.search(cursor, user, [
            ('model', '=', model),
            ], context=context)[0]
        field_id = field_obj.search(cursor, user, [
            ('name', '=', field),
            ], context=context)[0]
        default_ids = self.search(cursor, user, [
            ('model', '=', model_id),
            ('field', '=', field_id),
            ('clause', '=', clause),
            ('user', '=', user_default),
            ], context=context)
        if default_ids:
            self.unlink(cursor, user, default_ids, context=context)
        self.create(cursor, user, {
            'model': model_id,
            'field': field_id,
            'value': str(value),
            'clause': clause,
            'user': user_default,
            }, context=context)

Default()
