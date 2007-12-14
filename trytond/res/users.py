"Users"
from trytond.osv import fields, OSV, ExceptOSV
#from trytond.tools import Cache


class Groups(OSV):
    "Groups"
    _name = "res.groups"
    _description = __doc__
    _columns = {
        'name': fields.Char('Group Name', size=64, required=True),
        'model_access': fields.One2Many('ir.model.access', 'group_id',
            'Access Controls'),
        'rule_groups': fields.Many2Many('ir.rule.group', 'group_rule_group_rel',
            'group_id', 'rule_group_id', 'Rules',
            domain="[('global', '<>', True)]"),
        'menu_access': fields.Many2Many('ir.ui.menu', 'ir_ui_menu_group_rel',
            'gid', 'menu_id', 'Access Menu'),
    }
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The name of the group must be unique!')
    ]

    def write(self, cursor, user, ids, vals, context=None):
        if 'name' in vals:
            if vals['name'].startswith('-'):
                raise ExceptOSV('Error',
                        'The name of the group can not start with "-"')
        res = super(Groups, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the company_get method
        self.pool.get('ir.rule').domain_get()
        return res

Groups()


class Roles(OSV):
    "Roles"
    _name = "res.roles"
    _description = __doc__
    _columns = {
        'name': fields.Char('Role Name', size=64, required=True),
        'parent_id': fields.Many2One('res.roles', 'Parent', select=True),
        'child_id': fields.One2Many('res.roles', 'parent_id', 'Childs')
    }

    def check_recursion(self, cursor, user, ids, parent=None):
        "Check for recursion"
        return super(Roles, self).check_recursion(cursor, user, ids,
                parent=parent)

    _constraints = [
        (check_recursion, 'Error! You can not create recursive roles.',
            ['parent_id'])
    ]

Roles()


class Users(OSV):
    "Users"
    _name = "res.users"
    _log_access = False
    _description = __doc__
    _columns = {
        'name': fields.Char('Name', size=64, required=True, select=True),
        'login': fields.Char('Login', size=64, required=True),
        'password': fields.Char('Password', size=64, invisible=True),
        'signature': fields.Text('Signature', size=64),
        #'address_id': fields.Many2One('res.partner.address', 'Address'),
        'active': fields.Boolean('Active'),
        'action_id': fields.Many2One('ir.actions.actions', 'Home Action'),
        'menu_id': fields.Many2One('ir.actions.actions', 'Menu Action'),
        'groups_id': fields.Many2Many('res.groups', 'res_groups_users_rel',
            'uid', 'gid', 'Groups'),
        'roles_id': fields.Many2Many('res.roles', 'res_roles_users_rel',
            'uid', 'rid', 'Roles'),
        #'company_id': fields.Many2One('res.company', 'Company'),
        'rule_groups': fields.Many2Many('ir.rule.group', 'user_rule_group_rel',
            'user_id', 'rule_group_id', 'Rules',
            domain="[('global', '<>', True)]"),
    }
    _sql_constraints = [
        ('login_key', 'UNIQUE (login)',
            'You can not have two users with the same login!')
    ]
    _defaults = {
        'password' : lambda *a: '',
        'active' : lambda *a: 1,
    }
#    def company_get(self, cursor, user, uid2):
#        company_id = self.pool.get('res.users').browse(cursor, user,
#               user).company_id.id
#        return company_id
#    company_get = Cache()(company_get)

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Users, self).write(cursor, user, ids, vals, context=context)
#        self.company_get()
        # Restart the cache on the company_get method
        self.pool.get('ir.rule').domain_get()
        return res

    def unlink(self, cursor, user, ids, context=None):
        if 1 in ids:
            raise ExceptOSV('UserError',
                    'You can not remove the root user\n' \
                            'as it is used internally for resources\n' \
                            'created by Tiny ERP ' \
                            '(updates, module installation, ...)')
        return super(Users, self).unlink(cursor, user, ids, context=context)

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=80):
        if args is None:
            args = []
        ids = []
        if name:
            ids = self.search(cursor, user, [('login', '=', name)] + args,
                    limit=limit, context=context)
        if not ids:
            ids = self.search(cursor, user, [('name', operator, name)] + args,
                    limit=limit, context=context)
        return self.name_get(cursor, user, ids, context=context)

    def copy(self, cursor, user, obj_id, default=None, context=None):
        if default is None:
            default = {}
        login = self.read(cursor, user, obj_id, ['login'])['login']
        default.update({'login': login+' (copy)'})
        return super(Users, self).copy(cursor, user, obj_id, default,
                context=context)
Users()


class Groups2(Groups):
    _columns = {
        'users': fields.many2many('res.users', 'res_groups_users_rel', 'gid',
            'uid', 'Users'),
    }

Groups2()
