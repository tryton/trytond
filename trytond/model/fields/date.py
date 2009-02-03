#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Date(Field):
    _type = 'date'


class DateTime(Field):
    _type = 'datetime'


class Time(Field):
    _type = 'time'
