"Workflow report"
import os
from trytond.netsvc import Logger, LOG_ERROR, LOG_WARNING
#import report
from trytond.tools import exec_command_pipe


def graph_get(cursor, graph, wkf_id, nested=False, workitem=None):
    import pydot
    if workitem is None:
        workitem = {}
    cursor.execute('SELECT * FROM wkf_activity WHERE wkf_id = %d', (wkf_id,))
    nodes = cursor.dictfetchall()
    activities = {}
    actfrom = {}
    actto = {}
    for node in nodes:
        activities[node['id']] = node
        if node['subflow_id'] and nested:
            cursor.execute('SELECT * FROM wkf WHERE id = %d',
                    (node['subflow_id'],))
            wkfinfo = cursor.dictfetchone()
            graph2 = pydot.Cluster('subflow' + str(node['subflow_id']),
                    fontsize=12, label = "Subflow: " + node['name'] + \
                            '\\nOSV: ' + wkfinfo['osv'])
            (sub1, sub2) = graph_get(cursor, graph2, node['subflow_id'],
                    nested, workitem)
            graph.add_subgraph(graph2)
            actfrom[node['id']] = sub2
            actto[node['id']] = sub1
        else:
            args = {}
            if node['flow_start'] or node['flow_stop']:
                args['style'] = 'filled'
                args['color'] = 'lightgrey'
            args['label'] = node['name']
            if node['subflow_id']:
                args['shape'] = 'box'
            if node['id'] in workitem:
                args['label'] += '\\nx ' + str(workitem[node['id']])
                args['color'] = "red"
            graph.add_node(pydot.Node(node['id'], **args))
            actfrom[node['id']] = (node['id'], {})
            actto[node['id']] = (node['id'], {})
    cursor.execute('SELECT * FROM wkf_transition ' \
            'WHERE act_from IN (' + ','.join([str(x['id']) for x in nodes]) + \
                ')')
    transitions = cursor.dictfetchall()
    for transition in transitions:
        args = {}
        args['label'] = str(transition['condition']).replace(' or ',
                '\\nor ').replace(' and ', '\\nand ')
        if transition['signal']:
            args['label'] += '\\n'+str(transition['signal'])
            args['style'] = 'bold'

        if activities[transition['act_from']]['split_mode'] == 'AND':
            args['arrowtail'] = 'box'
        elif str(activities[transition['act_from']]['split_mode']) == 'OR ':
            args['arrowtail'] = 'inv'

        if activities[transition['act_to']]['join_mode'] == 'AND':
            args['arrowhead'] = 'crow'

        activity_from = actfrom[transition['act_from']][1].get(
                transition['signal'], actfrom[transition['act_from']][0])
        activity_to = actto[transition['act_to']][1].get(transition['signal'],
                actto[transition['act_to']][0])
        graph.add_edge(pydot.Edge(activity_from , activity_to,
            fontsize=10, **args))
    nodes = cursor.dictfetchall()
    cursor.execute('SELECT id FROM wkf_activity ' \
            'WHERE flow_start = True AND wkf_id = %d ' \
            'LIMIT 1', (wkf_id,))
    start = cursor.fetchone()[0]
    cursor.execute("SELECT 'subflow.'||name, id FROM wkf_activity " \
            "WHERE flow_stop = True AND wkf_id = %d", (wkf_id,))
    stop = cursor.fetchall()
    stop = (stop[0][1], dict(stop))
    return ((start, {}), stop)


def graph_instance_get(cursor, graph, inst_id, nested=False):
    cursor.execute('SELECT * FROM wkf_instance WHERE id = %d', (inst_id,))
    inst = cursor.dictfetchone()

    def workitem_get(instance):
        cursor.execute('SELECT act_id, count(*) FROM wkf_workitem ' \
                'WHERE inst_id = %d GROUP BY act_id', (instance,))
        workitems = dict(cursor.fetchall())

        cursor.execute('SELECT subflow_id FROM wkf_workitem ' \
                'WHERE inst_id = %d', (instance,))
        for (subflow_id,) in cursor.fetchall():
            workitems.update(workitem_get(subflow_id))
        return workitems
    graph_get(cursor, graph, inst['wkf_id'], nested, workitem_get(inst_id))


