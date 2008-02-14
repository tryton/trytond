"Attachment"
import os
import md5
import base64
from trytond.osv import fields, OSV
from trytond.config import CONFIG

class Attachment(OSV):
    "Attachment"
    _name = 'ir.attachment'
    _description = __doc__

    #TODO directory structure is on 2 level, check if it is enough
    def _datas(self, cursor, user, ids, name, arg, context=None):
        res = {}
        db_name = cursor.dbname
        print "ids:", ids
        for attachment in self.browse(cursor, user, ids, context=context):
            value = False
            if attachment.digest:
                digest = attachment.digest
                filename = os.path.join(CONFIG['data_path'], db_name,
                        digest[0:2], digest[2:4], digest)
                file_p = file(filename, 'rb')
                value = base64.encodestring(file_p.read())
            res[attachment.id] = value
        return res

    def _datas_inv(self, cursor, user, obj_id, name, value, args, context=None):
        if not value:
            return
        db_name = cursor.dbname
        directory = os.path.join(CONFIG['data_path'], db_name)
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        data = base64.decodestring(value)
        digest = md5.new(data).hexdigest()
        directory = os.path.join(directory, digest[0:2], digest[2:4])
        if not os.path.isdir(directory):
            os.makedirs(directory, 0770)
        filename = os.path.join(directory, digest)
        file_p = file(filename, 'wb')
        file_p.write(data)
        cursor.execute('UPDATE ir_attachment ' \
                'SET digest = %s ' \
                'WHERE id = %d', (digest, obj_id))

    _columns = {
        'name': fields.Char('Attachment Name',size=64, required=True),
        'datas': fields.Function(_datas, fnct_inv=_datas_inv, method=True,
            type='binary', string='Datas'),
        'datas_fname': fields.Char('Data Filename',size=64),
        'description': fields.Text('Description'),
        'res_model': fields.Char('Resource Model',size=64, readonly=True),
        'res_id': fields.Integer('Resource ID', readonly=True),
        'link': fields.Char('Link', size=256),
        'digest': fields.Char('Digest', size=32),
    }

Attachment()
