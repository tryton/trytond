"Convert"
import re
import StringIO, xml.dom.minidom
from trytond import pooler
from trytond.osv.fields import Integer
import csv
import os.path
from trytond.netsvc import Logger, LOG_ERROR, LOG_INFO, LocalService
from trytond.config import CONFIG
from trytond.version import VERSION
import logging


def _ref(self, cursor):
    return lambda x: self.id_get(cursor, x)

def _obj(pool, cursor, user, model_str, context=None):
    model = pool.get(model_str)
    return lambda x: model.browse(cursor, user, x, context=context)

def _eval_xml(self, node, pool, cursor, user, idref, context=None):
    if context is None:
        context = {}
    if node.nodeType == node.TEXT_NODE:
        return node.data.encode("utf8")
    elif node.nodeType == node.ELEMENT_NODE:
        if node.nodeName in ('field','value'):
            f_type = node.getAttribute('type') or 'char'
            f_model = node.getAttribute("model").encode('ascii')
            if len(node.getAttribute('search')):
                f_search = node.getAttribute("search").encode('utf-8')
                f_use = node.getAttribute("use").encode('ascii')
                f_name = node.getAttribute("name").encode('utf-8')
                if len(f_use)==0:
                    f_use = "id"
                args = eval(f_search, idref)
                ids = pool.get(f_model).search(cursor, user, args)
                if f_use != 'id':
                    ids = [x[f_use] for x in pool.get(f_model).read(
                        cursor, user, ids, [f_use])]
                _cols = pool.get(f_model)._columns
                if (f_name in _cols) and _cols[f_name]._type=='many2many':
                    return ids
                f_val = False
                if len(ids):
                    f_val = ids[0]
                    if isinstance(f_val, tuple):
                        f_val = f_val[0]
                return f_val
            a_eval = node.getAttribute('eval')
            if len(a_eval):
                import time
                idref['time'] = time
                idref['version'] = VERSION.rsplit('.', 1)[0]
                idref['ref'] = lambda x: self.id_get(cursor, x)
                if len(f_model):
                    idref['obj'] = _obj(self.pool, cursor, user, f_model,
                            context=context)
                try:
                    import pytz
                except:
                    Logger().notify_channel("init", LOG_INFO,
                            'could not find pytz library')


                    class Pytz(object):
                        all_timezones = []

                    pytz = Pytz()
                idref['pytz'] = pytz
                return eval(a_eval, idref)
            if f_type == 'xml':

                def _process(string, idref):
                    matches = re.findall('[^%]%\((.*?)\)[ds]', string)
                    for i in matches:
                        if not i in idref:
                            idref[i] = self.id_get(cursor, i)
                    return string % idref

                txt = '<?xml version="1.0"?>\n' + \
                        _process("".join([x.toxml().encode("utf8") \
                        for x in node.childNodes]), idref)
                return txt
            if f_type in ('char', 'int', 'float'):
                value = ""
                for child_node in node.childNodes:
                    value += str(_eval_xml(self, child_node, pool, cursor,
                        user, idref))
                if f_type == 'int':
                    value = value.strip()
                    if value == 'None':
                        return None
                    else:
                        value = int(value.strip())
                elif f_type == 'float':
                    value = float(value.strip())
                return value
            elif f_type in ('list', 'tuple'):
                res = []
                for child_node in node.childNodes:
                    if child_node.nodeType != child_node.ELEMENT_NODE \
                            or child_node.nodeName != 'value':
                        continue
                    res.append(_eval_xml(self, child_node, pool, cursor,
                        user, idref))
                if f_type == 'tuple':
                    return tuple(res)
                return res
        elif node.nodeName=="getitem":
            for child_node in node.childNodes:
                if child_node.nodeType != child_node.ELEMENT_NODE:
                    continue
                res = _eval_xml(self, child_node, pool, cursor, user, idref)
            if not res:
                raise LookupError
            elif node.getAttribute('type') in ("int", "list"):
                return res[int(node.getAttribute('index'))]
            else:
                return res[node.getAttribute('index').encode("utf8")]
        elif node.nodeName=="function":
            args = []
            a_eval = node.getAttribute('eval')
            if len(a_eval):
                idref['ref'] = lambda x: self.id_get(cursor, x)
                args = eval(a_eval, idref)
            for child_node in node.childNodes:
                if child_node.nodeType != child_node.ELEMENT_NODE:
                    continue
                args.append(_eval_xml(self, child_node, pool, cursor, user,
                    idref, context))
            model = pool.get(node.getAttribute('model'))
            method = node.getAttribute('name')
            res = getattr(model, method)(cursor, user, *args)
            return res
        elif node.nodeName=="test":
            value = ""
            for child_node in node.childNodes:
                value += str(_eval_xml(self, child_node, pool, cursor, user,
                    idref, context=context))
            return value

