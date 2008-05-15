import time
import threading
import SimpleXMLRPCServer, signal, sys, xmlrpclib
import SocketServer
import socket
import logging
import os
from pysocket import PySocket
import traceback
import select
import BaseHTTPServer

_SERVICE = {}
_GROUP = {}
_RES = {}

LOG_DEBUG = 'debug'
LOG_INFO = 'info'
LOG_WARNING = 'warn'
LOG_ERROR = 'error'
LOG_CRITICAL = 'critical'

from config import CONFIG


class Service(object):
    _serviceEndPointID = 0

    def __init__(self, name=None):
        if name is None:
            return
        _SERVICE[name] = self
        self.__name = name
        self.method = {}
        self.exportedmethods = None
        self._response_process = None
        self._response_process_id = None

    def join_group(self, name):
        if not name in _GROUP:
            _GROUP[name] = {}
        _GROUP[name][self.__name] = self

    def export_method(self, method):
        if callable(method):
            self.method[method.__name__] = method

    def abort_response(self, description, origin, details):
        raise Exception("%s -- %s\n\n%s" % (origin, description, details))


class LocalService(Service):

    def __init__(self, name):
        super(LocalService, self).__init__()
        self.__name = name
        service = _SERVICE[name]
        self.service = service
        for method in service.method:
            setattr(self, method, service.method[method])


class ServiceUnavailable(Exception):
    pass

def service_exist(name):
    return (name in _SERVICE) and bool(_SERVICE[name])

def init_logger():
    if CONFIG['logfile']:
        logf = CONFIG['logfile']
        # test if the directories exist, else create them
        try:
            if not os.path.exists(os.path.dirname(logf)):
                os.makedirs(os.path.dirname(logf))
            try:
                fd_log = open(logf, 'a')
                handler = logging.StreamHandler(fd_log)
            except IOError:
                sys.stderr.write("ERROR: couldn't open the logfile\n")
                handler = logging.StreamHandler(sys.stdout)
        except OSError:
            sys.stderr.write("ERROR: couldn't create the logfile directory\n")
            handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.StreamHandler(sys.stdout)

    # create a format for log messages and dates
    formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s:%(name)s:%(message)s',
            '%a %b %d %H:%M:%S %Y')

    # tell the handler to use this format
    handler.setFormatter(formatter)

    # add the handler to the root logger
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


class Logger(object):

    def notify_channel(self, name, level, msg):
        log = logging.getLogger(name)
        getattr(log, level)(msg)


class Agent(object):
    _timers = []
    _logger = Logger()

    def set_alarm(self, function, time_start, args=None, kwargs=None):
        if not args:
            args = []
        if not kwargs:
            kwargs = {}
        wait = time_start - time.time()
        if wait > 0:
            self._logger.notify_channel('timers', LOG_DEBUG,
                    "Job scheduled in %s seconds for %s.%s" % \
                            (wait, function.im_class.__name__,
                                function.func_name))
            timer = threading.Timer(wait, function, args, kwargs)
            timer.start()
            self._timers.append(timer)
        for timer in self._timers[:]:
            if not timer.isAlive():
                self._timers.remove(timer)

    def quit(cls):
        for timer in cls._timers:
            timer.cancel()
    quit = classmethod(quit)


class RpcGateway(object):

    def __init__(self, name):
        self.name = name


class Dispatcher(object):

    def __init__(self):
        pass

    def monitor(self, sig):
        pass

    def run(self):
        pass


class XmlRpc(object):


    class RpcGateway(object):

        def __init__(self, name):
            self.name = name


class GenericXMLRPCRequestHandler:

    def _dispatch(self, method, params):
        host, port = self.sock.getpeername()[:2]
        Logger().notify_channel('web-service', LOG_INFO,
                'connection from %s:%d' % (host, port))
        try:
            name = self.path.split("/")[-1]
            service = LocalService(name)
            meth = getattr(service, method)
            res = meth(*params)
            return res
        except Exception, exp:
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_traceback))
            for path in sys.path:
                tb_s = tb_s.replace(path, '')
            if CONFIG['debug_mode']:
                import pdb
                traceb = sys.exc_info()[2]
                pdb.post_mortem(traceb)
            raise xmlrpclib.Fault(str(exp), tb_s)


class SimpleXMLRPCRequestHandler(GenericXMLRPCRequestHandler,
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.rpc_paths = (
            '/xmlrpc/db',
            '/xmlrpc/common',
            '/xmlrpc/object',
            '/xmlrpc/report',
            '/xmlrpc/wizard',
            )


class SecureXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):

    def setup(self):
        self.connection = self.request
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)


