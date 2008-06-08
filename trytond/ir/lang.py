"Lang"
from trytond.osv import fields, OSV


class Lang(OSV):
    "Language"
    _name = "ir.lang"
    _log_access = False
    _description = __doc__
    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True,
            help="RFC 4646 tag: http://tools.ietf.org/html/rfc4646")
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
