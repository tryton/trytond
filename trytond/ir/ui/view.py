"View"
from trytond.osv import fields, OSV
from xml import dom


class View(OSV):
    "View"
    _name = 'ir.ui.view'
    _description = __doc__
    _columns = {
        'name': fields.char('View Name',size=64,  required=True),
        'model': fields.char('Model', size=64, required=True),
        'priority': fields.integer('Priority', required=True),
        'type': fields.selection((
            ('tree','Tree'),
            ('form','Form'),
            ('graph', 'Graph'),
            ('calendar', 'Calendar')), 'View Type', required=True),
        'arch': fields.text('View Architecture', required=True),
        'inherit_id': fields.many2one('ir.ui.view', 'Inherited View'),
        'field_parent': fields.char('Childs Field',size=64)
    }
    _defaults = {
        'arch': lambda *a: '<?xml version="1.0"?>\n' \
                '<tree title="Unknwown">\n\t<field name="name"/>\n</tree>',
        'priority': lambda *a: 16,
    }
    _order = "priority"

    def _check_xml(self, cursor, user, ids):
        "Check XML"
        cursor.execute('SELECT arch FROM ir_ui_view ' \
                'WHERE id IN (' + ','.join([str(x) for x in ids]) + ')')
        for row in cursor.fetchall():
            try:
                dom.minidom.parseString(row[0])
            except:
                return False
        return True

    _constraints = [
        (_check_xml, 'Invalid XML for View Architecture!', ['arch'])
    ]

    def unlink(self, cursor, user, ids, context=None):
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
