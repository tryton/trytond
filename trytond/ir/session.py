# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import json
from secrets import token_hex

from trytond.cache import Cache
from trytond.config import config
from trytond.model import Index, ModelSQL, fields

_session_timeout = datetime.timedelta(
    seconds=config.getint('session', 'timeout'))
_reset_interval = _session_timeout // 10


class Session(ModelSQL):
    "Session"
    __name__ = 'ir.session'
    _rec_name = 'key'

    key = fields.Char("Key", required=True, strip=False)
    _session_reset_cache = Cache('ir_session.session_reset', context=False)

    @classmethod
    def __setup__(cls):
        super(Session, cls).__setup__()
        table = cls.__table__()
        cls.__rpc__ = {}
        cls.__rpc__ = {}
        cls._sql_indexes.update({
                Index(table,
                    (table.key, Index.Equality()),
                    (table.create_uid, Index.Equality())),
                Index(table,
                    (table.key, Index.Equality()),
                    (table.create_date, Index.Equality())),
                Index(table,
                    (table.key, Index.Equality()),
                    (table.write_date, Index.Equality())),
                })

    @classmethod
    def default_key(cls, nbytes=None):
        return token_hex(nbytes)

    @classmethod
    def write(cls, *args):
        super().write(*args)
        for sessions in args[0:None:2]:
            for session in sessions:
                cls._session_reset_cache.set(session.key, session.write_date)

    @classmethod
    def new(cls, values=None):
        "Create a new session for the transaction user and return the key."
        if values is None:
            values = {}
        session, = cls.create([values])
        return session.key

    @classmethod
    def remove(cls, key, domain=None):
        "Delete the key session and return the login."
        domain = [
            ('key', '=', key),
            domain or [],
            ]
        sessions = cls.search(domain)
        if not sessions:
            return
        session, = sessions
        name = session.create_uid.login
        cls.delete(sessions)
        return name

    @classmethod
    def check(cls, user, key, domain=None):
        """
        Check user key against max_age and delete old one.
        Return True if key is still valid, False if the key is expired and None
        if the key does not exist.
        """
        now = datetime.datetime.now()
        timeout = datetime.timedelta(
            seconds=config.getint('session', 'max_age'))
        sessions = cls.search([
                ('create_uid', '=', user),
                domain or [],
                ])
        find, last_reset = None, None
        to_delete = []
        for session in sessions:
            if abs(session.create_date - now) < timeout:
                if session.key == key:
                    find = True
                    last_reset = session.write_date or session.create_date
            else:
                if find is None and session.key == key:
                    find = False
                to_delete.append(session)
        cls.delete(to_delete)
        if find:
            cls._session_reset_cache.set(key, last_reset)
        return find

    @classmethod
    def check_timeout(cls, user, key, domain=None):
        """
        Check user key against timeout.
        Return True if key is still valid otherwise the key is deleted.
        """
        now = datetime.datetime.now()
        timeout = datetime.timedelta(
            seconds=config.getint('session', 'timeout'))
        session, = cls.search([
                ('create_uid', '=', user),
                ('key', '=', key),
                domain or [],
                ], limit=1)
        timestamp = session.write_date or session.create_date
        valid = abs(timestamp - now) < timeout
        if not valid:
            cls.delete([session])
        return valid

    @classmethod
    def reset(cls, key, domain=None):
        "Reset key session timestamp"
        now = datetime.datetime.now()
        last_reset = cls._session_reset_cache.get(key)
        if last_reset is None or (now - _reset_interval) > last_reset:
            timestamp = now - _session_timeout
            sessions = cls.search([
                    ('key', '=', key),
                    ['OR',
                        ('create_date', '>=', timestamp),
                        ('write_date', '>=', timestamp),
                        ],
                    domain or [],
                    ])
            cls.write(sessions, {})

    @classmethod
    def clear(cls, users, domain=None):
        "Clear all sessions for users"
        sessions = cls.search([
                ('create_uid', 'in', users),
                domain or [],
                ])
        cls.delete(sessions)

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            # Ensure to get a different key for each record
            # default methods are called only once
            values.setdefault('key', cls.default_key())
        return super(Session, cls).create(vlist)


class SessionWizard(ModelSQL):
    "Session Wizard"
    __name__ = 'ir.session.wizard'

    data = fields.Text('Data')

    @classmethod
    def __setup__(cls):
        super(SessionWizard, cls).__setup__()
        cls.__rpc__ = {}

    @staticmethod
    def default_data():
        return json.dumps({})
