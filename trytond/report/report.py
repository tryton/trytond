#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Report"
from trytond.netsvc import Service, service_exist, Logger, LOG_ERROR
from trytond import pooler
import copy
import xml
from xml import dom
from xml.dom import minidom
from trytond.osv import ExceptORM, ExceptOSV, OSV
import sys
import base64
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import zipfile
import locale
import time
import os
import datetime

if not hasattr(locale, 'nl_langinfo'):
    locale.nl_langinfo = lambda *a: '%x'

if not hasattr(locale, 'D_FMT'):
    locale.D_FMT = None

MODULE_LIST = []
MODULE_CLASS_LIST = {}
CLASS_POOL = {}
_LOCALE2WIN32 = {
    'af_ZA': 'Afrikaans_South Africa',
    'sq_AL': 'Albanian_Albania',
    'ar_SA': 'Arabic_Saudi Arabia',
    'eu_ES': 'Basque_Spain',
    'be_BY': 'Belarusian_Belarus',
    'bs_BA': 'Serbian (Latin)',
    'bg_BG': 'Bulgarian_Bulgaria',
    'ca_ES': 'Catalan_Spain',
    'hr_HR': 'Croatian_Croatia',
    'zh_CN': 'Chinese_China',
    'zh_TW': 'Chinese_Taiwan',
    'cs_CZ': 'Czech_Czech Republic',
    'da_DK': 'Danish_Denmark',
    'nl_NL': 'Dutch_Netherlands',
    'et_EE': 'Estonian_Estonia',
    'fa_IR': 'Farsi_Iran',
    'ph_PH': 'Filipino_Philippines',
    'fi_FI': 'Finnish_Finland',
    'fr_FR': 'French_France',
    'fr_BE': 'French_France',
    'fr_CH': 'French_France',
    'fr_CA': 'French_France',
    'ga': 'Scottish Gaelic',
    'gl_ES': 'Galician_Spain',
    'ka_GE': 'Georgian_Georgia',
    'de_DE': 'German_Germany',
    'el_GR': 'Greek_Greece',
    'gu': 'Gujarati_India',
    'he_IL': 'Hebrew_Israel',
    'hi_IN': 'Hindi',
    'hu': 'Hungarian_Hungary',
    'is_IS': 'Icelandic_Iceland',
    'id_ID': 'Indonesian_indonesia',
    'it_IT': 'Italian_Italy',
    'ja_JP': 'Japanese_Japan',
    'kn_IN': 'Kannada',
    'km_KH': 'Khmer',
    'ko_KR': 'Korean_Korea',
    'lo_LA': 'Lao_Laos',
    'lt_LT': 'Lithuanian_Lithuania',
    'lat': 'Latvian_Latvia',
    'ml_IN': 'Malayalam_India',
    'id_ID': 'Indonesian_indonesia',
    'mi_NZ': 'Maori',
    'mn': 'Cyrillic_Mongolian',
    'no_NO': 'Norwegian_Norway',
    'nn_NO': 'Norwegian-Nynorsk_Norway',
    'pl': 'Polish_Poland',
    'pt_PT': 'Portuguese_Portugal',
    'pt_BR': 'Portuguese_Brazil',
    'ro_RO': 'Romanian_Romania',
    'ru_RU': 'Russian_Russia',
    'mi_NZ': 'Maori',
    'sr_CS': 'Serbian (Cyrillic)_Serbia and Montenegro',
    'sk_SK': 'Slovak_Slovakia',
    'sl_SI': 'Slovenian_Slovenia',
    'es_ES': 'Spanish_Spain',
    'sv_SE': 'Swedish_Sweden',
    'ta_IN': 'English_Australia',
    'th_TH': 'Thai_Thailand',
    'mi_NZ': 'Maori',
    'tr_TR': 'Turkish_Turkey',
    'uk_UA': 'Ukrainian_Ukraine',
    'vi_VN': 'Vietnamese_Viet Nam',
}



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
            tb_s = reduce(lambda x, y: x+y,
                    traceback.format_exception(*sys.exc_info()))
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
            if module != 'trytond' and module != 'modules':
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
        if context is None:
            context = {}
        action_report_obj = self.pool.get('ir.action.report')
        action_report_ids = action_report_obj.search(cursor, user, [
            ('report_name', '=', self._name)
            ], context=context)
        if not action_report_ids:
            raise ExceptOSV('Error', 'Report (%s) not find!' % self._name)
        action_report = action_report_obj.browse(cursor, user,
                action_report_ids[0], context=context)
        objects = self._get_objects(cursor, user, ids, action_report.model,
                datas, context)
        type, data = self.parse(cursor, user, action_report,
                objects, datas, context)
        return (type, base64.encodestring(data), action_report.direct_print)

    def _get_objects(self, cursor, user, ids, model, datas, context):
        model_obj = self.pool.get(model)
        context = context.copy()
        if 'language' in context:
            del context['language']
        return model_obj.browse(cursor, user, ids, context=context)

    def parse(self, cursor, user, report, objects, datas, context):
        localcontext = {}
        localcontext['datas'] = datas
        localcontext['objects'] = objects
        localcontext['user'] = self.pool.get('res.user').\
                browse(cursor, user, user)
        localcontext['_language_cache'] = {}
        localcontext.update(context)
        if not report.report_content:
            raise ExceptOSV('Error', 'Missing report file!')
        #cStringIO difference:
        #calling StringIO() with a string parameter creates a read-only object
        content_io = StringIO.StringIO()
        content_io.write(report.report_content)
        content_z = zipfile.ZipFile(content_io, mode='r')
        content_xml = content_z.read('content.xml')
        dom = xml.dom.minidom.parseString(content_xml)
        node = dom.documentElement
        self._parse_node(cursor, user, node, localcontext, context)

        style_z = zipfile.ZipFile(content_io, mode='r')
        style_xml = content_z.read('styles.xml')
        style_z.close()
        dom_style = xml.dom.minidom.parseString(style_xml)
        node_style = dom_style.documentElement
        self._parse_node(cursor, user, node_style, localcontext, context)
        content_z.close()

        pictures = []
        if report.style_content:
            #cStringIO difference:
            #calling StringIO() with a string parameter creates a read-only object
            style2_io = StringIO.StringIO()
            style2_io.write(report.style_content)
            style2_z = zipfile.ZipFile(style2_io, mode='r')
            style2_xml = style2_z.read('styles.xml')
            for file in style2_z.namelist():
                if file.startswith('Pictures'):
                    picture = style2_z.read(file)
                    pictures.append((file, picture))
            style2_z.close()
            style2_io.close()
            dom_style2 = xml.dom.minidom.parseString(style2_xml)
            node_style2 = dom_style2.documentElement
            self._parse_node(cursor, user, node_style2, localcontext, context)
            style_header_node2 = self.find(node_style2, 'master-styles')
            style_header_node = self.find(node_style, 'master-styles')
            style_header_node.parentNode.replaceChild(style_header_node2,
                    style_header_node)
            style_header_node2 = self.find(node_style2, 'automatic-styles')
            style_header_node = self.find(node_style, 'automatic-styles')
            style_header_node.parentNode.replaceChild(style_header_node2,
                    style_header_node)

        content_z = zipfile.ZipFile(content_io, mode='a')
        content_z.writestr('content.xml',
                '<?xml version="1.0" encoding="UTF-8"?>' + \
                dom.documentElement.toxml('utf-8'))
        content_z.writestr('styles.xml',
                '<?xml version="1.0" encoding="UTF-8"?>' + \
                        dom_style.documentElement.toxml('utf-8'))
        for file, picture in pictures:
            content_z.writestr(file, picture)
        content_z.close()
        data = content_io.getvalue()
        content_io.close()
        output_format = report.output_format.format
        if output_format == 'pdf':
            data = self.convert_pdf(data)
        return (output_format, data)


    def convert_pdf(self, data):
        """
        Convert report to PDF using OpenOffice.org.
        This requires OpenOffice.org, pyuno and openoffice-python to
        be installed.
        """
        import tempfile
        try:
            import unohelper # installs import-hook
            import openoffice.interact
            import openoffice.officehelper as officehelper
            from openoffice.streams import OutputStream
            from com.sun.star.beans import PropertyValue
        except ImportError, exception:
            raise ExceptOSV('ImportError', str(exception))
        try:
            # connect to OOo
            desktop = openoffice.interact.Desktop()
        except officehelper.BootstrapException:
            raise ExceptOSV('Error', "Can't connect to (bootstrap) OpenOffice.org")

        res_data = None
        # Create temporary file (with name) and write data there.
        # We can not use NamedTemporaryFile here, since this would be
        # deleted as soon as we close it to allow OOo reading.
        #TODO use an input stream here
        fd_odt, odt_name = tempfile.mkstemp()
        fh_odt = os.fdopen(fd_odt, 'wb+')
        try:
            fh_odt.write(data)
            del data # save memory
            fh_odt.close()
            doc = desktop.openFile(odt_name, hidden=False)
            # Export as PDF
            buffer = StringIO.StringIO()
            out_props = (
                PropertyValue("FilterName", 0, "writer_pdf_Export", 0),
                PropertyValue("Overwrite", 0, True, 0),
                PropertyValue("OutputStream", 0, OutputStream(buffer), 0),
                )
            doc.storeToURL("private:stream", out_props)
            res_data = buffer.getvalue()
            del buffer
            doc.dispose()
        finally:
            fh_odt.close()
            os.remove(odt_name)
        if not res_data:
            ExceptOSV('Error', 'Error converting to PDF')
        return res_data

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
            ctx = localcontext.copy()
            ctx.update(context)
            ctx['RepeatIn'] = lambda lst, name, parents=False: \
                    self.repeat_in(lst, name, parents=parents,
                            tnode=node, node_context=node_context)
            ctx['setTag'] = lambda oldtag, newtag, attrs=None: \
                    self.set_tag(oldtag, newtag, attrs=attrs, tnode=node)
            ctx['removeParentNode'] = lambda tag='p': \
                    self.remove_parent_node(tag, tnode=node)
            ctx['setLang'] = lambda lang: \
                    self.set_lang(lang, localcontext)
            ctx['formatLang'] = lambda value, digits=2, date=False: \
                    self.format_lang(value, digits=digits, date=date,
                            localcontext=localcontext)
            ctx['time'] = time
            ctx['datetime'] = datetime
            try:
                res = eval(node.nodeValue, ctx)
            except:
                Logger().notify_channel('report', LOG_ERROR,
                        'Error on eval "%s"' % node.nodeValue)
                raise
            if isinstance(res, bool):
                res = ''
            if hasattr(res, '__str__'):
                res = res.__str__()
            if isinstance(res, basestring):
                if '\n' in res:
                    parent2 = node.parentNode.parentNode
                    parent = node.parentNode
                    first = True
                    newnode = None
                    for val in res.decode('utf-8').split('\n'):
                        if first:
                            newnode = node
                            first = False
                        else:
                            newnode = node.cloneNode(1)
                        newnode.nodeValue = val
                        parent2.insertBefore(newnode, parent)
                        newnode = node.parentNode.cloneNode(1)
                        newnode.nodeType = newnode.ELEMENT_NODE
                        newnode.tagName = 'text:line-break'
                        newnode.firstChild.nodeValue = ''
                        if newnode.getAttribute('text:style-name'):
                            newnode.removeAttribute('text:style-name')
                        parent2.insertBefore(newnode, parent)
                    parent2.removeChild(parent)
                    if newnode:
                        parent2.removeChild(newnode)
                else:
                    node.nodeValue = res.decode('utf-8')
                    node.parentNode.parentNode.replaceChild(node, node.parentNode)
            return res
        if 'language' in localcontext:
            lang = localcontext['language']
            text = node.nodeValue
            if lang and text and not text.isspace():
                translation_obj = self.pool.get('ir.translation')
                new_text = translation_obj._get_source(cursor,
                        self._name, 'odt', lang, text)
                if new_text:
                    node.nodeValue = new_text.decode('utf-8')
        return None

    def repeat_in(self, lst, name, parents=False, tnode=None, node_context=None):
        node = self.find_parent(tnode, parents or PARENTS)

        pnode = node.parentNode
        nextnode = node.nextSibling
        pnode.removeChild(node)
        tnode.parentNode.parentNode.removeChild(tnode.parentNode)

        if not lst:
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
        node = self.find_parent(tnode, [tag])
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

    def find(self, tnode, tag):
        for node in tnode.childNodes:
            if node.nodeType == node.ELEMENT_NODE \
                    and node.localName == tag:
                return node
            res = self.find(node, tag)
            if res is not None:
                return res
        return None

    def set_lang(self, lang, localcontext):
        localcontext['language'] = lang
        _language_cache = localcontext['_language_cache']
        for obj in localcontext['objects']:
            obj._context['language'] = lang
            for table in obj._cache:
                for obj_id in obj._cache[table]:
                    _language_cache.setdefault(
                            obj._context['language'], {}).setdefault(
                                    table, {}).update(
                                            obj._cache[table][obj_id])
                    if lang in _language_cache \
                            and table in _language_cache[lang] \
                            and obj_id in _language_cache[lang][table]:
                        obj._cache[table][obj_id] = \
                                _language_cache[lang][table][obj_id]
                    else:
                        obj._cache[table][obj_id] = {'id': obj_id}
        return ''

    def format_lang(self, value, digits=2, date=False, localcontext=None):
        if localcontext is None:
            localcontext = {}
        encoding = locale.getdefaultlocale()[1]
        if encoding == 'utf':
            encoding = 'UTF-8'
        if encoding == 'cp1252':
            encoding = '1252'
        lang = localcontext.get('language', False) or 'en_US'
        try:
            if os.name == 'nt':
                locale.setlocale(locale.LC_ALL,
                        _LOCALE2WIN32.get(lang, lang) + '.' + encoding)
            else:
                locale.setlocale(locale.LC_ALL, lang + '.' + encoding)
        except Exception:
            Logger().notify_channel('web-service', LOG_ERROR,
                    'Report %s: unable to set locale "%s"' % \
                            (self._name,
                                localcontext.get('language', False) or 'en_US'))
        if date:
            if isinstance(value, time.struct_time):
                locale_format = locale.nl_langinfo(locale.D_FMT)\
                        .replace('%y', '%Y')
                date = value
            else:
                # assume string, parse it
                if len(str(value)) == 10:
                    # length of date like 2001-01-01 is ten
                    # assume format '%Y-%m-%d'
                    locale_format = locale.nl_langinfo(locale.D_FMT)\
                            .replace('%y', '%Y')
                    string_pattern = '%Y-%m-%d'
                else:
                    # assume format '%Y-%m-%d %H:%M:%S'
                    value = str(value)[:19]
                    locale_format = locale.nl_langinfo(locale.D_FMT)\
                            .replace('%y', '%Y') + ' %H:%M:%S'
                    string_pattern = '%Y-%m-%d %H:%M:%S'
                date = time.strptime(str(value), string_pattern)
            return time.strftime(locale_format, date)

        return locale.format('%.' + str(digits) + 'f', value, True)