class SimpleThreadedXMLRPCServer(SocketServer.ThreadingMixIn,
        SimpleXMLRPCServer.SimpleXMLRPCServer):

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        SimpleXMLRPCServer.SimpleXMLRPCServer.server_bind(self)


class SimpleThreadedXMLRPCServer6(SimpleThreadedXMLRPCServer):
    address_family = socket.AF_INET6


class SecureThreadedXMLRPCServer(SimpleThreadedXMLRPCServer):

    def __init__(self, server_address, HandlerClass, logRequests=1):
        from OpenSSL import SSL
        SimpleThreadedXMLRPCServer.__init__(self, server_address, HandlerClass,
                logRequests)
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_privatekey_file(CONFIG['privatekey'])
        ctx.use_certificate_file(CONFIG['certificate'])
        self.socket = SSL.Connection(ctx, socket.socket(self.address_family,
            self.socket_type))
        self.server_bind()
        self.server_activate()


class SecureThreadedXMLRPCServer6(SecureThreadedXMLRPCServer):
    address_family = socket.AF_INET6


class HttpDaemon(threading.Thread):

    def __init__(self, interface, port, secure=False):
        threading.Thread.__init__(self)
        self.secure = secure
        self.running = False
        if secure:
            server_class = SecureThreadedXMLRPCServer
            if socket.has_ipv6:
                try:
                    socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                    server_class = SecureThreadedXMLRPCServer6
                    if not interface:
                        interface = '::'
                except:
                    pass
            if not interface:
                interface = '0.0.0.0'
            self.server = server_class((interface, port),
                    SecureXMLRPCRequestHandler, 0)
        else:
            server_class = SimpleThreadedXMLRPCServer
            if socket.has_ipv6:
                try:
                    socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                    server_class = SimpleThreadedXMLRPCServer6
                    if not interface:
                        interface = '::'
                except:
                    pass
            if not interface:
                interface = '0.0.0.0'
            self.server = server_class((interface, port),
                    SimpleXMLRPCRequestHandler, 0)

    def attach(self, path, gateway):
        pass

    def stop(self):
        self.running = False
        if os.name != 'nt':
            if hasattr(socket, 'SHUT_RDWR'):
                if self.secure:
                    self.server.socket.sock_shutdown(socket.SHUT_RDWR)
                else:
                    self.server.socket.shutdown(socket.SHUT_RDWR)
            else:
                if self.secure:
                    self.server.socket.sock_shutdown(2)
                else:
                    self.server.socket.shutdown(2)
        self.server.socket.close()

    def run(self):
        self.server.register_introspection_functions()

        self.running = True
        while self.running:
            self.server.handle_request()
        return True

        # If the server need to be run recursively
        #
        #signal.signal(signal.SIGALRM, self.my_handler)
        #signal.alarm(6)
        #while True:
        #    self.server.handle_request()
        #signal.alarm(0)          # Disable the alarm


class TinySocketClientThread(threading.Thread):
    def __init__(self, sock, threads, secure):
        threading.Thread.__init__(self)
        self.sock = sock
        self.threads = threads
        self.running = False
        self.secure = secure

    def run(self):
        self.running = True
        try:
            pysocket = PySocket(self.sock)
        except:
            self.sock.close()
            self.threads.remove(self)
            return False
        first = True
        timeout = 0
        while self.running:
            (rlist, wlist, xlist) = select.select([self.sock], [], [], 1)
            if not rlist:
                timeout += 1
                if timeout > 600:
                    break
                continue
            timeout = 0
            try:
                msg = pysocket.receive()
            except:
                pysocket.disconnect()
                self.threads.remove(self)
                return False
            if first:
                host, port = self.sock.getpeername()[:2]
                Logger().notify_channel('web-service', LOG_INFO,
                        'connection from %s:%d' % (host, port))
                first = False
            try:
                service = LocalService(msg[0])
                method = getattr(service, msg[1])
                res = method(*msg[2:])
                pysocket.send(res)
            except Exception, exp:
                tb_s = reduce(lambda x, y: x+y,
                        traceback.format_exception(sys.exc_type,
                            sys.exc_value, sys.exc_traceback))
                for path in sys.path:
                    tb_s = tb_s.replace(path, '')
                if CONFIG['debug_mode']:
                    import pdb
                    tback = sys.exc_info()[2]
                    pdb.post_mortem(tback)
                pysocket.send(str(exp), exception=True, traceback=tb_s)
        pysocket.disconnect()
        self.threads.remove(self)
        return True

    def stop(self):
        self.running = False


