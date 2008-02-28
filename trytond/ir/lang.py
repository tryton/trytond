"Lang"
from trytond.osv import fields, OSV


class Lang(OSV):
    "Language"
    _name = "ir.lang"
    _log_access = False
    _description = __doc__
    name = fields.Char('Name', size=64, required=True)
    code = fields.Char('Code', size=5, required=True)
    translatable = fields.Boolean('Translatable')
    active = fields.Boolean('Active')
    direction = fields.Selection([
       ('ltr', 'Left-to-right'),
       ('rtl', 'Right-to-left'),
       ], 'Direction',required=True)

    def default_active(self, cursor, user, context=None):
        return 1

    def default_translatable(self, cursor, user, context=None):
        return 0

    def default_direction(self, cursor, user, context=None):
        return 'ltr'

Lang()
