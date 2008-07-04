#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Request"
from trytond.osv import OSV, fields
import time

class Request(OSV):
    "Request"
    _name = 'res.request'
    _table = 'res_request'
    _description = __doc__
    create_date = fields.DateTime('Created date', readonly=True)
    name = fields.Char('Subject', states={
       'readonly': "state in ('waiting', 'active', 'closed')",
       }, required=True)
    active = fields.Boolean('Active')
    priority = fields.Selection([
       ('0', 'Low'),
       ('1', 'Normal'),
       ('2', 'High'),
       ], 'Priority', states={
           'readonly': "state in ('waiting', 'closed')",
           }, required=True)
    act_from = fields.Many2One('res.user', 'From', required=True,
       readonly=True, states={
           'readonly': "state == 'closed'",
           })
    act_to = fields.Many2One('res.user', 'To', required=True,
       states={
           'readonly': "state in ('waiting', 'closed')",
           })
    body = fields.Text('Request', states={
       'readonly': "state in ('waiting', 'closed')",
       })
    date_sent = fields.DateTime('Date', readonly=True)
    trigger_date = fields.DateTime('Trigger Date', states={
       'readonly': "state in ('waiting', 'closed')",
       })
#   'ref_partner_id': fields.Many2One('res.partner', 'Partner Ref.',
#       states={
#           'closed': [('readonly', True)],
#           })
#    TODO: use one2many instead limit number of reference
    ref_doc1 = fields.Reference('Document Ref 1', selection='links_get',
            states={
                'readonly': "state == 'closed'",
            })
    ref_doc2 = fields.Reference('Document Ref 2', selection='links_get',
            states={
                'readonly': "state == 'closed'",
            })
    state = fields.Selection([
        ('draft', 'draft'),
        ('waiting', 'waiting'),
        ('active', 'active'),
        ('closed', 'closed'),
        ], 'State', required=True, readonly=True)
    history = fields.One2Many('res.request.history', 'request',
           'History', readonly=True)

    def default_act_from(self, cursor, user, context=None):
        return user

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_active(self, cursor, user, context=None):
        return 1

    def default_priority(self, cursor, user, context=None):
        return '1'

    def __init__(self):
        super(Request, self).__init__()
        self._rpc_allowed += [
            'request_send',
            'request_reply',
            'request_close',
            'request_get',
        ]
        self._order.insert(0, ('priority', 'DESC'))
        self._order.insert(1, ('trigger_date', 'ASC'))
        self._order.insert(2, ('create_date', 'DESC'))

    def links_get(self, cursor, user, context=None):
        request_link_obj = self.pool.get('res.request.link')
        ids = request_link_obj.search(cursor, user, [])
        request_links = request_link_obj.browse(cursor, user, ids,
                context=context)
        return [(x.object, x.name) for x in request_links]

    def request_send(self, cursor, user, ids, context=None):
        request_history_obj = self.pool.get('res.request.history')
        for request in self.browse(cursor, user, ids, context=context):
            values = {
                'request': request.id,
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
                'WHERE act_to = %s ' \
                    'AND (trigger_date <= %s OR trigger_date IS NULL) ' \
                    'AND active = True', (user, time.strftime('%Y-%m-%d')))
        ids = [x[0] for x in cursor.fetchall()]
        cursor.execute('SELECT id FROM res_request ' \
                'WHERE act_from = %s AND (act_to <> %s) ' \
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
    name = fields.Char('Name', required=True, translate=True)
    object = fields.Char('Object', required=True)
    priority = fields.Integer('Priority')

    def __init__(self):
        super(RequestLink, self).__init__()
        self._order.insert(0, ('priority', 'ASC'))

    def default_priority(self, cursor, user, context=None):
        return 5

RequestLink()


class RequestHistory(OSV):
    "Request history"
    _name = 'res.request.history'
    _description = __doc__
    name = fields.Char('Summary', required=True)
    request = fields.Many2One('res.request', 'Request', required=True,
       ondelete='cascade', select=True)
    act_from = fields.Many2One('res.user', 'From', required=True,
       readonly=True)
    act_to = fields.Many2One('res.user', 'To', required=True)
    body = fields.Text('Body')
    date_sent = fields.DateTime('Date sent', required=True)

    def default_name(self, cursor, user, context=None):
        return 'No Name'

    def default_act_from(self, cursor, user, context=None):
        return user

    def default_act_to(self, cursor, user, context=None):
        return user

    def default_date_sent(self, cursor, user, context=None):
        return time.strftime('%Y-%m-%d %H:%M:%S')

RequestHistory()
