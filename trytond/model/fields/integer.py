#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Integer(Field):
    _type = 'integer'


class BigInteger(Field):
    _type = 'biginteger'
