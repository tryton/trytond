"UI menu"
from trytond.osv import fields, OSV

def one_in(i, j):
    """Check the presence of an element of setA in setB
    """
    for k in i:
        if k in j:
            return True
    return False

ICONS = [(x, x) for x in [
    'STOCK_ABOUT',
    'STOCK_ADD',
    'STOCK_APPLY',
    'STOCK_BOLD',
    'STOCK_CANCEL',
    'STOCK_CDROM',
    'STOCK_CLEAR',
    'STOCK_CLOSE',
    'STOCK_COLOR_PICKER',
    'STOCK_CONNECT',
    'STOCK_CONVERT',
    'STOCK_COPY',
    'STOCK_CUT',
    'STOCK_DELETE',
    'STOCK_DIALOG_AUTHENTICATION',
    'STOCK_DIALOG_ERROR',
    'STOCK_DIALOG_INFO',
    'STOCK_DIALOG_QUESTION',
    'STOCK_DIALOG_WARNING',
    'STOCK_DIRECTORY',
    'STOCK_DISCONNECT',
    'STOCK_DND',
    'STOCK_DND_MULTIPLE',
    'STOCK_EDIT',
    'STOCK_EXECUTE',
    'STOCK_FILE',
    'STOCK_FIND',
    'STOCK_FIND_AND_REPLACE',
    'STOCK_FLOPPY',
    'STOCK_GOTO_BOTTOM',
    'STOCK_GOTO_FIRST',
    'STOCK_GOTO_LAST',
    'STOCK_GOTO_TOP',
    'STOCK_GO_BACK',
    'STOCK_GO_DOWN',
    'STOCK_GO_FORWARD',
    'STOCK_GO_UP',
    'STOCK_HARDDISK',
    'STOCK_HELP',
    'STOCK_HOME',
    'STOCK_INDENT',
    'STOCK_INDEX',
    'STOCK_ITALIC',
    'STOCK_JUMP_TO',
    'STOCK_JUSTIFY_CENTER',
    'STOCK_JUSTIFY_FILL',
    'STOCK_JUSTIFY_LEFT',
    'STOCK_JUSTIFY_RIGHT',
    'STOCK_MEDIA_FORWARD',
    'STOCK_MEDIA_NEXT',
    'STOCK_MEDIA_PAUSE',
    'STOCK_MEDIA_PLAY',
    'STOCK_MEDIA_PREVIOUS',
    'STOCK_MEDIA_RECORD',
    'STOCK_MEDIA_REWIND',
    'STOCK_MEDIA_STOP',
    'STOCK_MISSING_IMAGE',
    'STOCK_NETWORK',
    'STOCK_NEW',
    'STOCK_NO',
    'STOCK_OK',
    'STOCK_OPEN',
    'STOCK_PASTE',
    'STOCK_PREFERENCES',
    'STOCK_PRINT',
    'STOCK_PRINT_PREVIEW',
    'STOCK_PROPERTIES',
    'STOCK_QUIT',
    'STOCK_REDO',
    'STOCK_REFRESH',
    'STOCK_REMOVE',
    'STOCK_REVERT_TO_SAVED',
    'STOCK_SAVE',
    'STOCK_SAVE_AS',
    'STOCK_SELECT_COLOR',
    'STOCK_SELECT_FONT',
    'STOCK_SORT_ASCENDING',
    'STOCK_SORT_DESCENDING',
    'STOCK_SPELL_CHECK',
    'STOCK_STOP',
    'STOCK_STRIKETHROUGH',
    'STOCK_UNDELETE',
    'STOCK_UNDERLINE',
    'STOCK_UNDO',
    'STOCK_UNINDENT',
    'STOCK_YES',
    'STOCK_ZOOM_100',
    'STOCK_ZOOM_FIT',
    'STOCK_ZOOM_IN',
    'STOCK_ZOOM_OUT',
]]


class Many2ManyUniq(fields.Many2Many):

    def set(self, cursor, obj, obj_id, name, values, user=None, context=None):
        if not values:
            return
        val = values[:]
        for act in values:
            if act[0] == 4:
                cursor.execute('SELECT * FROM ' + self._rel + ' ' \
                        'WHERE ' + self._id1 + ' = %d ' \
                            'AND ' + self._id2 + ' = %d',
                        (obj_id, act[1]))
                if cursor.fetchall():
                    val.remove(act)
        return super(Many2ManyUniq, self).set(cursor, obj, obj_id, name, val,
                user=user, context=context)


