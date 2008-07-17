#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Workflow"
import os
from trytond.osv import fields, OSV
from trytond.netsvc import LocalService
from trytond.report import Report
from trytond.tools import exec_command_pipe
import base64


class Workflow(OSV):
    "Workflow"
    _name = "workflow"
    _table = "wkf"
    _log_access = False
    _description = __doc__
    name = fields.Char('Name', size=64, required=True)
    osv = fields.Char('Resource Model', size=64, required=True)
    on_create = fields.Boolean('On Create')
    activities = fields.One2Many('workflow.activity', 'workflow',
       'Activities')

    def default_on_create(self, cursor, user, context=None):
        return 1

    def write(self, cursor, user, ids, vals, context=None):
        wf_service = LocalService("workflow")
        wf_service.clear_cache(cursor)
        return super(Workflow, self).write(cursor, user, ids, vals,
                context=context)

    def create(self, cursor, user, vals, context=None):
        wf_service = LocalService("workflow")
        wf_service.clear_cache(cursor)
        return super(Workflow, self).create(cursor, user, vals,
                context=context)

Workflow()


class WorkflowActivity(OSV):
    "Workflow activity"
    _name = "workflow.activity"
    _table = "wkf_activity"
    _log_access = False
    _description = __doc__
    name = fields.Char('Name', size=64, required=True)
    workflow = fields.Many2One('workflow', 'Workflow', required=True,
       select=1, ondelete='cascade')
    split_mode = fields.Selection([
       ('XOR', 'Xor'),
       ('OR', 'Or'),
       ('AND', 'And'),
       ], 'Split Mode', size=3, required=True)
    join_mode = fields.Selection([
       ('XOR', 'Xor'),
       ('AND', 'And'),
       ], 'Join Mode', size=3, required=True)
    kind = fields.Selection([
       ('dummy', 'Dummy'),
       ('function', 'Function'),
       ('subflow', 'Subflow'),
       ('stopall', 'Stop All'),
       ], 'Kind', size=64, required=True)
    action = fields.Char('Action', size=None)
    flow_start = fields.Boolean('Flow Start')
    flow_stop = fields.Boolean('Flow Stop')
    subflow =  fields.Many2One('workflow', 'Subflow')
    signal_send = fields.Char('Signal (subflow.*)', size=32)
    out_transitions = fields.One2Many('workflow.transition', 'act_from',
       'Outgoing transitions')
    in_transitions = fields.One2Many('workflow.transition', 'act_to',
       'Incoming transitions')

    def default_kind(self, cursor, user, context=None):
        return 'dummy'

    def default_join_mode(self, cursor, user, context=None):
        return 'XOR'

    def default_split_mode(self, cursor, user, context=None):
        return 'XOR'

WorkflowActivity()


class WorkflowTransition(OSV):
    "Workflow transition"
    _table = "wkf_transition"
    _name = "workflow.transition"
    _log_access = False
    _rec_name = 'signal'
    _description = __doc__
    trigger_model = fields.Char('Trigger Type', size=128)
    trigger_expr_id = fields.Char('Trigger Expr ID', size=128)
    signal = fields.Char('Signal (button Name)', size=64)
    group = fields.Many2One('res.group', 'Group Required')
    condition = fields.Char('Condition', required=True, size=128)
    act_from = fields.Many2One('workflow.activity', 'Source Activity',
       required=True, select=1, ondelete='cascade')
    act_to = fields.Many2One('workflow.activity', 'Destination Activity',
       required=True, select=1, ondelete='cascade')

    def default_condition(self, cursor, user, context=None):
        return 'True'

WorkflowTransition()


class WorkflowInstance(OSV):
    "Workflow instance"
    _table = "wkf_instance"
    _name = "workflow.instance"
    _rec_name = 'res_type'
    _log_access = False
    _description = __doc__
    workflow = fields.Many2One('workflow', 'Workflow', ondelete="restrict")
    uid = fields.Integer('User ID')
    res_id = fields.Integer('Resource ID')
    res_type = fields.Char('Resource Model', size=64)
    state = fields.Char('State', size=32)

    def _auto_init(self, cursor, module_name):
        super(WorkflowInstance, self)._auto_init(cursor, module_name)
        cursor.execute('SELECT indexname FROM pg_indexes ' \
                'WHERE indexname = ' \
                    '\'wkf_instance_res_id_res_type_state_index\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX ' \
                        'wkf_instance_res_id_res_type_state_index ' \
                    'ON wkf_instance (res_id, res_type, state)')

