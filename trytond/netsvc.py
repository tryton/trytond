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

_SERVICE = {}
_GROUP = {}
_RES = {}

LOG_DEBUG = 'debug'
LOG_INFO = 'info'
LOG_WARNING = 'warn'
LOG_ERROR = 'error'
LOG_CRITICAL = 'critical'

from config import CONFIG


class ServiceEndPointCall(object):

    def __init__(self, id, method):
        self._id = id
        self._meth = method

    def __call__(self, *args):
        _RES[self._id] = self._meth(*args)
        return self._id


class ServiceEndPoint(object):

    def __init__(self, name, id):
        self._id = id
        self._meth = {}
        service = _SERVICE[name]
        for method in service.method:
            self._meth[method] = service.method[method]

    def __getattr__(self, name):
        return ServiceEndPointCall(self._id, self._meth[name])


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
        self.response = None

    def join_group(self, name):
        if not name in _GROUP:
            _GROUP[name] = {}
        _GROUP[name][self.__name] = self

    def export_method(self, method):
        if callable(method):
            self.method[method.__name__] = method

    def service_end_point(self, service):
        if Service._serviceEndPointID >= 2**16:
            Service._serviceEndPointID = 0
        Service._serviceEndPointID += 1
        return ServiceEndPoint(service, self._serviceEndPointID)

    def conversation_id(self):
        return 1

    def process_response(self, service, id):
        self._response_process, self._response_process_id = service, id

    def process_failure(self, service, id):
        pass

    def resume_response(self, service):
        pass

    def cancel_response(self, service):
        pass

    def suspend_response(self, service):
        if self._response_process:
            self._response_process(self._response_process_id,
                                   _RES[self._response_process_id])
        self._response_process = None
        self.response = service(self._response_process_id)

    def abort_response(self, description, origin, details):
        if not CONFIG['debug_mode']:
            raise Exception("%s -- %s\n\n%s" % (origin, description, details))
        else:
            raise

    def current_failure(self, service):
        pass


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
        try:
            name = self.path.split("/")[-1]
            service = LocalService(name)
            meth = getattr(service, method)
            service.service.response = None
            res = meth(*params)
            res2 = service.service.response
            if res2 != None:
                res = res2
            return res
        except Exception, exp:
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_traceback))
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


class SimpleThreadedXMLRPCServer(SocketServer.ThreadingMixIn,
        SimpleXMLRPCServer.SimpleXMLRPCServer):

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET,
                socket.SO_REUSEADDR, 1)
        SimpleXMLRPCServer.SimpleXMLRPCServer.server_bind(self)


class HttpDaemon(threading.Thread):

    def __init__(self, interface, port, secure=False):
        threading.Thread.__init__(self)
        self.__port = port
        self.__interface = interface
        self.secure = secure
        self.running = False
        if secure:
#            from ssl import SecureXMLRPCServer
#            class SecureXMLRPCRequestHandler(GenericXMLRPCRequestHandler,
#                    SecureXMLRPCServer.SecureXMLRPCRequestHandler):
#                SecureXMLRPCServer.SecureXMLRPCRequestHandler.rpc_paths = (
#                        '/xmlrpc/db',
#                        '/xmlrpc/common',
#                        '/xmlrpc/object',
#                        '/xmlrpc/report',
#                        '/xmlrpc/wizard',
#                        )
#            class SecureThreadedXMLRPCServer(SocketServer.ThreadingMixIn,
#                    SecureXMLRPCServer.SecureXMLRPCServer):
#
#                def server_bind(self):
#                    self.socket.setsockopt(socket.SOL_SOCKET,
#                            socket.SO_REUSEADDR, 1)
#                    SecureXMLRPCServer.SecureXMLRPCServer.server_bind(self)
#
#            self.server = SecureThreadedXMLRPCServer((interface, port),
#                    SecureXMLRPCRequestHandler,0)
            raise
        else:
            self.server = SimpleThreadedXMLRPCServer((interface, port),
                    SimpleXMLRPCRequestHandler,0)

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
    def __init__(self, sock, threads):
        threading.Thread.__init__(self)
        self.sock = sock
        self.threads = threads
        self.running = False

    def run(self):
        self.running = True
        try:
            pysocket = PySocket(self.sock)
        except:
            self.sock.close()
            self.threads.remove(self)
            return False
        while self.running:
            (rlist, wlist, xlist) = select.select([self.sock], [], [], 1)
            if not rlist:
                continue
            try:
                msg = pysocket.receive()
            except:
                self.sock.close()
                self.threads.remove(self)
                return False
            try:
                service = LocalService(msg[0])
                method = getattr(service, msg[1])
                service.service.response = None
                res = method(*msg[2:])
                res2 = service.service.response
                if res2 != None:
                    res = res2
                pysocket.send(res)
            except Exception, exp:
                tb_s = reduce(lambda x, y: x+y,
                        traceback.format_exception(sys.exc_type,
                            sys.exc_value, sys.exc_traceback))
                if CONFIG['debug_mode']:
                    import pdb
                    tback = sys.exc_info()[2]
                    pdb.post_mortem(tback)
                pysocket.send(exp, exception=True, traceback=tb_s)
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.threads.remove(self)
        return True

    def stop(self):
        self.running = False


class TinySocketServerThread(threading.Thread):
    def __init__(self, interface, port, secure=False):
        threading.Thread.__init__(self)
        self.__port = port
        self.__interface = interface
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.__interface, self.__port))
        self.socket.listen(5)
        self.threads = []
        self.secure = secure
        self.running = False

    def run(self):
        try:
            self.running = True
            while self.running:
                (clientsocket, address) = self.socket.accept()
                c_thread = TinySocketClientThread(clientsocket, self.threads)
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
            if hasattr(socket, 'SHUT_RDWR'):
                self.socket.shutdown(socket.SHUT_RDWR)
            else:
                self.socket.shutdown(2)
            self.socket.close()
        except:
            return False
