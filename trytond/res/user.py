"User"
import time
from xml import dom
from xml.dom import minidom
from trytond.osv import fields, OSV, ExceptOSV
#from trytond.tools import Cache


class Group(OSV):
    "Group"
    _name = "res.group"
    _description = __doc__
    _columns = {
        'name': fields.Char('Group Name', size=64, required=True),
        'model_access': fields.One2Many('ir.model.access', 'group',
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
        res = super(Group, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method
        self.pool.get('ir.rule').domain_get()
        return res

Group()


class User(OSV):
    "User"
    _name = "res.user"
    _description = __doc__
    _columns = {
        'name': fields.Char('Name', size=64, required=True, select=1),
        'login': fields.Char('Login', size=64, required=True),
        'password': fields.Char('Password', size=64),
        'signature': fields.Text('Signature', size=64),
        #'address_id': fields.Many2One('res.partner.address', 'Address'),
        'active': fields.Boolean('Active'),
        'action': fields.Many2One('ir.action', 'Home Action'),
        'menu': fields.Many2One('ir.action', 'Menu Action'),
        'groups': fields.Many2Many('res.group', 'res_group_user_rel',
            'uid', 'gid', 'Groups'),
        'rule_groups': fields.Many2Many('ir.rule.group', 'user_rule_group_rel',
            'user_id', 'rule_group_id', 'Rules',
            domain="[('global', '<>', True)]"),
        'language': fields.Selection('languages', 'Language'),
        'timezone': fields.Selection('timezones', 'Timezone'),
    }
    _sql_constraints = [
        ('login_key', 'UNIQUE (login)',
            'You can not have two users with the same login!')
    ]
    _defaults = {
        'password' : lambda *a: '',
        'active' : lambda *a: 1,
        'language': lambda *a: 'en_US',
        'timezone': lambda *a: time.tzname[0],
    }
    _preferences_fields = [
        'name',
        'password',
        'signature',
        'menu',
        'action',
    ]
    _context_fields = [
        'language',
        'timezone',
        'groups',
    ]

    def __init__(self, pool):
        super(User, self).__init__(pool)
        if pool:
            self._rpc_allowed = self._rpc_allowed + [
                'get_preferences',
                'set_preferences',
                'get_preferences_fields_view',
                'languages',
                'timezones',
            ]

    def _convert_vals(self, cursor, user, vals, context=None):
        vals = vals.copy()
        action_obj = self.pool.get('ir.action')
        if 'action' in vals:
            vals['action'] = action_obj.get_action_id(cursor, user,
                    vals['action'], context=context)
        if 'menu' in vals:
            vals['menu'] = action_obj.get_action_id(cursor, user,
                    vals['menu'], context=context)
        return vals

    def create(self, cursor, user, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        return super(User, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        vals = self._convert_vals(cursor, user, vals, context=context)
        res = super(User, self).write(cursor, user, ids, vals, context=context)
        # Restart the cache for domain_get method
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

    def get_preferences(self, cursor, user, context_only=False, context=None):
        res = {}
        user = self.browse(cursor, 0, user, context=context)
        if context_only:
            fields = self._context_fields
        else:
            fields = self._preferences_fields + self._context_fields
        for field in fields:
            if self._columns[field]._type in ('many2one', 'one2one'):
                res[field] = user[field].id
            elif self._columns[field]._type in ('one2many', 'many2many'):
                res[field] = [x.id for x in user[field]]
            else:
                res[field] = user[field]
        return res

    def set_preferences(self, cursor, user, values, context=None):
        values_clean = values.copy()
        fields = self._preferences_fields + self._context_fields
        for field in values:
            if field not in fields or field == 'groups':
                del values_clean[field]
        self.write(cursor, 1, user, values_clean, context=context)

    def get_preferences_fields_view(self, cursor, user, context=None):
        res = {}
        fields = self.fields_get(cursor, user,
                fields_names=self._preferences_fields + self._context_fields,
                context=context)

        xml = '<?xml version="1.0" encoding="utf-8"?>' \
                '<form string="%s" col="2">' % (self._description,)
        for field in fields:
            xml += '<label name="%s"/><field name="%s"/>' % (field, field)
        xml += '</form>'
        doc = dom.minidom.parseString(xml)
        arch, fields = self._view_look_dom_arch(cursor,
                user, doc, context=context)
        for field in fields:
            if field not in ('groups'):
                fields[field]['readonly'] = False
            else:
                fields[field]['readonly'] = True
        res['arch'] = arch
        res['fields'] = fields
        return res

    def languages(self, cursor, user, context=None):
        lang_obj = self.pool.get('ir.lang')
        lang_ids = lang_obj.search(cursor, user, [], context=context)
        res = []
        for lang in lang_obj.browse(cursor, user, lang_ids, context=context):
            res.append([lang.code, lang.name])
        return res

    def timezones(self, cursor, user, context=None):
        try:
            import pytz
            res = [[x, x] for x in pytz.all_timezones]
        except ImportError:
            res = [[time.tzname[0], time.tzname[0]]]
        return res

User()


class Group2(Group):

    def __init__(self, pool):
        super(Group2, self).__init__(pool)
        if pool:
            self._columns['users'] = fields.many2many(
                'res.user', 'res_group_user_rel', 'gid', 'uid', 'Users')

Group2()
