#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields


class Boolean(ModelSQL):
    'Boolean'
    _name = 'tests.boolean'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean',
            required=False)

Boolean()


class BooleanDefault(ModelSQL):
    'Boolean Default'
    _name = 'tests.boolean_default'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean',
            required=False)

    def default_boolean(self, cursor, user, context=None):
        return True

BooleanDefault()


class BooleanRequired(ModelSQL):
    'Boolean Required'
    _name = 'tests.boolean_required'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean',
            required=True)

BooleanRequired()


class Integer(ModelSQL):
    'Integer'
    _name = 'tests.integer'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

Integer()


class IntegerDefault(ModelSQL):
    'Integer Default'
    _name = 'tests.integer_default'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

    def default_integer(self, cursor, user, context=None):
        return 5

IntegerDefault()