class UIMenu(OSV):
    "UI menu"
    _name = 'ir.ui.menu'
    _description = __doc__
    name = fields.Char('Menu', size=64, required=True, translate=True)
    sequence = fields.Integer('Sequence')
    childs = fields.One2Many('ir.ui.menu', 'parent','Childs')
    parent = fields.Many2One('ir.ui.menu', 'Parent Menu', select=1)
    groups = Many2ManyUniq('res.group', 'ir_ui_menu_group_rel',
       'menu_id', 'gid', 'Groups')
    complete_name = fields.Function('get_full_name',
       string='Complete Name', type='char', size=128)
    icon = fields.selection(ICONS, 'Icon', size=64)
    action = fields.Function('get_action', fnct_inv='action_inv',
       type='reference', string='Action',
       selection=[
           ('ir.action.report', 'ir.action.report'),
           ('ir.action.act_window', 'ir.action.act_window'),
           ('ir.action.wizard', 'ir.action.wizard'),
           ('ir.action.url', 'ir.action.url'),
           ])
    _order = "sequence, id"

    def default_icon(self, cursor, user, context=None):
        return 'STOCK_OPEN'

    def default_sequence(self, cursor, user, context=None):
        return 10

    def get_full_name(self, cursor, user, ids, name, args, context):
        res = {}
        for menu in self.browse(cursor, user, ids):
            res[menu.id] = self._get_one_full_name(menu)
        return res

    def _get_one_full_name(self, menu, level=6):
        if level <= 0:
            return '...'
        if menu.parent:
            parent_path = self._get_one_full_name(menu.parent, level-1) + "/"
        else:
            parent_path = ''
        return parent_path + menu.name

    def get_action(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for menu_id in ids:
            res[menu_id] = False
        action_keyword_obj = self.pool.get('ir.action.keyword')
        action_keyword_ids = action_keyword_obj.search(cursor, user, [
            ('keyword', '=', 'tree_open'),
            ('model', 'in', [self._name + ',' + str(x) for x in ids]),
            ], context=context)
        for action_keyword in action_keyword_obj.browse(cursor, user,
                action_keyword_ids, context=context):
            model_id = int(action_keyword.model.split(',')[1])
            action_obj = self.pool.get(action_keyword.action.type)
            action_id = action_obj.search(cursor, user, [
                ('action', '=', action_keyword.action.id),
                ], context=context)
            if action_id:
                action_id = action_id[0]
            else:
                action_id = 0
            res[model_id] = action_keyword.action.type + \
                    ',' + str(action_id)
        return res

    def action_inv(self, cursor, user, menu_id, name, value, arg,
            context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        if 'read_delta' in ctx:
            del ctx['read_delta']
        action_keyword_obj = self.pool.get('ir.action.keyword')
        action_keyword_ids = action_keyword_obj.search(cursor, user, [
            ('keyword', '=', 'tree_open'),
            ('model', '=', self._name + ',' + str(menu_id)),
            ], context=context)
        if action_keyword_ids:
            action_keyword_obj.unlink(cursor, user, action_keyword_ids,
                    context=ctx)
        action_type, action_id = value.split(',')
        action_obj = self.pool.get(action_type)
        action = action_obj.browse(cursor, user, int(action_id),
                context=context)
        action_keyword_obj.create(cursor, user, {
            'keyword': 'tree_open',
            'model': self._name + ',' + str(menu_id),
            'action': action.action.id,
            }, context=ctx)

    def create(self, cursor, user, vals, context=None):
        new_id = super(UIMenu, self).create(cursor, user, vals,
                context=context)
        if 'module' in context:
            cursor.execute('INSERT INTO ir_translation ' \
                    '(name, lang, type, src, res_id, value, module) ' \
                    'VALUES (%s, %s, %s, %s, %d, %s, %s)',
                    ('ir.ui.menu,name', 'en_US', 'model', vals['name'],
                        new_id, '', context.get('module')))
        return new_id

UIMenu()
