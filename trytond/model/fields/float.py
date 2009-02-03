#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Float(Field):
    _type = 'float'

    def __init__(self, string='', digits=None, **args):
        super(Float, self).__init__(string=string, **args)
        self.digits = digits