WorkflowInstance()


class WorkflowWorkitem(OSV):
    "Workflow workitem"
    _table = "wkf_workitem"
    _name = "workflow.workitem"
    _log_access = False
    _rec_name = 'state'
    _description = __doc__
    activity = fields.Many2One('workflow.activity', 'Activity',
       required=True, ondelete="cascade")
    subflow = fields.Many2One('workflow.instance', 'Subflow',
       ondelete="cascade")
    instance = fields.Many2One('workflow.instance', 'Instance',
       required=True, ondelete="cascade", select=1)
    state = fields.Char('State', size=64)

WorkflowWorkitem()


class WorkflowTrigger(OSV):
    "Workflow trigger"
    _table = "wkf_trigger"
    _name = "workflow.trigger"
    _log_access = False
    _description = __doc__
    res_id = fields.Integer('Resource ID', size=128)
    model = fields.Char('Model', size=128)
    instance = fields.Many2One('workflow.instance',
       'Destination Instance', ondelete="cascade")
    workitem = fields.Many2One('workflow.workitem', 'Workitem',
       required=True, ondelete="cascade")

    def _auto_init(self, cursor, module_name):
        super(WorkflowTrigger, self)._auto_init(cursor, module_name)
        cursor.execute('SELECT indexname FROM pg_indexes ' \
                'WHERE indexname = \'wkf_trigger_res_id_model_index\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX wkf_trigger_res_id_model_index ' \
                    'ON wkf_trigger (res_id, model)')
            cursor.commit()

WorkflowTrigger()


