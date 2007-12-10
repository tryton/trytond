"Attachment"
from trytond.osv import fields, OSV

class Attachment(OSV):
    "Attachment"
    _name = 'ir.attachment'
    _description = __doc__
    _columns = {
        'name': fields.char('Attachment Name',size=64, required=True),
        'datas': fields.binary('Data'),
        'datas_fname': fields.char('Data Filename',size=64),
        'description': fields.text('Description'),
        # Not required due to the document module !
        'res_model': fields.char('Resource Model',size=64, readonly=True),
        'res_id': fields.integer('Resource ID', readonly=True),
        'link': fields.char('Link', size=256)
    }

Attachment()
