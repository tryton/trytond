#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import threading
import SocketServer
import socket
import logging
import os
import BaseHTTPServer
from trytond.protocols.sslsocket import SSLSocket
from config import CONFIG


#-- WebDAV server

class BaseThreadedHTTPServer(SocketServer.ThreadingMixIn,
        BaseHTTPServer.HTTPServer):

    max_children = CONFIG['max_thread']

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        BaseHTTPServer.HTTPServer.server_bind(self)


class SecureThreadedHTTPServer(BaseThreadedHTTPServer):

    def __init__(self, server_address, HandlerClass):
        BaseThreadedHTTPServer.__init__(self, server_address, HandlerClass)
        self.socket = SSLSocket(socket.socket(self.address_family,
                                              self.socket_type))
        self.server_bind()
        self.server_activate()


class WebDAVServerThread(threading.Thread):

    def __init__(self, interface, port, secure=False):
        from webdavsvc import WebDAVAuthRequestHandler, SecureWebDAVAuthRequestHandler, \
                TrytonDAVInterface
        threading.Thread.__init__(self)
        self.secure = secure
        self.running = False
        ipv6 = False
        if socket.has_ipv6:
            try:
                socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                ipv6 = True
            except:
                pass
        if secure:
            handler_class = SecureWebDAVAuthRequestHandler
            server_class = SecureThreadedHTTPServer
            if ipv6:
                server_class = SecureThreadedHTTPServer6
        else:
            handler_class = WebDAVAuthRequestHandler
            server_class = BaseThreadedHTTPServer
            if ipv6:
                server_class = BaseThreadedHTTPServer6
        handler_class.IFACE_CLASS = TrytonDAVInterface(interface, port, secure)
        self.server = server_class((interface, port), handler_class)

    def stop(self):
        self.running = False
        if os.name != 'nt':
            if hasattr(socket, 'SHUT_RDWR'):
                self.server.socket.shutdown(socket.SHUT_RDWR)
            else:
                self.server.socket.shutdown(2)
        self.server.socket.close()

    def run(self):
        self.running = True
        while self.running:
            self.server.handle_request()
        return True

#--- IPv6 Servers

class BaseThreadedHTTPServer6(BaseThreadedHTTPServer):
    address_family = socket.AF_INET6

#--- Secure IPv6 Servers

class SecureThreadedHTTPServer6(SecureThreadedHTTPServer):
    address_family = socket.AF_INET6
