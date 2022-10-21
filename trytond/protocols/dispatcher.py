# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import pydoc
import time

try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from sql import Table
from werkzeug.exceptions import abort
from werkzeug.wrappers import Response

from trytond import __version__, backend, security
from trytond.config import config, get_hostname
from trytond.exceptions import (
    ConcurrencyException, LoginException, RateLimitException, UserError,
    UserWarning)
from trytond.tools import is_instance_method
from trytond.transaction import Transaction
from trytond.worker import run_task
from trytond.wsgi import app

from .wrappers import with_pool

__all__ = ['register_authentication_service']

logger = logging.getLogger(__name__)

ir_configuration = Table('ir_configuration')
ir_lang = Table('ir_lang')
ir_module = Table('ir_module')
res_user = Table('res_user')
_MAX_LENGTH = 80


@app.route('/<string:database_name>/', methods=['POST'])
def rpc(request, database_name):
    methods = {
        'common.db.login': login,
        'common.db.logout': logout,
        'system.listMethods': list_method,
        'system.methodHelp': help_method,
        'system.methodSignature': lambda *a: 'signatures not supported',
        }
    return methods.get(request.rpc_method, _dispatch)(
        request, database_name, *request.rpc_params)


def login(request, database_name, user, parameters, language=None):
    context = {
        'language': language,
        '_request': request.context,
        }
    try:
        session = security.login(
            database_name, user, parameters, context=context)
        code = HTTPStatus.UNAUTHORIZED
    except backend.DatabaseOperationalError:
        logger.error('fail to connect to %s', database_name, exc_info=True)
        abort(HTTPStatus.NOT_FOUND)
    except RateLimitException:
        session = None
        code = HTTPStatus.TOO_MANY_REQUESTS
    if not session:
        abort(code)
    return session


@app.auth_required
def logout(request, database_name):
    auth = request.authorization
    security.logout(
        database_name, auth.get('userid'), auth.get('session'),
        context={'_request': request.context})


@app.route('/', methods=['POST'])
def root(request, *args):
    methods = {
        'common.server.version': lambda *a: __version__,
        'common.db.list': db_list,
        'common.authentication.services': authentication_services,
        }
    return methods[request.rpc_method](request, *request.rpc_params)


@app.route('/', methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options(request, path=None):
    return Response(status=HTTPStatus.NO_CONTENT)


def db_exist(request, database_name):
    try:
        backend.Database(database_name).connect()
        return True
    except Exception:
        return False


def db_list(request, *args):
    if not config.getboolean('database', 'list'):
        abort(HTTPStatus.FORBIDDEN)
    context = {'_request': request.context}
    hostname = get_hostname(request.host)
    with Transaction().start(
            None, 0, context=context, readonly=True, close=True,
            ) as transaction:
        return transaction.database.list(hostname=hostname)


def authentication_services(request):
    return _AUTHENTICATION_SERVICES


def register_authentication_service(name, url):
    _AUTHENTICATION_SERVICES.append((name, url))


_AUTHENTICATION_SERVICES = []


@app.auth_required
@with_pool
def list_method(request, pool):
    methods = []
    for type in ('model', 'wizard', 'report'):
        for object_name, obj in pool.iterobject(type=type):
            for method in obj.__rpc__:
                methods.append(type + '.' + object_name + '.' + method)
    return methods


def get_object_method(request, pool):
    method = request.rpc_method
    type, _ = method.split('.', 1)
    name = '.'.join(method.split('.')[1:-1])
    method = method.split('.')[-1]
    return pool.get(name, type=type), method


@app.auth_required
@with_pool
def help_method(request, pool):
    obj, method = get_object_method(request, pool)
    return pydoc.getdoc(getattr(obj, method))


def _safe_repr(args, kwargs, short=False):
    args = args + tuple('%s=%r' % (k, v) for k, v in kwargs.items())
    result = repr(args)
    if not short or len(result) < _MAX_LENGTH:
        return result
    return result[:_MAX_LENGTH] + ' [truncated]...)'


@app.auth_required
@with_pool
def _dispatch(request, pool, *args, **kwargs):
    obj, method = get_object_method(request, pool)
    if method in obj.__rpc__:
        rpc = obj.__rpc__[method]
    else:
        abort(HTTPStatus.FORBIDDEN)

    user = request.user_id
    session = None
    if request.authorization.type == 'session':
        session = request.authorization.get('session')

    if rpc.fresh_session and session:
        context = {'_request': request.context}
        if not security.check_timeout(
                pool.database_name, user, session, context=context):
            abort(HTTPStatus.UNAUTHORIZED)

    log_message = '%s.%s%s from %s@%s%s in %i ms'
    username = request.authorization.username
    if isinstance(username, bytes):
        username = username.decode('utf-8')
    log_args = (
        obj.__name__, method,
        _safe_repr(args, kwargs, not logger.isEnabledFor(logging.DEBUG)),
        username, request.remote_addr, request.path)

    def duration():
        return (time.monotonic() - started) * 1000
    started = time.monotonic()

    retry = config.getint('database', 'retry')
    for count in range(retry, -1, -1):
        if count != retry:
            time.sleep(0.02 * (retry - count))
        with Transaction().start(pool.database_name, user,
                readonly=rpc.readonly) as transaction:
            try:
                c_args, c_kwargs, transaction.context, transaction.timestamp \
                    = rpc.convert(obj, *args, **kwargs)
                transaction.context['_request'] = request.context
                meth = getattr(obj, method)
                if (rpc.instantiate is None
                        or not is_instance_method(obj, method)):
                    result = rpc.result(meth(*c_args, **c_kwargs))
                else:
                    assert rpc.instantiate == 0
                    inst = c_args.pop(0)
                    if hasattr(inst, method):
                        result = rpc.result(meth(inst, *c_args, **c_kwargs))
                    else:
                        result = [rpc.result(meth(i, *c_args, **c_kwargs))
                            for i in inst]
            except backend.DatabaseOperationalError:
                if count and not rpc.readonly:
                    transaction.rollback()
                    logger.debug("Retry: %i", retry - count + 1)
                    continue
                logger.exception(log_message, *log_args, duration())
                raise
            except (ConcurrencyException, UserError, UserWarning,
                    LoginException):
                logger.info(
                    log_message, *log_args, duration(),
                    exc_info=logger.isEnabledFor(logging.DEBUG))
                raise
            except Exception:
                logger.exception(log_message, *log_args, duration())
                raise
            # Need to commit to unlock SQLite database
            transaction.commit()
        while transaction.tasks:
            task_id = transaction.tasks.pop()
            run_task(pool, task_id)
        if session:
            context = {'_request': request.context}
            security.reset(pool.database_name, session, context=context)
        logger.info(log_message, *log_args, duration())
        logger.debug('Result: %r', result)
        response = app.make_response(request, result)
        if rpc.readonly and rpc.cache:
            response.headers.extend(rpc.cache.headers())
        return response
