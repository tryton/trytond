"Actions"
from trytond.osv import fields, OSV
from trytond.tools import file_open


class Actions(OSV):
    "Actions"
    _name = 'ir.actions.actions'
    _table = 'ir_actions'
    _description = __doc__
    _columns = {
        'name': fields.char('Action Name', required=True, size=64),
        'type': fields.char('Action Type', required=True, size=32),
        'usage': fields.char('Action Usage', size=32)
    }
    _defaults = {
        'usage': lambda *a: False,
    }

Actions()


class ActionsExecute(OSV):
    "Actions execute"
    _name = 'ir.actions.execute'
    _table = 'ir_act_execute'
    _sequence = 'ir_actions_id_seq'
    _description = __doc__
    _columns = {
        'name': fields.char('name', size=64, required=True, translate=True),
        'type': fields.char('type', size=32, required=True),
        'func_name': fields.char('Function Name', size=64, required=True),
        'func_arg': fields.char('Function Argument', size=64),
        'usage': fields.char('Action Usage', size=32)
    }

ActionsExecute()


class ActionsGroup(OSV):
    "Actions group"
    _name = 'ir.actions.group'
    _table = 'ir_act_group'
    _sequence = 'ir_actions_id_seq'
    _description = __doc__
    _columns = {
        'name': fields.char('Group Name', size=64, required=True),
        'type': fields.char('Action Type', size=32, required=True),
        'exec_type': fields.char('Execution sequence', size=64, required=True),
        'usage': fields.char('Action Usage', size=32)
    }

ActionsGroup()


class ActionsReportCustom(OSV):
    "Actions report custom"
    _name = 'ir.actions.report.custom'
    _table = 'ir_act_report_custom'
    _sequence = 'ir_actions_id_seq'
    _description = __doc__
    _columns = {
        'name': fields.char('Report Name', size=64, required=True,
            translate=True),
        'type': fields.char('Report Type', size=32, required=True),
        'model':fields.char('Model', size=64, required=True),
        'report_id': fields.integer('Report Ref.', required=True),
        'usage': fields.char('Action Usage', size=32),
        'multi': fields.boolean('On multiple doc.',
            help="If set to true, the action will not be displayed " \
                    "on the right toolbar of a form views.")
    }
    _defaults = {
        'multi': lambda *a: False,
    }

ActionsReportCustom()


