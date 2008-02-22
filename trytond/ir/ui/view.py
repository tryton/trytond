"View"
from trytond.osv import fields, OSV
from xml import dom
from difflib import SequenceMatcher


class View(OSV):
    "View"
    _name = 'ir.ui.view'
    _description = __doc__
    _rec_name = 'model'
    _columns = {
        'model': fields.Char('Model', size=64, required=True),
        'priority': fields.Integer('Priority', required=True),
        'type': fields.Selection((
            ('tree','Tree'),
            ('form','Form'),
            ('graph', 'Graph'),
            ('calendar', 'Calendar')), 'View Type', required=True),
        'arch': fields.Text('View Architecture', required=True),
        'inherit': fields.Many2One('ir.ui.view', 'Inherited View'),
        'field_childs': fields.Char('Childs Field',size=64),
        'module': fields.Char('Module', size=128, readonly=True),
    }
    _defaults = {
        'arch': lambda *a: '<?xml version="1.0"?>\n' \
                '<tree title="Unknwown">\n\t<field name="name"/>\n</tree>',
        'priority': lambda *a: 16,
        'module': lambda obj, cursor, user, context: context and context.get('module', '') or '',
    }
    _order = "priority"
    _constraints = [
        ('check_xml', 'Invalid XML for View Architecture!', ['arch'])
    ]

    def check_xml(self, cursor, user, ids):
        "Check XML"
        views = self.browse(cursor, user, ids)
        cursor.execute('SELECT id, name, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name IN ' \
                        '(' + ','.join(['%s' for x in views]) + ')',
                        ('en_US', 'view') + tuple([x.model for x in views]))
        trans_views = {}
        for trans in cursor.dictfetchall():
            trans_views.setdefault(trans['name'], {})
            trans_views[trans['name']][trans['src']] = trans
        model_data_obj = self.pool.get('ir.model.data')
        model_data_ids = model_data_obj.search(cursor, user, [
            ('model', '=', self._name),
            ('db_id', 'in', ids),
            ])
        for view in views:
            try:
                document = dom.minidom.parseString(view.arch)
            except:
                return False
            strings = self._translate_view(document.documentElement)
            view_ids = self.search(cursor, 0, [
                ('model', '=', view.model),
                ('id', '!=', view.id),
                ])
            for view2 in self.browse(cursor, 0, view_ids):
                document = dom.minidom.parseString(view2.arch)
                strings += self._translate_view(document.documentElement)
            if not strings:
                continue
            for string in {}.fromkeys(strings).keys():
                done = False
                if string in trans_views.get(view.model, {}):
                    del trans_views[view.model][string]
                    continue
                for string_trans in trans_views.get(view.model, {}):
                    seqmatch = SequenceMatcher(lambda x: x == ' ',
                            string, string_trans)
                    if seqmatch.ratio() == 1.0:
                        del trans_views[view.model][string_trans]
                        done = True
                        break
                    if seqmatch.ratio() > 0.6:
                        cursor.execute('UPDATE ir_translation ' \
                            'SET src = %s, ' \
                                'fuzzy = True ' \
                            'WHERE name = %s ' \
                                'AND type = %s ' \
                                'AND src = %s',
                            (string, view.model, 'view', string_trans))
                        del trans_views[view.model][string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module)' \
                        'VALUES (%s, %s, %s, %s, %s, %s)',
                        (view.model, 'en_US', 'view', string, '',
                            view.module))
            cursor.execute('DELETE FROM ir_translation ' \
                    'WHERE name = %s ' \
                        'AND type = %s ' \
                        'AND src NOT IN ' \
                            '(' + ','.join(['%s' for x in strings]) + ')',
                    (view.model, 'view') + tuple(strings))
        return True

    def unlink(self, cursor, user, ids, context=None):

        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids, context=context)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get()
            except:
                pass
        res = super(View, self).unlink(cursor, user, ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(View, self).create(cursor, user, vals, context=context)
        if 'model' in vals:
            model = vals['model']
            # Restart the cache
            try:
                self.pool.get(model).fields_view_get()
            except:
                pass
        return res

    def write(self, cursor, user, ids, vals, context=None):

        if isinstance(ids, (int, long)):
            ids = [ids]
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get()
            except:
                pass
        res = super(View, self).write(cursor, user, ids, vals, context=context)
        views = self.browse(cursor, user, ids)
        for view in views:
            # Restart the cache
            try:
                self.pool.get(view.model).fields_view_get()
            except:
                pass
        return res

    def _translate_view(self, document):
        strings = []
        if document.hasAttribute('string'):
            string = document.getAttribute('string')
            if string:
                strings.append(string.encode('utf-8'))
        if document.hasAttribute('sum'):
            string = document.getAttribute('sum')
            if string:
                strings.append(string.encode('utf-8'))
        for child in [x for x in document.childNodes \
                if (x.nodeType == x.ELEMENT_NODE)]:
            strings.extend(self._translate_view(child))
        return strings

View()


class ViewShortcut(OSV):
    "View shortcut"
    _name = 'ir.ui.view_sc'
    _description = __doc__
    _columns = {
        'name': fields.char('Shortcut Name', size=64, required=True),
        'res_id': fields.integer('Resource Ref.', required=True),
        'sequence': fields.integer('Sequence'),
        'user_id': fields.many2one('res.user', 'User Ref.', required=True,
            ondelete='cascade'),
        'resource': fields.char('Resource Name', size=64, required=True)
    }

    def __init__(self, pool):
        super(ViewShortcut, self).__init__(pool)
        if pool:
            self._rpc_allowed = self._rpc_allowed + [
                'get_sc',
            ]

    def get_sc(self, cursor, user, user_id, model='ir.ui.menu', context=None):
        "Provide user's shortcuts"
        ids = self.search(cursor, user, [
            ('user_id','=',user_id),
            ('resource','=',model),
            ], context=context)
        return self.read(cursor, user, ids, ['res_id', 'name'], context=context)

    _order = 'sequence'
    _defaults = {
        'resource': lambda *a: 'ir.ui.menu',
    }

ViewShortcut()
