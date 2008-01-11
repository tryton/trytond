"User"
from trytond.osv import fields, OSV, ExceptOSV
#from trytond.tools import Cache


class Group(OSV):
    "Group"
    _name = "res.group"
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
        res = super(Group, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the company_get method
        self.pool.get('ir.rule').domain_get()
        return res

Group()


class Role(OSV):
    "Role"
    _name = "res.role"
    _description = __doc__
    _columns = {
        'name': fields.Char('Role Name', size=64, required=True),
        'parent_id': fields.Many2One('res.role', 'Parent', select=True),
        'child_id': fields.One2Many('res.role', 'parent_id', 'Childs')
    }

    def check_recursion(self, cursor, user, ids, parent=None):
        "Check for recursion"
        return super(Role, self).check_recursion(cursor, user, ids,
                parent=parent)

    _constraints = [
        (check_recursion, 'Error! You can not create recursive roles.',
            ['parent_id'])
    ]

Role()


class User(OSV):
    "User"
    _name = "res.user"
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
        'groups_id': fields.Many2Many('res.group', 'res_group_user_rel',
            'uid', 'gid', 'Groups'), 
        'roles_id': fields.Many2Many('res.role', 'res_role_user_rel',
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
#        company_id = self.pool.get('res.user').browse(cursor, user,
#               user).company_id.id
#        return company_id
#    company_get = Cache()(company_get)

    def write(self, cursor, user, ids, vals, context=None):
        res = super(User, self).write(cursor, user, ids, vals, context=context)
        # Restart the cache for company_get and domain_get method
#        self.company_get()
        self.pool.get('ir.rule').domain_get()
        return res

    def unlink(self, cursor, user, ids, context=None):
        if 1 in ids:
            raise ExceptOSV('UserError',
                    'You can not remove the root user\n' \
                            'as it is used internally for resources\n' \
                            'created by Tiny ERP ' \
                            '(updates, module installation, ...)')
        return super(User, self).unlink(cursor, user, ids, context=context)

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
        return super(User, self).copy(cursor, user, obj_id, default,
                context=context)
User()


class Group2(Group):

    def __init__(self, pool):
        super(Group2, self).__init__(pool)
        self._columns['users'] = fields.many2many(
            'res.user', 'res_group_user_rel', 'gid', 'uid', 'Users')

Group2()