# TODO: Fix concurency
class ReportGraphInstance(object):

    def __init__(self, cursor, data):
        logger = Logger()
        try:
            import pydot
        except:
            logger.notify_channel('workflow', LOG_WARNING,
                    'Import Error for pydot, you will not be able ' \
                            'to render workflows\n' \
                            'Consider Installing PyDot or dependencies: ' \
                            'http://dkbza.org/pydot.html')
            raise
        self.done = False

        try:
            cursor.execute('SELECT * FROM wkf WHERE osv = %s LIMIT 1',
                    (data['model'],))
            wkfinfo = cursor.dictfetchone()
            if not wkfinfo:
                ps_string = '''%PS-Adobe-3.0
/inch {72 mul} def
/Times-Roman findfont 50 scalefont setfont
1.5 inch 15 inch moveto
(No workflow defined) show
showpage'''
            else:
                cursor.execute('SELECT id FROM wkf_instance ' \
                        'WHERE res_id=%d AND wkf_id=%d ' \
                        'ORDER BY state LIMIT 1',
                        (data['id'], wkfinfo['id']))
                inst_id = cursor.fetchone()
                if not inst_id:
                    ps_string = '''%PS-Adobe-3.0
/inch {72 mul} def
/Times-Roman findfont 50 scalefont setfont
1.5 inch 15 inch moveto
(No workflow instance defined) show
showpage'''
                else:
                    inst_id = inst_id[0]
                    graph = pydot.Dot(fontsize=16,
                            label="\\n\\nWorkflow: %s\\n OSV: %s" % \
                                    (wkfinfo['name'],wkfinfo['osv']))
                    graph.set('size', '10.7,7.3')
                    graph.set('center', '1')
                    graph.set('ratio', 'auto')
                    graph.set('rotate', '90')
                    graph.set('rankdir', 'LR')
                    graph_instance_get(cursor, graph, inst_id,
                            data.get('nested', False))
                    ps_string = graph.create(prog='dot', format='ps')
        except:
            import traceback, sys
            tb_s = reduce(lambda x, y: x+y,
                    traceback.format_exception(sys.exc_type, sys.exc_value,
                        sys.exc_traceback))
            logger.notify_channel('workflow', LOG_ERROR,
                    'Exception in call: ' + tb_s)
            # string is in PS, like the success message would have been
            ps_string = '''%PS-Adobe-3.0
/inch {72 mul} def
/Times-Roman findfont 50 scalefont setfont
1.5 inch 15 inch moveto
(No workflow available) show
showpage'''
        if os.name == "nt":
            prog = 'ps2pdf.bat'
        else:
            prog = 'ps2pdf'
        args = (prog, '-', '-')
        try:
            inpt, outpt = exec_command_pipe(*args)
        except:
            return
        inpt.write(ps_string)
        inpt.close()
        self.result = outpt.read()
        outpt.close()
        self.done = True

    def is_done(self):
        return self.done

    def get(self):
        if self.done:
            return self.result
        else:
            return None

#class report_graph(report.interface.report_int):
#    def __init__(self, name, table):
#        report.interface.report_int.__init__(self, name)
#        self.table = table
#
#    def result(self):
#        if self.obj.is_done():
#            return (True, self.obj.get(), 'pdf')
#        else:
#            return (False, False, False)
#
#    def create(self, cursor, user, ids, data, context={}):
#        self.obj = ReportGraphInstance(cursor, data)
#        return (self.obj.get(), 'pdf')
#
#report_graph('report.workflow.instance.graph', 'ir.workflow')
