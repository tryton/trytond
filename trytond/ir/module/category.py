"Category"
from trytond.osv import fields, OSV


class Category(OSV):
    "Module Category"
    _name = "ir.module.category"
    _description = __doc__
    name = fields.Char("Name", size=128, required=True)
    parent = fields.Many2One('ir.module.category',
       'Parent Category', select=1)
    childs = fields.One2Many('ir.module.category',
       'parent', 'Parent Category')

    def __init__(self):
        super(Category, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

Category()
