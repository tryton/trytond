"Workflow"
from trytond.osv import fields, OSV
from trytond.netsvc import LocalService


class Workflow(OSV):
    "Workflow"
    _name = "workflow"
    _table = "wkf"
    _log_access = False
    _description = __doc__
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'osv': fields.char('Resource Model', size=64, required=True),
        'on_create': fields.boolean('On Create'),
        'activities': fields.one2many('workflow.activity', 'wkf_id',
            'Activities'),
    }
    _defaults = {
        'on_create': lambda *a: True
    }

    def write(self, cursor, user, ids, vals, context=None):
        wf_service = LocalService("workflow")
        wf_service.clear_cache(cursor, user)
        return super(Workflow, self).write(cursor, user, ids, vals,
                context=context)

    def create(self, cursor, user, vals, context=None):
        wf_service = LocalService("workflow")
        wf_service.clear_cache(cursor, user)
        return super(Workflow, self).create(cursor, user, vals,
                context=context)

Workflow()


class WorkflowActivity(OSV):
    "Workflow activity"
    _name = "workflow.activity"
    _table = "wkf_activity"
    _log_access = False
    _description = __doc__
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'wkf_id': fields.many2one('workflow', 'Workflow', required=True,
            select=1),
        'split_mode': fields.selection([
            ('XOR', 'Xor'),
            ('OR', 'Or'),
            ('AND', 'And'),
            ], 'Split Mode', size=3, required=True),
        'join_mode': fields.selection([
            ('XOR', 'Xor'),
            ('AND', 'And'),
            ], 'Join Mode', size=3, required=True),
        'kind': fields.selection([
            ('dummy', 'Dummy'),
            ('function', 'Function'),
            ('subflow', 'Subflow'),
            ('stopall', 'Stop All'),
            ], 'Kind', size=64, required=True),
        'action': fields.char('Action', size=64),
        'flow_start': fields.boolean('Flow Start'),
        'flow_stop': fields.boolean('Flow Stop'),
        'subflow_id': fields.many2one('workflow', 'Subflow'),
        'signal_send': fields.char('Signal (subflow.*)', size=32),
        'out_transitions': fields.one2many('workflow.transition', 'act_from',
            'Outgoing transitions'),
        'in_transitions': fields.one2many('workflow.transition', 'act_to',
            'Incoming transitions'),
    }
    _defaults = {
        'kind': lambda *a: 'dummy',
        'join_mode': lambda *a: 'XOR',
        'split_mode': lambda *a: 'XOR',
    }

WorkflowActivity()


class WorkflowTransition(OSV):
    "Workflow transition"
    _table = "wkf_transition"
    _name = "workflow.transition"
    _log_access = False
    _rec_name = 'signal'
    _description = __doc__
    _columns = {
        'trigger_model': fields.char('Trigger Type', size=128),
        'trigger_expr_id': fields.char('Trigger Expr ID', size=128),
        'signal': fields.char('Signal (button Name)', size=64),
        'role_id': fields.many2one('res.role', 'Role Required'),
        'condition': fields.char('Condition', required=True, size=128),
        'act_from': fields.many2one('workflow.activity', 'Source Activity',
            required=True, select=1),
        'act_to': fields.many2one('workflow.activity', 'Destination Activity',
            required=True, select=1),
    }
    _defaults = {
        'condition': lambda *a: 'True',
    }

WorkflowTransition()


class WorkflowInstance(OSV):
    "Workflow instance"
    _table = "wkf_instance"
    _name = "workflow.instance"
    _rec_name = 'res_type'
    _log_access = False
    _description = __doc__
    _columns = {
        'wkf_id': fields.many2one('workflow', 'Workflow', ondelete="cascade"),
        'uid': fields.integer('User ID'),
        'res_id': fields.integer('Resource ID'),
        'res_type': fields.char('Resource Model', size=64),
        'state': fields.char('State', size=32),
    }

    def _auto_init(self, cursor):
        super(WorkflowInstance, self)._auto_init(cursor)
        cursor.execute('SELECT indexname FROM pg_indexes ' \
                'WHERE indexname = ' \
                    '\'wkf_instance_res_id_res_type_state_index\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX ' \
                        'wkf_instance_res_id_res_type_state_index ' \
                    'ON wkf_instance (res_id, res_type, state)')
            cursor.commit()

WorkflowInstance()


class WorkflowWorkitem(OSV):
    "Workflow workitem"
    _table = "wkf_workitem"
    _name = "workflow.workitem"
    _log_access = False
    _rec_name = 'state'
    _description = __doc__
    _columns = {
        'act_id': fields.many2one('workflow.activity', 'Activity',
            required=True, ondelete="cascade"),
        'subflow_id': fields.many2one('workflow.instance', 'Subflow',
            ondelete="cascade"),
        'inst_id': fields.many2one('workflow.instance', 'Instance',
            required=True, ondelete="cascade", select=1),
        'state': fields.char('State', size=64),
    }

WorkflowWorkitem()


class WorkflowTrigger(OSV):
    "Workflow trigger"
    _table = "wkf_triggers"
    _name = "workflow.triggers"
    _log_access = False
    _description = __doc__
    _columns = {
        'res_id': fields.integer('Resource ID', size=128),
        'model': fields.char('Model', size=128),
        'instance_id': fields.many2one('workflow.instance',
            'Destination Instance', ondelete="cascade"),
        'workitem_id': fields.many2one('workflow.workitem', 'Workitem',
            required=True, ondelete="cascade"),
    }

    def _auto_init(self, cursor):
        super(WorkflowTrigger, self)._auto_init(cursor)
        cursor.execute('SELECT indexname FROM pg_indexes ' \
                'WHERE indexname = \'wkf_triggers_res_id_model_index\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX wkf_triggers_res_id_model_index ' \
                    'ON wkf_triggers (res_id, model)')
            cursor.commit()

WorkflowTrigger()