class TinySocketServerThread(threading.Thread):
    def __init__(self, interface, port, secure=False):
        threading.Thread.__init__(self)
        familly = socket.AF_INET
        if socket.has_ipv6:
            try:
                socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                familly = socket.AF_INET6
                if not interface:
                    interface = '::'
            except:
                pass
        if not interface:
            interface = '0.0.0.0'
        self.socket = socket.socket(familly, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if secure:
            from OpenSSL import SSL
            ctx = SSL.Context(SSL.SSLv23_METHOD)
            ctx.use_privatekey_file(CONFIG['privatekey'])
            ctx.use_certificate_file(CONFIG['certificate'])
            self.socket = SSL.Connection(ctx, self.socket)
        self.socket.bind((interface, port))
        self.socket.listen(5)
        self.threads = []
        self.secure = secure
        self.running = False

    def run(self):
        try:
            self.running = True
            while self.running:
                if not int(CONFIG['max_thread']) \
                        or len(self.threads) < int(CONFIG['max_thread']):
                    (clientsocket, address) = self.socket.accept()
                    c_thread = TinySocketClientThread(clientsocket, self.threads,
                            self.secure)
                    self.threads.append(c_thread)
                    c_thread.start()
            self.socket.close()
        except Exception, exp:
            self.socket.close()
            return False

    def stop(self):
        self.running = False
        for thread in self.threads:
            thread.stop()
        try:
            if self.secure:
                if hasattr(socket, 'SHUT_RDWR'):
                    self.socket.sock_shutdown(socket.SHUT_RDWR)
                else:
                    self.socket.sock_shutdown(2)
            else:
                if hasattr(socket, 'SHUT_RDWR'):
                    self.socket.shutdown(socket.SHUT_RDWR)
                else:
                    self.socket.shutdown(2)
            self.socket.close()
        except:
            return False


class BaseThreadedHTTPServer(SocketServer.ThreadingMixIn,
        BaseHTTPServer.HTTPServer):

    max_children = CONFIG['max_thread']

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        BaseHTTPServer.HTTPServer.server_bind(self)


class BaseThreadedHTTPServer6(BaseThreadedHTTPServer):
    address_family = socket.AF_INET6


class SecureThreadedHTTPServer(BaseThreadedHTTPServer):

    def __init__(self, server_address, HandlerClass):
        from OpenSSL import SSL
        BaseThreadedHTTPServer.__init__(self, server_address, HandlerClass)
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_privatekey_file(CONFIG['privatekey'])
        ctx.use_certificate_file(CONFIG['certificate'])
        self.socket = SSL.Connection(ctx, socket.socket(self.address_family,
            self.socket_type))
        self.server_bind()
        self.server_activate()


class SecureThreadedHTTPServer6(SecureThreadedHTTPServer):
    address_family = socket.AF_INET6


class WebDAVServerThread(threading.Thread):

    def __init__(self, interface, port, secure=False):
        from webdavsvc import WebDAVAuthRequestHandler, SecureWebDAVAuthRequestHandler, \
                TrytonDAVInterface
        threading.Thread.__init__(self)
        self.secure = secure
        self.running = False
        if secure:
            handler = SecureWebDAVAuthRequestHandler
            handler.IFACE_CLASS = TrytonDAVInterface(interface, port, secure)
            server_class = SecureThreadedHTTPServer
            if socket.has_ipv6:
                try:
                    socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                    server_class = SecureThreadedHTTPServer6
                    if not interface:
                        interface = '::'
                except:
                    pass
            if not interface:
                interface = '0.0.0.0'
            self.server = server_class((interface, port), handler)
        else:
            handler = WebDAVAuthRequestHandler
            handler.IFACE_CLASS = TrytonDAVInterface(interface, port, secure)
            server_class = BaseThreadedHTTPServer
            if socket.has_ipv6:
                try:
                    socket.getaddrinfo(interface or None, port, socket.AF_INET6)
                    server_class = BaseThreadedHTTPServer6
                    if not interface:
                        interface = '::'
                except:
                    pass
            if not interface:
                interface = '0.0.0.0'
            self.server = server_class((interface, port), handler)

    def stop(self):
        self.running = False
        if os.name != 'nt':
            if hasattr(socket, 'SHUT_RDWR'):
                if self.secure:
                    self.server.socket.sock_shutdown(socket.SHUT_RDWR)
                else:
                    self.server.socket.shutdown(socket.SHUT_RDWR)
            else:
                if self.secure:
                    self.server.socket.sock_shutdown(2)
                else:
                    self.server.socket.shutdown(2)
        self.server.socket.close()

    def run(self):
        self.running = True
        while self.running:
            self.server.handle_request()
        return True
