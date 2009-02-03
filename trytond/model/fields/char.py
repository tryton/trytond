#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Char(Field):
    _type = 'char'

    def __init__(self, string='', size=None, **args):
        super(Char, self).__init__(string=string, **args)
        self.size = size
