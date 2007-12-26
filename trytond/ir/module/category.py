"Category"
from trytond.osv import fields, OSV


class Category(OSV):
    "Module Category"
    _name = "ir.module.category"
    _description = __doc__
    _columns = {
        'name': fields.Char("Name", size=128, required=True),
        'parent_id': fields.Many2One('ir.module.category',
            'Parent Category', select=1),
        'child_ids': fields.One2Many('ir.module.category',
            'parent_id', 'Parent Category'),
    }
    _order = 'name'

Category()
