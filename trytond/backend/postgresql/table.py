#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.backend.table import TableHandlerInterface
from trytond.backend.postgresql.fields import FIELDS
import logging


class TableHandler(TableHandlerInterface):

    def __init__(self, cursor, table_name, object_name=None, module_name=None,
            history=False):
        super(TableHandler, self).__init__(cursor, table_name,
                object_name=object_name, module_name=module_name)
        self._columns = {}
        self._constraints = []
        self._fk_deltypes = {}
        self._indexes = {}
        self._field2module = {}

        # Create new table if necessary
        if not self.table_exist(self.cursor, self.table_name):
            if not history:
                self.cursor.execute('CREATE TABLE "%s" ' \
                                "(id SERIAL NOT NULL, " \
                                "PRIMARY KEY(id))"% self.table_name)
            else:
                self.cursor.execute('CREATE TABLE "%s" ' \
                        '(id INTEGER)' % self.table_name)
        self._update_definitions()

    @staticmethod
    def table_exist(cursor, table_name):
        cursor.execute("SELECT relname FROM pg_class " \
                           "WHERE relkind = 'r' AND relname = %s",
                       (table_name,))
        return bool(cursor.rowcount)

    def column_exist(self, column_name):
        return column_name in self._columns

    def _update_definitions(self):
        # Fetch columns definitions from the table
        self.cursor.execute("SELECT at.attname, at.attlen, "\
                         "at.atttypmod, at.attnotnull, at.atthasdef, "\
                         "ty.typname, "\
                         "CASE WHEN at.attlen = -1 "\
                           "THEN at.atttypmod-4 "\
                           "ELSE at.attlen END as size "\
                       "FROM pg_class cl "\
                         "JOIN pg_attribute at on (cl.oid = at.attrelid) "\
                         "JOIN pg_type ty on (at.atttypid = ty.oid) "\
                       "WHERE cl.relname = %s AND at.attnum > 0",
                       (self.table_name,))
        self._columns = {}
        for line in self.cursor.fetchall():
            column, length, typmod, notnull, hasdef, typname, size = line
            self._columns[column] = {
                "length": length,
                "typmod": typmod,
                "notnull": notnull ,
                "hasdef": hasdef,
                "size": size,
                "typname": typname}

        # fetch constrains for the table
        self.cursor.execute("SELECT co.contype, co.confdeltype, at.attname, "\
                         "cl2.relname, co.conname "\
                       "FROM pg_constraint co "\
                         "LEFT JOIN pg_class cl on (co.conrelid = cl.oid) "\
                         "LEFT JOIN pg_class cl2 on (co.confrelid = cl2.oid) "\
                         "LEFT JOIN pg_attribute at on (co.conkey[1] = at.attnum) "\
                       "WHERE cl.relname = %s AND at.attrelid = cl.oid",
                       (self.table_name,))
        self._constraints = []
        self._fk_deltypes = {}
        for line in self.cursor.fetchall():
            contype, confdeltype, column, ref, conname = line
            if contype == 'f':
                self._fk_deltypes[column] = confdeltype
            else:
                if conname not in self._constraints:
                    self._constraints.append(conname)

        # Fetch indexes defined for the table
        self.cursor.execute("SELECT cl2.relname "\
                       "FROM pg_index ind "\
                         "JOIN pg_class cl on (cl.oid = ind.indrelid) "\
                         "JOIN pg_class cl2 on (cl2.oid = ind.indexrelid) "\
                       "WHERE cl.relname = %s",
                       (self.table_name,))
        self._indexes = [l[0] for l in self.cursor.fetchall()]

        # Keep track of which module created each field
        self._field2module = {}
        if self.object_name is not None:
            self.cursor.execute('SELECT f.name, f.module '\
                           'FROM ir_model_field f '\
                             'JOIN ir_model m on (f.model=m.id) '\
                           'WHERE m.model = %s',
                           (self.object_name,)
                           )
            for line in self.cursor.fetchall():
                self._field2module[line[0]] = line[1]

    def alter_size(self, column_name, column_type):

        self.cursor.execute("ALTER TABLE \"%s\" " \
                       "RENAME COLUMN \"%s\" " \
                       "TO temp_change_size" % \
                       (self.table_name, column_name))
        self.cursor.execute("ALTER TABLE \"%s\" " \
                       "ADD COLUMN \"%s\" %s" % \
                       (self.table_name, column_name, column_type))
        self.cursor.execute("UPDATE \"%s\" " \
                       "SET \"%s\" = temp_change_size::%s" % \
                       (self.table_name, column_name, column_type))
        self.cursor.execute("ALTER TABLE \"%s\" " \
                       "DROP COLUMN temp_change_size" % \
                       (self.table_name,))
        self._update_definitions()

    def alter_type(self, column_name, column_type):
        self.cursor.execute('ALTER TABLE "' + self.table_name + '" ' \
                'ALTER "' + column_name + '" TYPE ' + column_type)
        self._update_definitions()

    def db_default(self, column_name, value):
        self.cursor.execute('ALTER TABLE "' + self.table_name + '" ' \
                'ALTER COLUMN "' + column_name + '" SET DEFAULT %s',
                (value,))

    def add_raw_column(self, column_name, column_type, symbol_set,
            default_fun=None, field_size=None, migrate=True):
        if self.column_exist(column_name):
            if not migrate:
                return
            base_type = column_type[0].lower()
            if base_type != self._columns[column_name]['typname']:
                if (self._columns[column_name]['typname'], base_type) in [
                        ('varchar', 'text'),
                        ('text', 'varchar'),
                        ('date', 'timestamp'),
                        ('int4', 'float8'),
                        ]:
                    self.alter_type(column_name, base_type)
                else:
                    logging.getLogger('init').warning(
                        'Unable to migrate column %s on table %s ' \
                                'from %s to %s.' % \
                        (column_name, self.table_name,
                            self._columns[column_name]['typname'], base_type))

            if base_type == 'varchar' \
                    and self._columns[column_name]['typname'] == 'varchar':
                # Migrate size
                if field_size == None:
                    if self._columns[column_name]['size'] > 0:
                        self.alter_size(column_name, base_type)
                    pass
                elif self._columns[column_name]['size'] == field_size:
                    pass
                elif self._columns[column_name]['size'] > 0 and \
                        self._columns[column_name]['size'] < field_size:
                    self.alter_size(column_name, column_type[1])
                else:
                    logging.getLogger('init').warning(
                        'Unable to migrate column %s on table %s ' \
                                'from varchar(%s) to varchar(%s).' % \
                        (column_name, self.table_name,
                         self._columns[column_name]['size'] > 0 and \
                             self._columns[column_name]['size'] or "",
                         field_size))
            return

        column_type = column_type[1]
        self.cursor.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' %
                       (self.table_name, column_name, column_type))

        # check if table is non-empty:
        self.cursor.execute('SELECT 1 FROM "%s" limit 1' % self.table_name)
        if self.cursor.rowcount:
            # Populate column with default values:
            default = None
            if default_fun is not None:
                default = default_fun(self.cursor, 0, {})
            self.cursor.execute('UPDATE "' + self.table_name + '" '\
                                'SET "' + column_name + '" = ' + symbol_set[0],
                                (symbol_set[1](default),))

        self._update_definitions()

    def add_m2m(self, column_name, other_table, relation_table, rtable_from,
            rtable_to, on_delete_from, on_delete_to):
        if not self.table_exist(self.cursor, other_table):
            raise Exception("table %s not found"%other_table)
        rtable = TableHandler(
            self.cursor, relation_table, object_name=None,
            module_name= self.module_name)
        integer = FIELDS['integer']
        rtable.add_raw_column(rtable_from, integer.sql_type(None),
                (integer.symbol_c, integer.symbol_f))
        rtable.add_raw_column(rtable_to,  integer.sql_type(None),
                (integer.symbol_c, integer.symbol_f))
        rtable.add_fk(rtable_from, self.table_name, on_delete=on_delete_from)
        rtable.add_fk(rtable_to, other_table, on_delete=on_delete_to)
        rtable.not_null_action(rtable_from)
        rtable.not_null_action(rtable_to)
        rtable.index_action(rtable_from, 'add')
        rtable.index_action(rtable_to, 'add')

    def add_fk(self, column_name, reference, on_delete=None):
        on_delete_code = {
            'RESTRICT': 'r',
            'NO ACTION': 'a',
            'CASCADE': 'c',
            'SET NULL': 'n',
            'SET DEFAULT': 'd',
            }
        if on_delete is not None :
            on_delete = on_delete.upper()
            if on_delete not in on_delete_code:
                raise Exception('On delete action not supported!')
        else:
            on_delete = 'SET NULL'
        code = on_delete_code[on_delete]

        self.cursor.execute('SELECT conname FROM pg_constraint ' \
                'WHERE conname = %s',
                (self.table_name + '_' + column_name + '_fkey',))
        add = False
        if not self.cursor.rowcount:
            add = True
        elif self._fk_deltypes.get(column_name) != code:
            self.cursor.execute('ALTER TABLE "' + self.table_name + '" ' \
                    'DROP CONSTRAINT "' + self.table_name + '_' + \
                    column_name + '_fkey"')
            add = True
        if add:
            self.cursor.execute('ALTER TABLE "' + self.table_name + '" ' \
                    'ADD FOREIGN KEY ("' + column_name + '") ' \
                        'REFERENCES "' + reference + '" ' \
                        'ON DELETE ' + on_delete)
        self._update_definitions()

    def index_action(self, column_name, action='add'):
        index_name = "%s_%s_index" % (self.table_name, column_name)

        if action == 'add':
            if index_name in self._indexes:
                return
            self.cursor.execute('CREATE INDEX "' + index_name + '" ' \
                               'ON "' + self.table_name + '" ("' + column_name + '")')
            self._update_definitions()
        elif action == 'remove':
            if self._field2module.get(column_name) != self.module_name:
                return

            self.cursor.execute("SELECT * FROM pg_indexes " \
                                "WHERE indexname = '%s'" %
                           (index_name,))
            if self.cursor.rowcount:
                self.cursor.execute('DROP INDEX "%s" ' % (index_name,))
                self._update_definitions()
        else:
            raise Exception('Index action not supported!')

    def not_null_action(self, column_name, action='add'):
        if not self.column_exist(column_name):
            return

        if action == 'add':
            if self._columns[column_name]['notnull']:
                return
            self.cursor.execute('SELECT id FROM "%s" ' \
                               'WHERE "%s" IS NULL' % \
                               (self.table_name, column_name))
            if not self.cursor.rowcount:
                self.cursor.execute('ALTER TABLE "' + self.table_name + '" ' \
                                   'ALTER COLUMN "' + column_name + '" ' \
                                   "SET NOT NULL")
                self._update_definitions()
            else:
                logging.getLogger('init').warning(
                    'Unable to set column %s ' \
                        'of table %s not null !\n'\
                        'Try to re-run: ' \
                        'trytond.py --update=module\n' \
                        'If it doesn\'t work, update records and execute manually:\n' \
                        'ALTER TABLE "%s" ALTER COLUMN "%s" SET NOT NULL' % \
                        (column_name, self.table_name, self.table_name, column_name))
        elif action == 'remove':
            if not self._columns[column_name]['notnull']:
                return
            if self._field2module.get(column_name) != self.module_name:
                return
            self.cursor.execute('ALTER TABLE "%s" ' \
                               'ALTER COLUMN "%s" DROP NOT NULL' %
                           (self.table_name, column_name))
            self._update_definitions()
        else:
            raise Exception('Not null action not supported!')

    def add_constraint(self, ident, constraint, exception=False):
        ident = self.table_name + "_" + ident
        if ident in self._constraints:
            # This constrain already exist
            return
        try:
            self.cursor.execute('ALTER TABLE "%s" ' \
                           'ADD CONSTRAINT "%s" %s' % \
                           (self.table_name, ident, constraint,))
        except:
            if exception:
                raise
            logging.getLogger('init').warning(
                'unable to add \'%s\' constraint on table %s !\n' \
                'If you want to have it, you should update the records ' \
                'and execute manually:\n'\
                'ALTER table "%s" ADD CONSTRAINT "%s" %s' % \
                (constraint, self.table_name, self.table_name,
                 ident, constraint,))
        self._update_definitions()

    def drop_constraint(self, ident, exception=False):
        ident = self.table_name + "_" + ident
        if ident not in self._constraints:
            return
        try:
            self.cursor.execute('ALTER TABLE "%s" ' \
                    'DROP CONSTRAINT "%s"' % \
                    (self.table_name, ident))
        except:
            if exception:
                raise
            logging.getLogger('init').warning(
                'unable to drop \'%s\' constraint on table %s!' % \
                (ident, self.table_name))
        self._update_definitions()

    def drop_column(self, column_name, exception=False):
        if not self.column_exist(column_name):
            return
        try:
            self.cursor.execute(
                'ALTER TABLE "%s" DROP COLUMN "%s"' %
                (self.table_name, column_name))

        except:
            if exception:
                raise
            logging.getLogger('init').warning(
                'unable to drop \'%s\' column on table %s!' % \
                (column_name, self.table_name))
        self._update_definitions()