class ActionsReportXML(OSV):
    "Actions report xml"

    def _report_content(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            data = report[name + '_data']
            if not data and report[name[:-8]]:
                try:
                    data = file_open(report[name[:-8]], mode='rb').read()
                except:
                    data = False
            res[report.id] = data
        return res

    def _report_content_inv(self, cursor, user, obj_id, name, value, arg,
            context=None):
        self.write(cursor, user, obj_id, {name+'_data': value}, context=context)

    def _report_sxw(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            if report.report_rml:
                res[report.id] = report.report_rml.replace('.rml', '.sxw')
            else:
                res[report.id] = False
        return res

    _name = 'ir.actions.report.xml'
    _table = 'ir_act_report_xml'
    _sequence = 'ir_actions_id_seq'
    _description = __doc__
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'type': fields.char('Report Type', size=32, required=True),
        'model': fields.char('Model', size=64, required=True),
        'report_name': fields.char('Internal Name', size=64, required=True),
        'report_xsl': fields.char('XSL path', size=256),
        'report_xml': fields.char('XML path', size=256),
        'report_rml': fields.char('RML path', size=256,
            help="The .rml path of the file or NULL \n" \
                    "if the content is in report_rml_content"),
        'report_sxw': fields.function(_report_sxw, method=True, type='char',
            string='SXW path'),
        'report_sxw_content_data': fields.binary('SXW content'),
        'report_rml_content_data': fields.binary('RML content'),
        'report_sxw_content': fields.function(_report_content,
            fnct_inv=_report_content_inv, method=True,
            type='binary', string='SXW content',),
        'report_rml_content': fields.function(_report_content,
            fnct_inv=_report_content_inv, method=True,
            type='binary', string='RML content'),
        'auto': fields.boolean('Automatic XSL:RML', required=True),
        'usage': fields.char('Action Usage', size=32),
        'header': fields.boolean('Add RML header',
            help="Add or not the coporate RML header"),
        'multi': fields.boolean('On multiple doc.',
            help="If set to true, the action will not be displayed " \
                    "on the right toolbar of a form views.")
    }
    _defaults = {
        'type': lambda *a: 'ir.actions.report.xml',
        'multi': lambda *a: False,
        'auto': lambda *a: True,
        'header': lambda *a: True,
        'report_sxw_content': lambda *a: False,
    }

ActionsReportXML()


class ActionsActWindow(OSV):
    "Actions act window"
    _name = 'ir.actions.act_window'
    _table = 'ir_act_window'
    _sequence = 'ir_actions_id_seq'
    _description = __doc__

    def _views_get_fnc(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for act in self.browse(cursor, user, ids, context=context):
            res[act.id] = [(view.view_id.id, view.view_mode) \
                    for view in act.view_ids]
            if (not act.view_ids):
                modes = act.view_mode.split(',')
                find = False
                if act.view_id.id:
                    res[act.id].append((act.view_id.id, act.view_id.type))
                for mode in modes:
                    if act.view_id and (mode == act.view_id.type) and not find:
                        find = True
                        continue
                    res[act.id].append((False, mode))
        return res

    _columns = {
        'name': fields.char('Action Name', size=64, translate=True),
        'type': fields.char('Action Type', size=32, required=True),
        'view_id': fields.many2one('ir.ui.view', 'View Ref.',
            ondelete='cascade'),
        'domain': fields.char('Domain Value', size=250),
        'context': fields.char('Context Value', size=250),
        'res_model': fields.char('Model', size=64),
        'src_model': fields.char('Source model', size=64),
        'view_type': fields.selection([('tree','Tree'), ('form','Form')],
            string='Type of view'),
        'view_mode': fields.char('Mode of view', size=250),
        'usage': fields.char('Action Usage', size=32),
        'view_ids': fields.one2many('ir.actions.act_window.view',
            'act_window_id', 'Views'),
        'views': fields.function(_views_get_fnc, method=True, type='binary',
            string='Views'),
        'limit': fields.integer('Limit',
            help='Default limit for the list view'),
        'auto_refresh': fields.integer('Auto-Refresh',
            help='Add an auto-refresh on the view'),
    }
    _defaults = {
        'type': lambda *a: 'ir.actions.act_window',
        'view_type': lambda *a: 'form',
        'view_mode': lambda *a: 'tree,form',
        'context': lambda *a: '{}',
        'limit': lambda *a: 80,
        'auto_refresh': lambda *a: 0,
    }

ActionsActWindow()


class ActionsActWindowView(OSV):
    "Actions act window view"
    _name = 'ir.actions.act_window.view'
    _table = 'ir_act_window_view'
    _rec_name = 'view_id'
    _description = __doc__
    _columns = {
        'sequence': fields.integer('Sequence'),
        'view_id': fields.many2one('ir.ui.view', 'View'),
        'view_mode': fields.selection((
            ('tree', 'Tree'),
            ('form', 'Form'),
            ('graph', 'Graph'),
            ('calendar', 'Calendar')), string='Type of view', required=True),
        'act_window_id': fields.many2one('ir.actions.act_window', 'Action'),
        'multi': fields.boolean('On multiple doc.',
            help="If set to true, the action will not be displayed \n" \
                    "on the right toolbar of a form views."),
    }
    _defaults = {
        'multi': lambda *a: False,
    }
    _order = 'sequence'

ActionsActWindowView()


class ActionsWizard(OSV):
    "Actions wizard"
    _name = 'ir.actions.wizard'
    _table = 'ir_act_wizard'
    _sequence = 'ir_actions_id_seq'
    _description = __doc__
    _columns = {
        'name': fields.char('Wizard info', size=64, required=True,
            translate=True),
        'type': fields.char('Action type', size=32, required=True),
        'wiz_name': fields.char('Wizard name', size=64, required=True),
        'multi': fields.boolean('Action on multiple doc.',
            help="If set to true, the wizard will not be displayed \n" \
                    "on the right toolbar of a form views.")
    }
    _defaults = {
        'type': lambda *a: 'ir.actions.wizard',
        'multi': lambda *a: False,
    }

ActionsWizard()


class ActionsURL(OSV):
    "Actions URL"
    _name = 'ir.actions.url'
    _table = 'ir_act_url'
    _sequence = 'ir_actions_id_seq'
    _description = __doc__
    _columns = {
        'name': fields.char('Action Name', size=64, translate=True),
        'type': fields.char('Action Type', size=32, required=True),
        'url': fields.text('Action Url',required=True),
        'target': fields.selection([
            ('new', 'New Window'),
            ('self', 'This Window'),
            ], 'Action Target', required=True)
    }
    _defaults = {
        'type': lambda *a: 'ir.actions.act_url',
        'target': lambda *a: 'new',
    }

ActionsURL()
