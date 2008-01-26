"Request"
from trytond.osv import OSV, fields
import time

class Request(OSV):
    "Request"
    _name = 'res.request'
    _table = 'res_request'
    _description = __doc__

    def _links_get(self, cursor, user, context=None):
        request_link_obj = self.pool.get('res.request.link')
        ids = request_link_obj.search(cursor, user, [])
        request_links = request_link_obj.browse(cursor, user, ids,
                context=context)
        return [(x.object, x.name) for x in request_links]

    _columns = {
        'create_date': fields.DateTime('Created date', readonly=True),
        'name': fields.Char('Subject', states={
            'waiting': [('readonly', True)],
            'active': [('readonly', True)],
            'closed': [('readonly', True)],
            }, required=True, size=128),
        'active': fields.Boolean('Active'),
        'priority': fields.Selection([
            ('0', 'Low'),
            ('1', 'Normal'),
            ('2', 'High'),
            ], 'Priority', states={
                'waiting': [('readonly', True)],
                'closed': [('readonly', True)],
                }, required=True),
        'act_from': fields.Many2One('res.user', 'From', required=True,
            readonly=True, states={
                'closed': [('readonly', True)],
                }),
        'act_to': fields.Many2One('res.user', 'To', required=True,
            states={
                'waiting': [('readonly', True)],
                'closed': [('readonly', True)],
                }),
        'body': fields.Text('Request', states={
            'waiting': [('readonly', True)],
            'closed': [('readonly', True)],
            }),
        'date_sent': fields.DateTime('Date', readonly=True),
        'trigger_date': fields.DateTime('Trigger Date', states={
            'waiting': [('readonly', True)],
            'closed': [('readonly', True)],
            }),
#        'ref_partner_id': fields.Many2One('res.partner', 'Partner Ref.',
#            states={
#                'closed': [('readonly', True)],
#                }),
        #TODO: use one2many instead limit number of reference
        'ref_doc1': fields.Reference('Document Ref 1', selection=_links_get,
            size=128, states={
                'closed': [('readonly', True)],
                }),
        'ref_doc2': fields.Reference('Document Ref 2', selection=_links_get,
            size=128, states={
                'closed': [('readonly', True)],
                }),
        'state': fields.Selection([
            ('draft', 'draft'),
            ('waiting', 'waiting'),
            ('active', 'active'),
            ('closed', 'closed'),
            ], 'State', required=True, readonly=True),
        'history': fields.One2Many('res.request.history', 'req_id',
                'History', readonly=True),
    }
    _defaults = {
        'act_from': lambda obj, cursor, user, context: user,
        'state': lambda *a: 'draft',
        'active': lambda *a: True,
        'priority': lambda *a: '1',
    }
    _order = 'priority DESC, trigger_date, create_date DESC'

    def request_send(self, cursor, user, ids, context=None):
        request_history_obj = self.pool.get('res.request.history')
        for request in self.browse(cursor, user, ids, context=context):
            values = {
                'req_id': request.id,
                'act_from': request.act_from.id,
                'act_to': request.act_to.id,
                'body': request.body,
            }
            if values['body'] and len(values['body']) > 128:
                values['name'] = values['body'][:125] + '...'
            else:
                values['name'] = values['body'] or '/'
            request_history_obj.create(cursor, user, values, context=context)
        self.write(cursor, user, ids, {
            'state': 'waiting',
            'date_send': time.strftime('%Y-%m-%d %H:%M:%S'),
            }, context=context)
        return True

    def request_reply(self, cursor, user, ids, context=None):
        for request in self.browse(cursor, user, ids, context=context):
            self.write(cursor, user, request.id, {
                'state': 'active',
                'act_from': user,
                'act_to': request.act_from.id,
                'trigger_date': False,
                'body': '',
                }, context=context)
        return True

    def request_close(self, cursor, user, ids, context=None):
        self.write(cursor, user, ids, {'state': 'closed', 'active': False})
        return True

    def request_get(self, cursor, user):
        cursor.execute('SELECT id FROM res_request ' \
                'WHERE act_to = %d ' \
                    'AND (trigger_date <= %s OR trigger_date IS NULL) ' \
                    'AND active = True', (user, time.strftime('%Y-%m-%d')))
        ids = [x[0] for x in cursor.fetchall()]
        cursor.execute('SELECT id FROM res_request ' \
                'WHERE act_from = %d AND (act_to <> %d) ' \
                    'AND (trigger_date <= %s OR trigger_date IS NULL) ' \
                    'AND active = True',
                    (user, user, time.strftime('%Y-%m-%d')))
        ids2 = [x[0] for x in cursor.fetchall()]
        return (ids, ids2)

Request()


class RequestLink(OSV):
    "Request link"
    _name = 'res.request.link'
    _description = __doc__
    _columns = {
        'name': fields.Char('Name', size=64, required=True, translate=True),
        'object': fields.Char('Object', size=64, required=True),
        'priority': fields.Integer('Priority'),
    }
    _defaults = {
        'priority': lambda *a: 5,
    }
    _order = 'priority'

RequestLink()


class RequestHistory(OSV):
    "Request history"
    _name = 'res.request.history'
    _description = __doc__
    _columns = {
        'name': fields.Char('Summary', size=128, states={
            'active': [('readonly', True)],
            'waiting': [('readonly', True)],
            }, required=True),
        'req_id': fields.Many2One('res.request', 'Request', required=True,
            ondelete='cascade', select=True),
        'act_from': fields.Many2One('res.user', 'From', required=True,
            readonly=True),
        'act_to': fields.Many2One('res.user', 'To', required=True, states={
            'waiting': [('readonly', True)],
            }),
        'body': fields.Text('Body', states={
            'waiting': [('readonly', True)],
            }),
        'date_sent': fields.DateTime('Date sent', states={
            'waiting': [('readonly', True)],
            }, required=True)
    }
    _defaults = {
        'name': lambda *a: 'NoName',
        'act_from': lambda obj, cursor, user, context: user,
        'act_to': lambda obj, cursor, user, context: user,
        'date_sent': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

RequestHistory()
