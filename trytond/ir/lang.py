"Lang"
from trytond.osv import fields, OSV


class Lang(OSV):
    "Language"
    _name = "ir.lang"
    _log_access = False
    _description = __doc__
    _columns = {
        'name': fields.Char('Name', size=64, required=True),
        'code': fields.Char('Code', size=5, required=True),
        'translatable': fields.Boolean('Translatable'),
        'active': fields.Boolean('Active'),
        'direction': fields.Selection([
            ('ltr', 'Left-to-right'),
            ('rtl', 'Right-to-left'),
            ], 'Direction',required=True),
    }
    _defaults = {
        'active': lambda *a: 1,
        'translatable': lambda *a: 0,
        'direction': lambda *a: 'ltr',
    }

Lang()
