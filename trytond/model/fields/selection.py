#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field


class Selection(Field):
    _type = 'selection'

    def __init__(self, selection, string='', sort=True, translate=True, **args):
        super(Selection, self).__init__(string=string, **args)
        self.selection = selection
        self.sort = sort
        self.translate_selection = translate
