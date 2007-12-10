"Exports"
from trytond.osv import fields, OSV


class Exports(OSV):
    "Exports"
    _name = "ir.exports"
    _description = __doc__
    _columns = {
            'name': fields.char('Export name', size=128),
            'resource': fields.char('Resource', size=128),
            'export_fields': fields.one2many('ir.exports.line', 'export_id',
                                             'Export Id'),
    }

Exports()


class ExportsLine(OSV):
    "Exports line"
    _name = 'ir.exports.line'
    _description = __doc__
    _columns = {
            'name': fields.char('Field name', size=64),
            'export_id': fields.many2one('ir.exports', 'Exportation',
                select=True),
            }

ExportsLine()
