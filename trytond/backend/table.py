#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.


class TableHandlerInterface(object):
    '''
    Define generic interface to handle database table
    '''

    def __init__(self, cursor, table_name, object_name=None, module_name=None):
        super(TableHandlerInterface, self).__init__()
        self.cursor = cursor
        self.table_name = table_name
        self.object_name = object_name
        self.module_name = module_name

    @staticmethod
    def table_exist(cursor, table_name):
        '''
        Table exist

        :param cursor: the database cursor
        :param table_name: the table name
        :return: a boolean
        '''
        raise

    def column_exist(self, column_name):
        '''
        Column exist

        :param column_name: the column name
        :return: a boolean
        '''
        raise

    def alter_size(self, column_name, column_type):
        '''
        Modify size of a column

        :param column_name: the column name
        :param column_type: the column definition
        '''
        raise

    def alter_type(self, column_name, column_type):
        '''
        Modify type of a column

        :param column_name: the column name
        :param column_type: the column definition
        '''
        raise

    def db_default(self, column_name, value):
        '''
        Set a default on a column

        :param column_name: the column name
        :param value: the default value
        '''
        raise

    def add_raw_column(self, column_name, column_type, symbol_set,
            default_fun=None, field_size=None, migrate=True):
        '''
        Add a column

        :param column_name: the column name
        :param column_type: the column definition
        :param symbol_set: a tuple with the symbol char and the symbol function
        :param default_fun: the function that return the default value
        :param field_size: the size of the column if there is one
        :param migrate: boolean to try to migrate the column if exists
        '''
        raise

    def add_m2m(self, column_name, other_table, relation_table, rtable_from,
            rtable_to, on_delete_from, on_delete_to):
        '''
        Add a many2many

        :param column_name: the column name
        :param other_table: the name of the other table
        :param relation_table: the name of the table for the relation
        :param rtable_from: the column name in the relation table
            for this table
        :param rtable_to: the column name in the relation table
            for the other table
        :param on_delete_from: the "on delete" for the column
            in the relation table for this table
        :param on_delete_to: the "on delete" for the column
            in the relation table for the other table
        '''
        raise

    def add_fk(self, column_name, reference, on_delete=None):
        '''
        Add a foreign key

        :param column_name: the column name
        :param reference: the foreign table name
        :param on_delete: the "on delete" value
        '''
        raise

    def index_action(self, column_name, action='add'):
        '''
        Add/remove an index

        :param column_name: the column name
        :param action: 'add' or 'remove'
        '''
        raise

    def not_null_action(self, column_name, action='add'):
        '''
        Add/remove a "not null"

        :param column_name: the column name
        :param action: 'add' or 'remove'
        '''
        raise

    def add_constraint(self, ident, constraint, exception=False):
        '''
        Add a constraint

        :param ident: the name of the constraint
        :param constraint: the definition of the constraint
        :param exception: a boolean to raise or not an exception
            if it is not possible to add the constraint
        '''
        raise

    def drop_constraint(self, ident, exception=False):
        '''
        Remove a constraint

        :param ident: the name of the constraint
        :param exception: a boolean to raise or not an exception
            if it is not possible to remove the constraint
        '''
        raise

    def drop_column(self, column_name, exception=False):
        '''
        Remove a column

        :param column_name: the column name
        :param exception: a boolean to raise or not an exception
            if it is not possible to remove the column
        '''
        raise
