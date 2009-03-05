#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


class UIMenuGroup(ModelSQL):
    "UI Menu - Group"
    _name = 'ir.ui.menu-res.group'
    _table = 'ir_ui_menu_group_rel'
    menu_id = fields.Many2One('ir.ui.menu', 'Menu', ondelete='RESTRICT',
            select=1, required=True)
    gid = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

UIMenuGroup()


class ActionGroup(ModelSQL):
    "Action - Group"
    _name = 'ir.action-res.group'
    _table = 'ir_action_group_rel'
    action_id = fields.Many2One('ir.action', 'Action', ondelete='RESTRICT',
            select=1, required=True)
    gid = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

ActionGroup()


class ModelFieldGroup(ModelSQL):
    "Model Field Group Rel"
    _name = 'ir.model.field-res.group'
    _table = 'ir_model_field_group_rel'
    field_id = fields.Many2One('ir.model.field', 'Model Field',
            ondelete='RESTRICT', select=1, required=True)
    group_id = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

ModelFieldGroup()


class RuleGroupGroup(ModelSQL):
    "Rule Group - Group"
    _name = 'ir.rule.group-res.group'
    _table = 'group_rule_group_rel'
    rule_group_id = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='RESTRICT', select=1, required=True)
    group_id = fields.Many2One('res.group', 'Group', ondelete='CASCADE',
            select=1, required=True)

RuleGroupGroup()


class RuleGroupUser(ModelSQL):
    "Rule Group - User"
    _name = 'ir.rule.group-res.user'
    _table = 'user_rule_group_rel'
    rule_group_id = fields.Many2One('ir.rule.group', 'Rule Group',
            ondelete='RESTRICT', select=1, required=True)
    user_id = fields.Many2One('res.user', 'User', ondelete='CASCADE',
            select=1, required=True)

RuleGroupUser()
