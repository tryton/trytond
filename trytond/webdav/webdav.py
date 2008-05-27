"WebDAV"
import os
import base64
import time
from trytond.osv import fields, OSV
from trytond.version import PACKAGE, VERSION, WEBSITE


class Directory(OSV):
    "Directory"
    _name = "webdav.directory"
    _description = __doc__
    name = fields.Char('Name', size=128, required=True, select=1)
    parent = fields.Many2One('webdav.directory', 'Parent',
       ondelete='restrict')
    childs = fields.One2Many('webdav.directory', 'parent', 'Childs')
    model = fields.Many2One('ir.model', 'Model')
    domain = fields.Char('Domain', size=250)
    _parent_name = 'parent'

    def __init__(self):
        super(Directory, self).__init__()
        self._sql_constraints += [
            ('name_parent_uniq', 'UNIQUE (name, parent)',
                'The directory name must be unique inside a directory!'),
        ]
        self._constraints += [
            ('check_recursion',
                'Error! You can not create recursive directories.', ['parent']),
            ('check_attachment',
                'Error! You can not create a directory \n' \
                        'with the same name of an existing file \n' \
                        'inside the same directory.', ['name']),
        ]
        self.ext2mime = {
            '.png': 'image/png',
        }

    def default_domain(self, cursor, user, context=None):
        return '[]'

    def check_attachment(self, cursor, user, ids):
        attachment_obj = self.pool.get('ir.attachment')
        for directory in self.browse(cursor, user, ids):
            if directory.parent:
                attachment_ids = attachment_obj.search(cursor, user, [
                    ('res_model', '=', self._name),
                    ('res_id', '=', directory.parent.id),
                    ])
                for attachment in attachment_obj.browse(cursor, user,
                        attachment_ids):
                    if attachment.name == directory.name:
                        return False
        return True

    def _uri2object(self, cursor, user, uri, object_name=_name, object_id=False,
            context=None):
        attachment_obj = self.pool.get('ir.attachment')
        if not uri:
            return self._name, False
        name, uri = (uri.split('/', 1) + [None])[0:2]
        if object_name == self._name:
            directory_ids = self.search(cursor, user, [
                ('name', '=', name),
                ('parent', '=', object_id),
                ], limit=1, context=context)
            if directory_ids:
                object_id = directory_ids[0]
                directory = self.browse(cursor, user, object_id,
                        context=context)
                if directory.model and uri:
                    object_name = directory.model.model
            else:
                if uri:
                    return None, 0
                attachment_ids = attachment_obj.search(cursor, user, [
                    ('res_model', '=', object_name),
                    ('res_id', '=', object_id),
                    ('name', '=', name),
                    ], limit=1, context=context)
                if attachment_ids:
                    object_name = 'ir.attachment'
                    object_id = attachment_ids[0]
                else:
                    object_name = None
                    object_id = False
        else:
            object_id = int(name.rsplit('-', 1)[1].strip())
            if uri:
                if '/' in uri:
                    return None, 0
                #TODO add report
                name = uri
                attachment_ids = attachment_obj.search(cursor, user, [
                    ('res_model', '=', object_name),
                    ('res_id', '=', object_id),
                    ('name', '=', name),
                    ], limit=1, context=context)
                if attachment_ids:
                    object_name = 'ir.attachment'
                    object_id = attachment_ids[0]
                else:
                    object_name = None
                    object_id = False
                return object_name, object_id
        if uri:
            return self._uri2object(cursor, user, uri, object_name,
                    object_id, context)
        return object_name, object_id

    def get_childs(self, cursor, user, uri, context=None):
        res = []
        if not uri:
            directory_ids = self.search(cursor, user, [
                ('parent', '=', False),
                ], context=context)
            for directory in self.browse(cursor, user, directory_ids,
                    context=context):
                if '/' in directory.name:
                    continue
                res.append(directory.name)
            return res
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name == self._name and object_id:
            directory = self.browse(cursor, user, object_id, context=context)
            if directory.model:
                model_obj = self.pool.get(directory.model.model)
                if not model_obj:
                    return res
                model_ids = model_obj.search(cursor, user,
                        eval(directory.domain or "[]"), context=context)
                for child_id, child_name in model_obj.name_get(cursor, user,
                        model_ids, context=context):
                    if '/' in child_name:
                        continue
                    res.append(child_name + '-' + str(child_id))
                return res
            else:
                for child in directory.childs:
                    if '/' in child.name:
                        continue
                    res.append(child.name)
        if object_name not in ('ir.attachment', 'ir.action.report'):
            attachment_obj = self.pool.get('ir.attachment')
            attachment_ids = attachment_obj.search(cursor, user, [
                ('res_model', '=', object_name),
                ('res_id', '=', object_id),
                ], context=context)
            for attachment in attachment_obj.browse(cursor, user, attachment_ids,
                    context=context):
                if attachment.name and not attachment.link:
                    if '/' in attachment.name:
                        continue
                    res.append(attachment.name)
        return res

    def get_resourcetype(self, cursor, user, uri, context=None):
        from DAV.constants import COLLECTION, OBJECT
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name in ('ir.attachment', 'ir.action.report'):
            return OBJECT
        return COLLECTION

    def get_contentlength(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name == 'ir.attachment':
            attachment_obj = self.pool.get('ir.attachment')
            attachment = attachment_obj.browse(cursor, user, object_id,
                    context=context)
            if attachment.datas_size:
                return str(attachment.datas_size)
        return '0'

    def get_contenttype(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name == 'ir.attachment':
            ext = os.path.splitext(uri)[1]
            if not ext:
                return "application/octet-stream"
            return self.ext2mime.get(ext, 'application/octet-stream')
        return "application/octet-stream"

    def get_creationdate(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        model_obj = self.pool.get(object_name)
        if model_obj._log_access:
            cursor.execute('SELECT EXTRACT(epoch FROM create_date) ' \
                    'FROM "' + model_obj._table +'" ' \
                    'WHERE id = %s', (object_id,))
            return cursor.fetchone()[0]
        return time.time()

    def get_lastmodified(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        model_obj = self.pool.get(object_name)
        if model_obj._log_access and object_id:
            cursor.execute('SELECT EXTRACT(epoch FROM write_date) ' \
                    'FROM "' + model_obj._table +'" ' \
                    'WHERE id = %s', (object_id,))
            return cursor.fetchone()[0]
        return time.time()

    def get_data(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_NotFound
        if uri:
            object_name, object_id = self._uri2object(cursor, user, uri,
                    context=context)
            if object_name == 'ir.attachment' and object_id:
                attachment_obj = self.pool.get('ir.attachment')
                attachment = attachment_obj.browse(cursor, user, object_id,
                        context=context)
                if attachment.datas:
                    return base64.decodestring(attachment.datas)
        raise DAV_NotFound

    def put(self, cursor, user, uri, data, content_type, context=None):
        from DAV.errors import DAV_Forbidden
        from DAV.utils import get_uriparentpath, get_urifilename
        object_name, object_id = self._uri2object(cursor, user,
                get_uriparentpath(uri), context=context)
        if not object_name \
                or object_name in ('ir.attachment') \
                or not object_id:
            raise DAV_Forbidden
        attachment_obj = self.pool.get('ir.attachment')
        object_name2, object_id2 = self._uri2object(cursor, user, uri,
                context=context)
        if not object_id2:
            name = get_urifilename(uri)
            try:
                attachment_obj.create(cursor, user, {
                    'name': name,
                    'datas': base64.encodestring(data),
                    'name': name,
                    'res_model': object_name,
                    'res_id': object_id,
                    }, context=context)
            except:
                raise DAV_Forbidden
        else:
            try:
                attachment_obj.write(cursor, user, object_id2, {
                    'datas': base64.encodestring(data),
                    }, context=context)
            except:
                raise DAV_Forbidden
        return 201

    def mkcol(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_Forbidden
        from DAV.utils import get_uriparentpath, get_urifilename
        if uri[-1:] == '/':
            uri = uri[:-1]
        object_name, object_id = self._uri2object(cursor, user,
                get_uriparentpath(uri), context=context)
        if object_name != 'webdav.directory':
            raise DAV_Forbidden
        name = get_urifilename(uri)
        try:
            self.create(cursor, user, {
                'name': name,
                'parent': object_id,
                }, context=context)
        except:
            raise DAV_Forbidden
        return 201

    def rmcol(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_Forbidden
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name != 'webdav.directory' \
                or not object_id:
            raise DAV_Forbidden
        try:
            self.unlink(cursor, user, object_id, context=context)
        except:
            raise DAV_Forbidden
        return 200

    def rm(self, cursor, user, uri, context=None):
        from DAV.errors import DAV_Forbidden
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name != 'ir.attachment' \
                or not object_id:
            raise DAV_Forbidden
        model_obj = self.pool.get(object_name)
        try:
            model_obj.unlink(cursor, user, object_id, context=context)
        except:
            raise DAV_Forbidden
        return 200

    def exists(self, cursor, user, uri, context=None):
        object_name, object_id = self._uri2object(cursor, user, uri,
                context=context)
        if object_name and object_id:
            return 1
        return None

Directory()


class Attachment(OSV):
    _name = 'ir.attachment'

    def __init__(self):
        super(Attachment, self).__init__()
        self._constraints += [
            ('check_directory',
                'Error! You can not create a attachment \n' \
                        'on a directory that have the same name \n' \
                        'than a child directory.', ['name']),
        ]

    def check_directory(self, cursor, user, ids):
        directory_obj = self.pool.get('webdav.directory')
        for attachment in self.browse(cursor, user, ids):
            if attachment.res_model == 'webdav.directory':
                directory = directory_obj.browse(cursor, user,
                        attachment.res_id)
                for child in directory.childs:
                    if child.name == attachment.name:
                        return False
        return True

Attachment()
