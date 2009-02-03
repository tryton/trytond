#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import sha
import psycopg2


class Field(object):
    symbol_c = '%s'

    @staticmethod
    def symbol_f(value):
        if value is None or value == False:
            return None
        elif isinstance(value, str):
            return unicode(value, 'utf-8')
        elif isinstance(value, unicode):
            return value
        return unicode(value)

    @staticmethod
    def sql_type(field):
        return None


class Boolean(Field):

    @staticmethod
    def symbol_f(value):
        return value and 'True' or 'False'

    @staticmethod
    def sql_type(field):
        return ('bool', 'bool')


class Integer(Field):

    @staticmethod
    def symbol_f(value):
        return int(value or 0)

    @staticmethod
    def sql_type(field):
        return ('int4', 'int4')


class BigInteger(Integer):

    @staticmethod
    def sql_type(field):
        return ('int8', 'int8')


class Char(Field):


    @staticmethod
    def sql_type(field):
        if field.size:
            return ('varchar', 'varchar(%d)' % (field.size,))
        return ('varchar', 'varchar')


class Sha(Field):

    @staticmethod
    def symbol_f(value):
        return value and sha.new(value).hexdigest() or ''

    @staticmethod
    def sql_type(field):
        return ('varchar', 'varchar(40)')


class Text(Field):

    @staticmethod
    def sql_type(field):
        return ('text', 'text')


class Float(Field):

    @staticmethod
    def symbol_f(value):
        return float(value or 0.0)

    @staticmethod
    def sql_type(field):
        return ('float8', 'float8')


class Numeric(Float):

    @staticmethod
    def sql_type(field):
        return ('numeric', 'numeric')


class Date(Field):

    @staticmethod
    def sql_type(field):
        return ('date', 'date')


class DateTime(Field):

    @staticmethod
    def sql_type(field):
        return ('timestamp', 'timestamp(0)')


class Time(Field):

    @staticmethod
    def sql_type(field):
        return ('time', 'time')


class Binary(Field):

    @staticmethod
    def symbol_f(value):
        return value and psycopg2.Binary(value) or None

    @staticmethod
    def sql_type(field):
        return ('bytea', 'bytea')


class Selection(Char):

    @staticmethod
    def sql_type(field):
        return ('varchar', 'varchar')


class Reference(Field):

    @staticmethod
    def sql_type(field):
        return ('varchar', 'varchar')


class Many2One(Field):

    @staticmethod
    def symbol_f(value):
        return value and int(value) or None

    @staticmethod
    def sql_type(field):
        return ('int4', 'int4')


class One2Many(Field):
    pass


class Many2Many(Field):
    pass


class Function(Field):
    pass


class Property(Function):
    pass


FIELDS = {
    'boolean': Boolean,
    'integer': Integer,
    'biginteger': BigInteger,
    'char': Char,
    'sha': Sha,
    'text': Text,
    'float': Float,
    'numeric': Numeric,
    'date': Date,
    'datetime': DateTime,
    'time': Time,
    'binary': Binary,
    'selection': Selection,
    'reference': Reference,
    'many2one': Many2One,
    'one2many': One2Many,
    'many2many': Many2Many,
    'function': Function,
    'property': Property,
}
