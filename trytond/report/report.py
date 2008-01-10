"Report"
from trytond.netsvc import Service, service_exist, Logger, LOG_ERROR
from trytond import pooler
import copy
import xml
from xml import dom
from trytond.osv import ExceptORM, ExceptOSV, OSV
import sys
import base64
import StringIO
import zipfile
import locale
import time

MODULE_LIST = []
MODULE_CLASS_LIST = {}
CLASS_POOL = {}


class ReportService(Service):

    def __init__(self):
        self.object_name_pool = {}
        self.module_obj_list = {}
        Service.__init__(self, 'report_proxy')
        Service.join_group(self, 'web-services')
        Service.export_method(self, self.execute)

    def execute_cr(self, cursor, user, report_name, ids, datas, context=None):
        try:
            report = pooler.get_pool_report(cursor.dbname).get(report_name)
            if not report:
                report = Report.create_instance(self, 'report', pooler.get_pool(cursor.dbname))
                report._name = report_name
                self.add(report._name, report)
            res = report.execute(cursor, user, ids, datas, context)
            return res
        except ExceptORM, inst:
            self.abort_response(inst.name, 'warning', inst.value)
        except ExceptOSV, inst:
            self.abort_response(inst.name, inst.exc_type, inst.value)
        except:
            import traceback
            tb_s = reduce(lambda x, y: x+y, traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_traceback))
            Logger().notify_channel("web-services", LOG_ERROR,
                    'Exception in call: ' + tb_s)
            raise

    def execute(self, dbname, user, report_name, ids, datas, context=None):
        cursor = pooler.get_db(dbname).cursor()
        pool = pooler.get_pool_report(dbname)
        try:
            try:
                res = pool.execute_cr(cursor, user, report_name, ids, datas, context)
                cursor.commit()
            except Exception:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def add(self, name, object_name_inst):
        """
        adds a new obj instance to the obj pool.
        if it already existed, the instance is replaced
        """
        if self.object_name_pool.has_key(name):
            del self.object_name_pool[name]
        self.object_name_pool[name] = object_name_inst

        module = str(object_name_inst.__class__)[6:]
        module = module[:len(module)-1]
        module = module.split('.')[0][2:]
        self.module_obj_list.setdefault(module, []).append(object_name_inst)

    def get(self, name):
        return self.object_name_pool.get(name, None)

    def instanciate(self, module, pool_obj):
        res = []
        class_list = MODULE_CLASS_LIST.get(module, [])
        for klass in class_list:
            res.append(klass.create_instance(self, module, pool_obj))
        return res

PARENTS = {
    'table-row': 1,
    'list-item': 1,
    'body': 0,
    'section': 0,
}


