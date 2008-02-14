import urlparse
import socket
import base64
import time
from DAV import AuthServer, WebDAVServer, iface
from DAV.errors import *
from DAV.constants import COLLECTION, OBJECT
from DAV.utils import get_uriparentpath, get_urifilename
from DAV.davcmd import copyone, copytree, moveone, movetree, delone, deltree
from netsvc import LocalService
import security
import pooler
from version import PACKAGE, VERSION, WEBSITE

# This work because there is only one thread
USER_ID = 0

# Fix for bad use of Document in DAV.utils make_xmlresponse
from DAV.utils import VERSION as DAV_VERSION
if DAV_VERSION == '0.6':
    from xml.dom.Document import Document
    Document.Document = Document

class TrytonDAVInterface(iface.dav_interface):

    def __init__(self, interface, port):
        self.baseuri = 'http://%s:%s/' % (interface or socket.gethostname(), port)

    def _get_dburi(self, uri):
        uri = urlparse.urlsplit(uri)[2]
        if uri[0] == '/':
            uri = uri[1:]
        dbname, uri = (uri.split('/', 1) + [None])[0:2]
        return dbname, uri

    def get_childs(self, uri):
        res = []
        dbname, dburi = self._get_dburi(uri)
        if not dbname:
            db = LocalService('db')
            for dbname in db.list():
                res.append(urlparse.urljoin(self.baseuri, dbname))
            return res
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        if uri[-1:] != '/':
            uri += '/'
        for child in directory_obj.get_childs(cursor, USER_ID, dburi):
            res.append(urlparse.urljoin(self.baseuri, uri + child))
        cursor.close()
        return res

    def get_data(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or self.is_collection(uri):
            res = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">'
            res += '<html>'
            res += '<head>'
            res += '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
            res += '<title>%s - WebDAV - %s</title>' \
                    % (PACKAGE, dbname or 'root')
            res += '</head>'
            res += '<body>'
            res += '<h2>Directory: %s</h2>' % (get_urifilename(uri) or '/')
            res += '<ul>'
            if dbname:
                res += '<li><a href="%s">..</a></li>' \
                        % (get_uriparentpath(uri) or '/')
            for child in self.get_childs(uri):
                res += '<li><a href="%s">%s</a></li>' \
                        % (child, get_urifilename(child))
            res += '</ul>'
            res += '<hr noshade>'
            res += '<em>Powered by <a href="%s">%s</a> version %s</em>' \
                    % (WEBSITE, PACKAGE, VERSION)
            res += '</body>'
            res += '</html>'
            return res
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        res = directory_obj.get_data(cursor, USER_ID, dburi)
        cursor.close()
        return res

    def put(self, uri, data, content_type=''):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        try:
            try:
                res = directory_obj.put(cursor, USER_ID, dburi, data,
                        content_type)
                cursor.commit()
            except:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def mkcol(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        try:
            try:
                res = directory_obj.mkcol(cursor, USER_ID, dburi)
                cursor.commit()
            except:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def _get_dav_resourcetype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return COLLECTION
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        res = directory_obj.get_resourcetype(cursor, USER_ID, dburi)
        cursor.close()
        return res

    def _get_dav_displayname(self, uri):
        raise DAV_Secret

    def _get_dav_getcontentlength(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return '0'
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        res = directory_obj.get_contentlength(cursor, USER_ID, dburi)
        cursor.close()
        return res

    def _get_dav_getcontenttype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or self.is_collection(uri):
            return "text/html"
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        res = directory_obj.get_contenttype(cursor, USER_ID, dburi)
        cursor.close()
        return res

    def get_creationdate(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return time.time()
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        res = directory_obj.get_creationdate(cursor, USER_ID, dburi)
        cursor.close()
        return res

    def get_lastmodified(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return time.time()
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        res = directory_obj.get_lastmodified(cursor, USER_ID, dburi)
        cursor.close()
        return res

    def rmcol(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        try:
            try:
                res = directory_obj.rmcol(cursor, USER_ID, dburi)
                cursor.commit()
            except:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def rm(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            raise DAV_Forbidden
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        try:
            try:
                res = directory_obj.rm(cursor, USER_ID, dburi)
                cursor.commit()
            except:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def exists(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return 1
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        res = directory_obj.exists(cursor, USER_ID, dburi)
        cursor.close()
        return res

    def is_collection(self, uri):
        if self._get_dav_resourcetype(uri) == COLLECTION:
            return 1
        return 0

    def copyone(self, src, dst, overwrite):
        return copyone(self, src, dst, overwrite)

    def copytree(self, src, dst, overwrite):
        return copytree(self, src, dst, overwrite)

    def moveone(self, uri):
        return moveone(self, uri)

    def movetree(self, src, dst, overwrite):
        return movetree(self, src, dst, overwrite)

    def delone(self, uri):
        return delone(self, uri)

    def deltree(self, uri):
        return deltree(self, uri)

    def copy(self, src, dst):
        content = self._get_dav_getcontenttype(src)
        data = self.get_data(src)
        self.put(dst, data, content)
        return 201

    def copycol(self, src, dst):
        return self.mkcol(dst)


class WebDAVAuthRequestHandler(AuthServer.BufferedAuthRequestHandler,
        WebDAVServer.DAVRequestHandler):

    def get_userinfo(self, user, password):
        global USER_ID
        dbname = self.path.split('/', 2)[1]
        if not dbname:
            return 1
        USER_ID = security.login(dbname, user, password)
        if USER_ID:
            return 1
        return 0