class InstanceGraph(Report):
    _name = 'workflow.instance.graph'

    def execute(self, cursor, user, ids, datas, context=None):
        import pydot
        lang_obj = self.pool.get('ir.lang')
        workflow_obj = self.pool.get('workflow')
        instance_obj = self.pool.get('workflow.instance')

        if context is None:
            context = {}

        lang_id = lang_obj.search(cursor, user, [
            ('code', '=', context.get('language', 'en_US')),
            ], limit=1, context=context)[0]
        lang = lang_obj.browse(cursor, user, lang_id, context=context)

        workflow_id = workflow_obj.search(cursor, user, [
            ('osv', '=', datas['model']),
            ], limit=1, context=context)
        if not workflow_id:
            raise Exception('Error', 'No workflow defined!')
        workflow_id = workflow_id[0]
        workflow = workflow_obj.browse(cursor, user, workflow_id,
                context=context)
        instance_id = instance_obj.search(cursor, user, [
            ('res_id', '=', datas['id']),
            ('workflow', '=', workflow.id),
            ], order=[('id', 'DESC')], limit=1, context=context)
        if not instance_id:
            raise Exception('Error', 'No workflow instance defined!')
        instance_id = instance_id[0]

        title = "Workflow: %s OSV: %s" % (workflow.name, workflow.osv)
        if pydot.__version__ == '1.0.2':
            # version 1.0.2 doesn't quote correctly label on Dot object
            title = '"' + title + '"'
        graph = pydot.Dot(fontsize='16',
                label=title)
        graph.set('center', '1')
        graph.set('ratio', 'auto')
        if lang.direction == 'ltr':
            if hasattr(graph, 'set_rankdir'):
                graph.set_rankdir('LR')
            else:
                graph.set('rankdir', 'LR')
        else:
            if hasattr(graph, 'set_rankdir'):
                graph.set_rankdir('RL')
            else:
                graph.set('rankdir', 'RL')
        self.graph_instance_get(cursor, user, graph, instance_id,
                datas.get('nested', False), context=context)
        data = graph.create(prog='dot', format='png')
        return ('png', base64.encodestring(data), False)

    def graph_instance_get(self, cursor, user, graph, instance_id, nested=False,
            context=None):
        instance_obj = self.pool.get('workflow.instance')
        instance = instance_obj.browse(cursor, user, instance_id,
                context=context)
        self.graph_get(cursor, user, graph, instance.workflow.id, nested,
                self.workitem_get(cursor, user, instance.id, context=context),
                context=context)

    def workitem_get(self, cursor, user, instance_id, context=None):
        res = {}
        workitem_obj = self.pool.get('workflow.workitem')
        workitem_ids = workitem_obj.search(cursor, user, [
            ('instance', '=', instance_id),
            ], context=context)
        workitems = workitem_obj.browse(cursor, user, workitem_ids,
                context=context)
        for workitem in workitems:
            res.setdefault(workitem.activity.id, 0)
            res[workitem.activity.id] += 1
            if workitem.subflow:
                res.update(self.workitem_get(cursor, user,
                    workitem.subflow.id, context=context))
        return res

    def graph_get(self, cursor, user, graph, workflow_id, nested=False,
            workitem=None, context=None):
        import pydot
        if workitem is None:
            workitem = {}
        activity_obj = self.pool.get('workflow.activity')
        workflow_obj = self.pool.get('workflow')
        transition_obj = self.pool.get('workflow.transition')
        activity_ids = activity_obj.search(cursor, user, [
            ('workflow', '=', workflow_id),
            ], context=context)
        id2activities = {}
        actfrom = {}
        actto = {}
        activities = activity_obj.browse(cursor, user, activity_ids,
                context=context)
        start = 0
        stop = {}
        for activity in activities:
            if activity.flow_start:
                start = activity.id
            if activity.flow_stop:
                stop['subflow.' + activity.name] =  activity.id
            id2activities[activity.id] = activity
            if activity.subflow and nested:
                workflow = workflow_obj.browse(cursor, user,
                        activity.subflow.id, context=context)
                subgraph = pydot.Cluster('subflow' + str(workflow.id),
                        fontsize='12', label="Subflow: " + activity.name + \
                                '\\nOSV: ' + workflow.osv)
                (substart, substop) = self.graph_get(cursor, user,
                        subgraph, workflow.id, nested, workitem,
                        context=context)
                graph.add_subgraph(subgraph)
                actfrom[activity.id] = substart
                actto[activity.id] = substop
            else:
                args = {}
                if activity.flow_start or activity.flow_stop:
                    args['style'] = 'filled'
                    args['color'] = 'lightgrey'
                args['label'] = activity.name
                if activity.subflow:
                    args['shape'] = 'box'
                if activity.id in workitem:
                    args['label'] += '\\nx ' + str(workitem[activity.id])
                    args['color'] = 'red'
                graph.add_node(pydot.Node(activity.id, **args))
                actfrom[activity.id] = (activity.id, {})
                actto[activity.id] = (activity.id, {})
        transition_ids = transition_obj.search(cursor, user, [
            ('act_from', 'in', [x.id for x in activities]),
            ], context=context)
        transitions = transition_obj.browse(cursor, user, transition_ids,
                context=context)
        for transition in transitions:
            args = {}
            args['label'] = str(transition.condition).replace(' or ',
                    '\\nor ').replace(' and ', '\\nand ')
            if transition.signal:
                args['label'] += '\\n' + str(transition.signal)
                args['style'] = 'bold'
            if id2activities[transition.act_from.id].split_mode == 'AND':
                args['arrowtail'] = 'box'
            elif id2activities[transition.act_from.id].split_mode == 'OR':
                args['arrowtail'] = 'inv'
            if id2activities[transition.act_to.id].join_mode == 'AND':
                args['arrowhead'] = 'crow'

            activity_from = actfrom[transition.act_from.id][1].get(
                    transition.signal, actfrom[transition.act_from.id][0])
            activity_to = actto[transition.act_to.id][1].get(
                    transition.signal, actto[transition.act_to.id][0])
            graph.add_edge(pydot.Edge(str(activity_from), str(activity_to),
                fontsize='10', **args))
        return ((start, {}), (stop.values()[0], stop))

InstanceGraph()