ESCAPE_RE = re.compile(r'(?<!\\)/')
def escape(i):
    return i.replace('\\/', '/')


class AssertionReport(object):

    def __init__(self):
        self._report = {}

    def record_assertion(self, success, severity):
        """
            Records the result of an assertion for the failed/success count
            retrurns success
        """
        if severity in self._report:
            self._report[severity][success] += 1
        else:
            self._report[severity] = {success:1, not success: 0}
        return success

    def get_report(self):
        return self._report

    def __str__(self):
        res = '\nAssertions report:\nLevel\tsuccess\tfailed\n'
        success = failed = 0
        for sev in self._report:
            res += sev + '\t' + str(self._report[sev][True]) + '\t' + \
                    str(self._report[sev][False]) + '\n'
            success += self._report[sev][True]
            failed += self._report[sev][False]
        res += 'total\t' + str(success) + '\t' + str(failed) + '\n'
        res += 'end of report (' + str(success + failed) + \
                ' assertion(s) checked)'
        return res

class XMLImport(object):

    def isnoupdate(self, data_node = None):
        return self.noupdate or (data_node \
                and data_node.getAttribute('noupdate'))

    def get_context(self, data_node, node, eval_dict):
        data_node_context = (data_node \
                and data_node.getAttribute('context').encode('utf8'))
        if data_node_context:
            context = eval(data_node_context, eval_dict)
        else:
            context = {}

        node_context = node.getAttribute("context").encode('utf8')
        if len(node_context):
            context.update(eval(node_context, eval_dict))

        return context

    def get_uid(self, cursor, user, data_node, node):
        node_uid = node.getAttribute('user') or (data_node \
                and data_node.getAttribute('user'))
        if len(node_uid):
            return self.id_get(cursor, node_uid)
        return user

    def _test_xml_id(self, xml_id):
        obj_id = xml_id
        if '.' in xml_id:
            obj_id = xml_id.split('.')[1]
        if len(obj_id) > 64:
            Logger().notify_channel('init', LOG_ERROR,
                    'id: %s is to long (max: 64)' % xml_id)
    def _tag_delete(self, cursor, rec, data_node=None):
        d_model = rec.getAttribute("model")
        d_search = rec.getAttribute("search")
        d_id = rec.getAttribute("id")
        ids = []
        if len(d_search):
            ids = self.pool.get(d_model).search(cursor, self.user,
                    eval(d_search))
        if len(d_id):
            ids.append(self.id_get(cursor, d_id))
        if len(ids):
            self.pool.get(d_model).unlink(cursor, self.user, ids)
            #self.pool.get('ir.model.data')._unlink(cursor, self.user, d_model,
            #   ids, direct=True)
        return False

    def _tag_report(self, cursor, rec, data_node=None):
        res = {}
        for dest, attr in (
                ('name', 'string'),
                ('model', 'model'),
                ('report_name', 'name'),
                ):
            res[dest] = rec.getAttribute(attr).encode('utf8')
            assert res[dest], "Attribute %s of report is empty !" % (attr,)
        for field, dest in (
                ('rml', 'report_rml'),
                ('xml', 'report_xml'),
                ('xsl', 'report_xsl'),
                ):
            if rec.hasAttribute(field):
                res[dest] = rec.getAttribute(field).encode('utf8')
        if rec.hasAttribute('auto'):
            res['auto'] = eval(rec.getAttribute('auto'))
        if rec.hasAttribute('header'):
            res['header'] = eval(rec.getAttribute('header'))
        res['multi'] = rec.hasAttribute('multi') \
                and  eval(rec.getAttribute('multi'))
        xml_id = rec.getAttribute('id').encode('utf8')
        self._test_xml_id(xml_id)
        obj_id = self.pool.get('ir.model.data')._update(cursor, self.user,
                "ir.actions.report.xml", self.module, res, xml_id,
                mode=self.mode)
        self.idref[xml_id] = int(obj_id)
        if not rec.hasAttribute('menu') or eval(rec.getAttribute('menu')):
            keyword = str(rec.getAttribute('keyword') or 'client_print_multi')
            value = 'ir.actions.report.xml,' + str(obj_id)
            replace = rec.hasAttribute('replace') \
                    and rec.getAttribute("replace")
            self.pool.get('ir.model.data').ir_set(cursor, self.user, 'action',
                    keyword, res['name'], [res['model']], value,
                    replace=replace, isobject=True, xml_id=xml_id)
        return False

    def _tag_function(self, cursor, rec, data_node=None):
        if self.isnoupdate(data_node) and self.mode != 'init':
            return
        context = self.get_context(data_node, rec, {'ref': _ref(self, cursor)})
        user = self.get_uid(cursor, self.user, data_node, rec)
        _eval_xml(self, rec, self.pool, cursor, user, self.idref,
                context=context)
        return False

    def _tag_wizard(self, cursor, rec, data_node=None):
        string = rec.getAttribute("string").encode('utf8')
        model = rec.getAttribute("model").encode('utf8')
        name = rec.getAttribute("name").encode('utf8')
        xml_id = rec.getAttribute('id').encode('utf8')
        self._test_xml_id(xml_id)
        multi = rec.hasAttribute('multi') and  eval(rec.getAttribute('multi'))
        res = {'name': string, 'wiz_name': name, 'multi':multi}

        obj_id = self.pool.get('ir.model.data')._update(cursor, self.user,
                "ir.actions.wizard", self.module, res, xml_id, mode=self.mode)
        self.idref[xml_id] = int(obj_id)
        # ir_set
        if (not rec.hasAttribute('menu') or eval(rec.getAttribute('menu'))) \
                and obj_id:
            keyword = str(rec.getAttribute('keyword') or 'client_action_multi')
            value = 'ir.actions.wizard,' + str(obj_id)
            replace = rec.hasAttribute('replace') and \
                    rec.getAttribute("replace") or True
            self.pool.get('ir.model.data').ir_set(cursor, self.user, 'action',
                    keyword, string, [model], value, replace=replace,
                    isobject=True, xml_id=xml_id)
        return False

    def _tag_act_window(self, cursor, rec, data_node=None):
        name = rec.hasAttribute('name') \
                and rec.getAttribute('name').encode('utf-8')
        xml_id = rec.getAttribute('id').encode('utf8')
        self._test_xml_id(xml_id)
        ftype = rec.hasAttribute('type') \
                and rec.getAttribute('type').encode('utf-8') \
                or 'ir.actions.act_window'
        view_id = False
        if rec.hasAttribute('view'):
            view_id = self.id_get(cursor,
                    rec.getAttribute('view').encode('utf-8'))
        domain = rec.hasAttribute('domain') \
                and rec.getAttribute('domain').encode('utf-8')
        context = rec.hasAttribute('context') \
                and rec.getAttribute('context').encode('utf-8') \
                or '{}'
        res_model = rec.getAttribute('res_model').encode('utf-8')
        src_model = rec.hasAttribute('src_model') \
                and rec.getAttribute('src_model').encode('utf-8')
        view_type = rec.hasAttribute('view_type') \
                and rec.getAttribute('view_type').encode('utf-8') \
                or 'form'
        view_mode = rec.hasAttribute('view_mode') \
                and rec.getAttribute('view_mode').encode('utf-8') \
                or 'tree,form'
        usage = rec.hasAttribute('usage') \
                and rec.getAttribute('usage').encode('utf-8')
        limit = rec.hasAttribute('limit') \
                and rec.getAttribute('limit').encode('utf-8')
        auto_refresh = rec.hasAttribute('auto_refresh') \
                and rec.getAttribute('auto_refresh').encode('utf-8')

        res = {
                'name': name,
                'type': ftype,
                'view_id': view_id,
                'domain': domain,
                'context': context,
                'res_model': res_model,
                'src_model': src_model,
                'view_type': view_type,
                'view_mode': view_mode,
                'usage': usage,
                'limit': limit,
                'auto_refresh': auto_refresh,
            }

        obj_id = self.pool.get('ir.model.data')._update(cursor, self.user,
                'ir.actions.act_window', self.module, res, xml_id,
                mode=self.mode)
        self.idref[xml_id] = int(obj_id)

        if src_model:
            keyword = 'client_action_relate'
            value = 'ir.actions.act_window,' + str(obj_id)
            replace = rec.hasAttribute('replace') \
                    and rec.getAttribute('replace')
            self.pool.get('ir.model.data').ir_set(cursor, self.user, 'action',
                    keyword, xml_id, [src_model], value, replace=replace,
                    isobject=True, xml_id=xml_id)
        # TODO add remove ir.model.data
        return False

    def _tag_ir_set(self, cursor, rec, data_node=None):
        if not self.mode == 'init':
            return False
        res = {}
        for field in [i for i in rec.childNodes \
                if (i.nodeType == i.ELEMENT_NODE and i.nodeName=="field")]:
            f_name = field.getAttribute("name").encode('utf-8')
            f_val = _eval_xml(self, field, self.pool, cursor, self.user,
                    self.idref)
            res[f_name] = f_val
        self.pool.get('ir.model.data').ir_set(cursor, self.user, res['key'],
                res['key2'], res['name'], res['models'], res['value'],
                replace=res.get('replace',True),
                isobject=res.get('isobject', False), meta=res.get('meta',None))
        return False

    def _tag_workflow(self, cursor, rec, data_node=None):
        if self.isnoupdate(data_node) and self.mode != 'init':
            return
        model = str(rec.getAttribute('model'))
        w_ref = rec.getAttribute('ref')
        if len(w_ref):
            obj_id = self.id_get(cursor, w_ref)
        else:
            assert rec.childNodes, 'You must define a child node ' \
                    'if you dont give a ref'
            element_childs = [i for i in rec.childNodes \
                    if i.nodeType == i.ELEMENT_NODE]
            assert len(element_childs) == 1, 'Only one child node ' \
                    'is accepted (%d given)' % len(rec.childNodes)
            obj_id = _eval_xml(self, element_childs[0], self.pool, cursor,
                    self.user, self.idref)

        user = self.get_uid(cursor, self.user, data_node, rec)
        wf_service = LocalService("workflow")
        wf_service.trg_validate(user, model,
            obj_id,
            str(rec.getAttribute('action')), cursor)
        return False

    def _tag_menuitem(self, cursor, rec, data_node=None):
        rec_id = rec.getAttribute("id").encode('ascii')
        self._test_xml_id(rec_id)
        m_l = [escape(x) for x in ESCAPE_RE.split(
            rec.getAttribute("name").encode('utf8'))]
        pid = False
        for idx, menu_elem in enumerate(m_l):
            if pid:
                cursor.execute('SELECT id FROM ir_ui_menu ' \
                        'WHERE parent_id = %d AND name = %s',
                        (pid, menu_elem))
            else:
                cursor.execute('SELECT id FROM ir_ui_menu ' \
                        'WHERE parent_id IS NULL AND name = %s',
                        (menu_elem,))
            res = cursor.fetchone()
            if idx == (len(m_l) - 1):
                # we are at the last menu element/level (it's a leaf)
                values = {'parent_id': pid, 'name': menu_elem}

                if rec.hasAttribute('action'):
                    a_action = rec.getAttribute('action').encode('utf8')
                    a_type = rec.getAttribute('type').encode('utf8') \
                            or 'act_window'
                    icons = {
                        "act_window": 'STOCK_NEW',
                        "report.xml": 'STOCK_PASTE',
                        "wizard": 'STOCK_EXECUTE',
                        "url": 'STOCK_JUMP_TO'
                    }
                    values['icon'] = icons.get(a_type,'STOCK_NEW')
                    if a_type == 'act_window':
                        a_id = self.id_get(cursor, a_action)
                        cursor.execute('SELECT view_type, view_mode, ' \
                                'name, view_id ' \
                                'FROM ir_act_window ' \
                                'WHERE id = %d', (int(a_id),))
                        action_type, action_mode, action_name, view_id = \
                                cursor.fetchone()
                        if view_id:
                            cursor.execute('SELECT type FROM ir_ui_view ' \
                                    'WHERE id = %d', (int(view_id),))
                            action_mode, = cursor.fetchone()
                        cursor.execute('SELECT view_mode ' \
                                'FROM ir_act_window_view ' \
                                'WHERE act_window_id = %d ' \
                                'ORDER BY sequence LIMIT 1', (int(a_id),))
                        if cursor.rowcount:
                            action_mode, = cursor.fetchone()
                        if action_type == 'tree':
                            values['icon'] = 'STOCK_INDENT'
                        elif action_mode and action_mode.startswith('tree'):
                            values['icon'] = 'STOCK_JUSTIFY_FILL'
                        elif action_mode and action_mode.startswith('graph'):
                            values['icon'] = 'terp-graph'
                        elif action_mode and action_mode.startswith('calendar'):
                            values['icon'] = 'terp-calendar'
                        if not values['name']:
                            values['name'] = action_name
                if rec.hasAttribute('sequence'):
                    values['sequence'] = int(rec.getAttribute('sequence'))
                if rec.hasAttribute('icon'):
                    values['icon'] = str(rec.getAttribute('icon'))
                if rec.hasAttribute('groups'):
                    g_names = rec.getAttribute('groups').split(',')
                    groups_value = []
                    groups_obj = self.pool.get('res.groups')
                    for group in g_names:
                        if group.startswith('-'):
                            obj_id = groups_obj.search(cursor, self.user,
                                    [('name', '=', group[1:])])[0]
                            groups_value.append((3, obj_id))
                        else:
                            obj_id = groups_obj.search(cursor, self.user,
                                [('name', '=', group)])[0]
                            groups_value.append((4, obj_id))
                    values['groups_id'] = groups_value
                xml_id = rec.getAttribute('id').encode('utf8')
                self._test_xml_id(xml_id)
                pid = self.pool.get('ir.model.data')._update(cursor, self.user,
                        'ir.ui.menu', self.module, values, xml_id,
                        mode=self.mode, res_id=(res and res[0] or False))
            elif res:
                # the menuitem already exists
                pid = res[0]
                xml_id = (idx==len(m_l) - 1) \
                        and rec.getAttribute('id').encode('utf8')
                self.pool.get('ir.model.data')._update_dummy(cursor,
                        self.user, 'ir.ui.menu', self.module, xml_id)
            else:
                # the menuitem does't exist but we are in branch (not a leaf)
                pid = self.pool.get('ir.ui.menu').create(cursor, self.user,
                    {'parent_id': pid, 'name': menu_elem})
        if rec_id and pid:
            self.idref[rec_id] = int(pid)
        if rec.hasAttribute('action') and pid:
            a_action = rec.getAttribute('action').encode('utf8')
            a_type = rec.getAttribute('type').encode('utf8') or 'act_window'
            a_id = self.id_get(cursor, a_action)
            action = "ir.actions.%s,%d" % (a_type, a_id)
            self.pool.get('ir.model.data').ir_set(cursor, self.user, 'action',
                'tree_but_open', 'Menuitem', [('ir.ui.menu', int(pid))],
                action, True, True, xml_id=rec_id)
        return ('ir.ui.menu', pid)

    @staticmethod
    def _assert_equals(i, j, prec=4):
        return not round(i - j, prec)

    def _tag_assert(self, cursor, rec, data_node=None):
        if self.isnoupdate(data_node) and self.mode != 'init':
            return

        rec_model = rec.getAttribute("model").encode('ascii')
        model = self.pool.get(rec_model)
        assert model, "The model %s does not exist !" % (rec_model,)
        rec_id = rec.getAttribute("id").encode('ascii')
        self._test_xml_id(rec_id)
        rec_src = rec.getAttribute("search").encode('utf8')
        rec_src_count = rec.getAttribute("count")

        severity = rec.getAttribute("severity").encode('ascii') or 'info'

        rec_string = rec.getAttribute("string").encode('utf8') or 'unknown'

        ids = None
        eval_dict = {'ref': _ref(self, cursor)}
        context = self.get_context(data_node, rec, eval_dict)
        user = self.get_uid(cursor, self.user, data_node, rec)
        if len(rec_id):
            ids = [self.id_get(cursor, rec_id)]
        elif len(rec_src):
            args = eval(rec_src, eval_dict)
            ids = self.pool.get(rec_model).search(cursor, user, args,
                    context=context)
            if len(rec_src_count):
                count = int(rec_src_count)
                if len(ids) != count:
                    self.assert_report.record_assertion(False, severity)
                    Logger().notify_channel('init', severity,
                            'assertion "' + rec_string + \
                                    '" failed ! (search count is incorrect: ' \
                                    + str(len(ids)) + ')' )
                    sevval = getattr(logging, severity.upper())
                    if sevval > CONFIG['assert_exit_level']:
                        # TODO: define a dedicated exception
                        raise Exception('Severe assertion failure')
                    return

        assert ids != None, 'You must give either an id or a search criteria'

        ref = _ref(self, cursor)
        for brrec in model.browse(cursor, user, ids, context):


            class Dict(dict):

                def __getitem__(self, key):
                    if key in brrec:
                        return brrec[key]
                    return dict.__getitem__(self, key)

            eval_globals = Dict()
            eval_globals['floatEqual'] = self._assert_equals
            eval_globals['ref'] = ref
            eval_globals['_ref'] = ref
            for test in [i for i in rec.childNodes \
                    if (i.nodeType == i.ELEMENT_NODE and i.nodeName=="test")]:
                f_expr = test.getAttribute("expr").encode('utf-8')
                f_val = _eval_xml(self, test, self.pool, cursor, user,
                        self.idref, context=context) or True
                if eval(f_expr, eval_globals) != f_val: # assertion failed
                    self.assert_report.record_assertion(False, severity)
                    Logger().notify_channel('init', severity,
                            'assertion "' + rec_string + \
                                    '" failed ! (tag ' + test.toxml() + ')' )
                    sevval = getattr(logging, severity.upper())
                    if sevval > CONFIG['assert_exit_level']:
                        # TODO: define a dedicated exception
                        raise Exception('Severe assertion failure')
                    return
        else: # all tests were successful for this assertion tag (no break)
            self.assert_report.record_assertion(True, severity)

    def _tag_record(self, cursor, rec, data_node=None):
        rec_model = rec.getAttribute("model").encode('ascii')
        model = self.pool.get(rec_model)
        assert model, "The model %s does not exist !" % (rec_model,)
        rec_id = rec.getAttribute("id").encode('ascii')
        self._test_xml_id(rec_id)

