#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

class Float(float):

    def __init__(self, value):
        super(Float, self).__init__()
        self.__decimal = value

    @property
    def decimal(self):
        return self.__decimal

    def __repr__(self):
        return self.decimal

    def __str__(self):
        return self.decimal
