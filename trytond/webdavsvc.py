import urlparse
import socket
import base64
from DAV import AuthServer, WebDAVServer, iface
from DAV.errors import *
from DAV.constants import COLLECTION, OBJECT
from DAV.utils import get_uriparentpath, get_urifilename
from netsvc import LocalService
import security
import pooler
from version import PACKAGE, VERSION, WEBSITE

# This work because there is only one thread
USER_ID = 0


class TrytonDAVInterface(iface.dav_interface):

    def __init__(self, interface, port):
        self.baseuri = 'http://%s:%s/' % (interface or socket.getfqdn(), port)

    def _get_dburi(self, uri):
        uri = uri[len(self.baseuri):]
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
        if uri[:-1] != '/':
            uri += '/'
        for child in directory_obj.get_childs(cursor, USER_ID, dburi):
            res.append(urlparse.urljoin(self.baseuri, uri + child))
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
        return directory_obj.get_data(cursor, USER_ID, dburi)

    def _get_dav_resourcetype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return COLLECTION
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        return directory_obj.get_resourcetype(cursor, USER_ID, dburi)

    def _get_dav_displayname(self, uri):
        raise DAV_Secret

    def _get_dav_getcontentlength(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return '0'
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        return directory_obj.get_contentlength(cursor, USER_ID, dburi)

    def _get_dav_getcontenttype(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or self.is_collection(uri):
            return "text/html"
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        return directory_obj.get_contenttype(cursor, USER_ID, dburi)

    def exists(self, uri):
        dbname, dburi = self._get_dburi(uri)
        if not dbname or not dburi:
            return 1
        pool = pooler.get_pool(dbname)
        cursor = pooler.get_db(dbname).cursor()
        directory_obj = pool.get('webdav.directory')
        return directory_obj.exists(cursor, USER_ID, dburi)

    def is_collection(self, uri):
        if self._get_dav_resourcetype(uri) == COLLECTION:
            return 1
        return 0


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