#        if not rec_id and not self.isnoupdate(data_node):
#            print "Warning", rec_model

        if self.isnoupdate(data_node) and not self.mode == 'init':
            # check if the xml record has an id string
            if rec_id:
                obj_id = self.pool.get('ir.model.data')._update_dummy(cursor,
                        self.user, rec_model, self.module, rec_id)
                # check if the resource already existed at the last update
                if obj_id:
                    # if it existed, we don't update the data, but we need to
                    # know the id of the existing record anyway
                    self.idref[rec_id] = int(obj_id)
                    return None
                else:
                    # if the resource didn't exist
                    if rec.getAttribute("forcecreate"):
                        # we want to create it, so we let the normal
                        # "update" behavior happen
                        pass
                    else:
                        # otherwise do nothing
                        return None
            else:
                # otherwise it is skipped
                return None

        res = {}
        for field in [i for i in rec.childNodes \
                if (i.nodeType == i.ELEMENT_NODE and i.nodeName=="field")]:
            #TODO: most of this code is duplicated above (in _eval_xml)
            f_name = field.getAttribute("name").encode('utf-8')
            f_ref = field.getAttribute("ref").encode('ascii')
            f_search = field.getAttribute("search").encode('utf-8')
            f_model = field.getAttribute("model").encode('ascii')
            if not f_model and model._columns.get(f_name, False):
                f_model = model._columns[f_name]._obj
            f_use = field.getAttribute("use").encode('ascii') or 'id'
            f_val = False

            if len(f_search):
                args = eval(f_search, self.idref)
                field = []
                assert f_model, 'Define an attribute ' \
                        'model="..." in your .XML file !'
                f_obj = self.pool.get(f_model)
                # browse the objects searched
                objs = f_obj.browse(cursor, self.user, f_obj.search(cursor,
                    self.user, args))
                # column definitions of the "local" object
                _cols = self.pool.get(rec_model)._columns
                # if the current field is many2many
                if (f_name in _cols) and _cols[f_name]._type=='many2many':
                    f_val = [(6, 0, [x[f_use] for x in objs])]
                elif len(objs):
                    # otherwise (we are probably in a many2one field),
                    # take the first element of the search
                    f_val = objs[0][f_use]
            elif len(f_ref):
                if f_ref == "null":
                    f_val = False
                else:
                    f_val = self.id_get(cursor, f_ref)
            else:
                f_val = _eval_xml(self, field, self.pool, cursor, self.user,
                        self.idref)
                if model._columns.has_key(f_name):
                    if isinstance(model._columns[f_name], Integer):
                        f_val = int(f_val)
            res[f_name] = f_val
        obj_id = self.pool.get('ir.model.data')._update(cursor, self.user,
                rec_model, self.module, res, rec_id or False,
                noupdate=self.isnoupdate(data_node), mode=self.mode)
        if rec_id:
            self.idref[rec_id] = int(obj_id)
        return rec_model, obj_id

    def id_get(self, cursor, id_str):
        if id_str in self.idref:
            return self.idref[id_str]
        mod = self.module
        if '.' in id_str:
            mod, id_str = id_str.split('.')
        result = self.pool.get('ir.model.data')._get_id(cursor, self.user,
                mod, id_str)
        return int(self.pool.get('ir.model.data').read(cursor, self.user,
            [result], ['res_id'])[0]['res_id'])

    def parse(self, xmlstr):
        doc = xml.dom.minidom.parseString(xmlstr)
        elem = doc.documentElement
        for node in [i for i in elem.childNodes \
                if (i.nodeType == i.ELEMENT_NODE and i.nodeName=="data")]:
            for rec in node.childNodes:
                if rec.nodeType == rec.ELEMENT_NODE:
                    if rec.nodeName in self._tags:
                        try:
                            self._tags[rec.nodeName](self.cursor, rec, node)
                        except:
                            Logger().notify_channel("init", LOG_INFO,
                                    '\n'+rec.toxml())
                            self.cursor.rollback()
                            raise
        return True

    def __init__(self, cursor, module, idref, mode, report=AssertionReport(),
            noupdate = False):
        self.mode = mode
        self.module = module
        self.cursor = cursor
        self.idref = idref
        self.pool = pooler.get_pool(cursor.dbname)
        self.user = 1
        self.assert_report = report
        self.noupdate = noupdate
        self._tags = {
            'menuitem': self._tag_menuitem,
            'record': self._tag_record,
            'assert': self._tag_assert,
            'report': self._tag_report,
            'wizard': self._tag_wizard,
            'delete': self._tag_delete,
            'ir_set': self._tag_ir_set,
            'function': self._tag_function,
            'workflow': self._tag_workflow,
            'act_window': self._tag_act_window,
        }

