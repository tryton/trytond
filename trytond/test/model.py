#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton, ModelSQL, fields


class Singleton(ModelSingleton, ModelSQL):
    'Singleton'
    _name = 'test.singleton'
    _description = __doc__

    name = fields.Char('Name')

    def default_name(self):
        return 'test'

Singleton()


class URLObject(ModelSQL):
    _name = 'test.urlobject'

    name = fields.Char('Name')


URLObject()


class ModelInherits(ModelSQL):
    _name = 'test.model_inherits'

    name = fields.Char('Name')

ModelInherits()


class ModelInheritsSubModel(ModelSQL):
    _name = 'test.submodel'
    _inherits = {'test.model_inherits': 'parent_model'}

    subfield = fields.Char('SubField')
    parent_model = fields.Many2One('test.model_inherits', 'Parent model',
        required=True)

ModelInheritsSubModel()


class ModelInheritsSubSubModel(ModelSQL):
    _name = 'test.subsubmodel'
    _inherits = {'test.submodel': 'parent_model'}

    subsubfield = fields.Char('SubField')
    parent_model = fields.Many2One('test.submodel', 'Parent model',
        required=True)

ModelInheritsSubSubModel()


class ModelInheritsSubSubSubModel(ModelSQL):
    _name = 'test.subsubsubmodel'
    _inherits = {'test.subsubmodel': 'parent_model'}

    subsubsubfield = fields.Char('SubField')
    parent_model = fields.Many2One('test.subsubmodel', 'Parent model',
        required=True)

ModelInheritsSubSubSubModel()


class ModelInheritsOverriddenFieldModel(ModelSQL):
    _name = 'test.overriddeninheritedfieldmodel'
    _inherits = {'test.subsubmodel': 'parent_model'}

    subfield = fields.Integer('Overridden field')
    parent_model = fields.Many2One('test.subsubmodel', 'Parent model',
        required=True)

ModelInheritsOverriddenFieldModel()