class Report(object):
    _name = ""

    def __new__(cls):
        for module in cls.__module__.split('.'):
            if module != 'trytond' and module != 'addons':
                break
        if not hasattr(cls, '_module'):
            cls._module = module
        MODULE_CLASS_LIST.setdefault(cls._module, []).append(cls)
        CLASS_POOL[cls._name] = cls
        if module not in MODULE_LIST:
            MODULE_LIST.append(cls._module)
        return None

    def create_instance(cls, pool, module, pool_obj):
        """
        try to apply inheritancy at the instanciation level and
        put objs in the pool var
        """
        if pool.get(cls._name):
            parent_class = pool.get(cls._name).__class__
            cls = type(cls._name, (cls, parent_class), {})

        obj = object.__new__(cls)
        obj.__init__(pool, pool_obj)
        return obj

    create_instance = classmethod(create_instance)

    def __init__(self, pool, pool_obj):
        if self._name:
            pool.add(self._name, self)
        self.pool = pool_obj
        super(Report, self).__init__()

    def execute(self, cursor, user, ids, datas, context=None):
        action_report_obj = self.pool.get('ir.actions.report')
        action_report_ids = action_report_obj.search(cursor, user, [
            ('report_name', '=', self._name)
            ], context=context)
        action_report = action_report_obj.browse(cursor, user,
                action_report_ids[0], context=context)
        objects = self._get_objects(cursor, user, ids, action_report.model,
                context)
        type, data = self.parse(cursor, user, action_report.report_content,
                objects, datas, context)
        return (type, base64.encodestring(data))

    def _get_objects(self, cursor, user, ids, model, context):
        model_obj = self.pool.get(model)
        context = context.copy()
        if 'lang' in context:
            del context['lang']
        #TODO change list_class
        return model_obj.browse(cursor, user, ids, context=context)

    def parse(self, cursor, user, content, objects, datas, context):
        localcontext = {}
        localcontext['datas'] = datas
        localcontext['objects'] = objects
        localcontext['user'] = self.pool.get('res.user').\
                browse(cursor, user, user)
        localcontext.update(context)
        content_io = StringIO.StringIO(content)
        content_z = zipfile.ZipFile(content_io, mode='r')
        content_xml = content_z.read('content.xml')
        content_z.close()
        dom = xml.dom.minidom.parseString(content_xml)
        node = dom.documentElement
        self._parse_node(cursor, user, node, localcontext, context)
        content_z = zipfile.ZipFile(content_io, mode='a')
        content_z.writestr('content.xml',
                '<?xml version="1.0" encoding="UTF-8"?>' + \
                dom.documentElement.toxml('utf-8'))
        content_z.close()
        data = content_io.getvalue()
        content_io.close()
        return ('odt', data)

    def _parse_node(self, cursor, user, node, localcontext, context,
            node_context = None):
        if node_context is None:
            node_context = {}
        while True:
            if node.hasChildNodes():
                node = node.firstChild
            elif node.nextSibling:
                node = node.nextSibling
            else:
                while node and not node.nextSibling:
                    node = node.parentNode
                if not node:
                    break
                node = node.nextSibling
            if node in node_context:
                localcontext.update(node_context[node])
            if node.nodeType in (node.CDATA_SECTION_NODE, node.TEXT_NODE):
                res = self._parse_text(cursor, user, node, localcontext, context,
                        node_context)
                if isinstance(res, dom.Node):
                    node = res

    def _parse_text(self, cursor, user, node, localcontext, context,
            node_context):
        if node.parentNode.tagName == 'text:text-input':
            localcontext['RepeatIn'] = lambda lst, name, parents=False: \
                    self.repeat_in(lst, name, parents=parents,
                            tnode=node, node_context=node_context)
            localcontext['setTag'] = lambda oldtag, newtag, attrs=None: \
                    self.set_tag(oldtag, newtag, attrs=attrs, tnode=node)
            localcontext['removeParentNode'] = lambda tag='p': \
                    self.remove_parent_node(tag, tnode=node)
            localcontext['setLang'] = lambda lang: \
                    self.set_lang(lang, localcontext)
            localcontext['formatLang'] = lambda value, digits=2, date=False: \
                    self.format_lang(value, digits=digits, date=date,
                            localcontext=localcontext)
            res = eval(node.nodeValue, localcontext)
            if isinstance(res, basestring):
                node.nodeValue = res
                node.parentNode.parentNode.replaceChild(node, node.parentNode)
            return res
        if 'lang' in localcontext:
            lang = localcontext['lang']
            text = node.nodeValue
            if lang and text and not text.isspace():
                translation_obj = self.pool.get('ir.translation')
                new_text = translation_obj._get_source(cursor,
                        self._name, 'rml', lang, text)
                if new_text:
                    node.nodeValue = new_text
        return None

    def repeat_in(self, lst, name, parents=False, tnode=None, node_context=None):
        node = self.find_parent(tnode, parents or PARENTS)

        pnode = node.parentNode
        nextnode = node.nextSibling
        pnode.removeChild(node)
        tnode.parentNode.parentNode.removeChild(tnode.parentNode)

        if not len(lst):
            return pnode
        for i in range(len(lst)):
            newnode = node.cloneNode(1)
            if nextnode:
                pnode.insertBefore(newnode, nextnode)
            else:
                pnode.appendChild(newnode)
            node_context[newnode] = {name: lst[i]}
        return pnode

    def set_tag(self, oldtag, newtag, attrs=None, tnode=None):
        if attrs is None:
            attrs = {}
        node = self.find_parent(tnode, [oldtag])
        if node:
            node.tagName = newtag
            for key, val in attrs.items():
                node.setAttribute(key, val)
        return None

    def remove_parent_node(self, tag='p', tnode=None):
        node = self.find_parent(node, [tag])
        if node:
            pnode = node.parentNode
            pnode.removeChild(node)
            return pnode

    def find_parent(self, node, parents):
        while True:
            if not node.parentNode:
                return None
            node = node.parentNode
            if node.nodeType == node.ELEMENT_NODE \
                    and node.localName in parents:
                break
        return node

    def set_lang(self, lang, localcontext):
        localcontext['lang'] = lang
        return None

    def format_lang(self, value, digits=2, date=False, localcontext=None):
        if localcontext is None:
            localcontext = {}
        encoding = locale.getdefaultlocale()[1]
        if encoding == 'utf':
            encoding = 'UTF-8'
        try:
            locale.setlocale(locale.LC_ALL,
                    (localcontext.get('lang', False) or 'en_US') + \
                            '.' + encoding)
        except Exception:
            Logger().notify_channel('web-service', LOG_ERROR,
                    'Report %s: unable to set locale "%s"' % \
                            (self._name,
                                localcontext.get('lang', False) or 'en_US'))
        if date:
            date = time.strptime(value, '%Y-%m-%d')
            return time.strftime(locale.nl_langinfo(locale.D_FMT).\
                    replace('%y', '%Y'), date)
        return locale.format('%.' + str(digits) + 'f', value, True)