def convert_csv_import(cursor, module, fname, csvcontent, idref=None,
        mode='init', noupdate=False):
    '''
    Import csv file :
        quote: "
        delimiter: ,
        encoding: utf-8
    '''
    if idref is None:
        idref = {}
    model = ('.'.join(fname.split('.')[:-1]).split('-'))[0]
    #remove folder path from model
    model = os.path.split(model)[1]

    pool = pooler.get_pool(cursor.dbname)

    input_file = StringIO.StringIO(csvcontent)
    reader = csv.reader(input_file, quotechar='"', delimiter=',')
    fields = reader.next()

    if not (mode == 'init' or 'id' in fields):
        return

    user = 1
    datas = []
    for line in reader:
        if (not line) or not reduce(lambda x, y: x or y, line) :
            continue
        datas.append([x.decode('utf8').encode('utf8') for x in line])
    pool.get(model).import_data(cursor, user, fields, datas, mode,
            module, noupdate)

def convert_xml_import(cursor, module, xmlstr, idref=None, mode='init',
        noupdate=False, report=None):
    if idref is None:
        idref = {}
    if report is None:
        report = AssertionReport()
    obj = XMLImport(cursor, module, idref, mode, report=report,
            noupdate=noupdate)
    obj.parse(xmlstr)
    del obj
    return True
