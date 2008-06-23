#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Exports"
from trytond.osv import fields, OSV


class Export(OSV):
    "Export"
    _name = "ir.export"
    _description = __doc__
    name = fields.char('Export name', size=128)
    resource = fields.char('Resource', size=128)
    export_fields = fields.one2many('ir.export.line', 'export',
       'Export Id')

Export()


class ExportLine(OSV):
    "Export line"
    _name = 'ir.export.line'
    _description = __doc__
    name = fields.char('Field name', size=64)
    export = fields.many2one('ir.export', 'Exportation',
       select=True)

ExportLine()
