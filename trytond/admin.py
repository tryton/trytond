# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import os
import logging
from getpass import getpass

from sql import Table

from trytond.transaction import Transaction
from trytond import backend
from trytond.pool import Pool
from trytond.config import config

__all__ = ['run']
logger = logging.getLogger(__name__)


def run(options):
    Database = backend.get('Database')
    init = {}
    for db_name in options.database_names:
        init[db_name] = False
        with Transaction().start(db_name, 0, _nocache=True):
            database = Database(db_name)
            database.connect()
            if options.update:
                if not database.test():
                    logger.info("init db")
                    database.init()
                    init[db_name] = True
            elif not database.test():
                raise Exception("'%s' is not a Tryton database!" % db_name)

    for db_name in options.database_names:
        if options.update:
            with Transaction().start(db_name, 0) as transaction,\
                    transaction.connection.cursor() as cursor:
                database = Database(db_name)
                database.connect()
                if not database.test():
                    raise Exception("'%s' is not a Tryton database!" % db_name)
                lang = Table('ir_lang')
                cursor.execute(*lang.select(lang.code,
                        where=lang.translatable == True))
                lang = set([x[0] for x in cursor.fetchall()])
            main_lang = config.get('database', 'language')
            lang.add(main_lang)
        else:
            lang = set()
        lang |= set(options.languages)
        pool = Pool(db_name)
        pool.init(update=options.update, lang=list(lang))

        if options.update_modules_list:
            with Transaction().start(db_name, 0) as transaction:
                Module = pool.get('ir.module')
                Module.update_list()

        if lang:
            with Transaction().start(db_name, 0) as transaction:
                pool = Pool()
                Lang = pool.get('ir.lang')
                languages = Lang.search([
                        ('code', 'in', lang),
                        ])
                Lang.write(languages, {
                        'translatable': True,
                        })

    for db_name in options.database_names:
        if init[db_name] or options.password:
            # try to read password from environment variable
            # TRYTONPASSFILE, empty TRYTONPASSFILE ignored
            passpath = os.getenv('TRYTONPASSFILE')
            password = ''
            if passpath:
                try:
                    with open(passpath) as passfile:
                        password = passfile.readline()[:-1]
                except Exception, err:
                    sys.stderr.write('Can not read password '
                        'from "%s": "%s"\n' % (passpath, err))

            if not password:
                while True:
                    password = getpass('Password for the user \'admin\' in the db %s: ' % db_name)
                    password2 = getpass('Password Confirmation: ')
                    if password != password2:
                        sys.stderr.write('Password Confirmation '
                            'doesn\'t match Password!\n')
                        continue
                    if not password:
                        sys.stderr.write('Password for the user \'admin\' is required!\n')
                        continue
                    break

            with Transaction().start(db_name, 0) as transaction:
                pool = Pool()
                User = pool.get('res.user')
                admin, = User.search([('login', '=', 'admin')])
                User.write([admin], {
                        'password': password,
                        })
