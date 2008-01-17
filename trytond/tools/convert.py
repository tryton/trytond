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

CDATA_START = re.compile('^\s*\<\!\[cdata\[', re.IGNORECASE)
CDATA_END = re.compile('\]\]\>\s*$', re.IGNORECASE)

# TODO :
# Add some exception helper, and give a good diagnostic for the errors


from xml import sax


class DummyTagHandler:
    """Dubhandler implementing empty methods. Will be used when whe
    want to ignore the xml content"""

    def __init__(self):
        pass

    def startElement(self, name, attributes):
        pass

    def characters(self, data):
        pass

    def endElement(self, name):
        pass


class MenuitemTagHandler:
    """Taghandler for the tag <record> """
    def __init__(self, master_handler):
        self.mh = master_handler

    def startElement(self, name, attributes):

        values = {}

        self.xml_id = attributes['id']

        for attr in ('name', 'icon', 'sequence', 'parent_id', 'action',):
            if attributes.get(attr):
                values[attr] = attributes.get(attr).encode('utf8')


        if values.get('parent_id'):
            values['parent_id'] = self.mh.get_id(values['parent_id'])

        action_name = False
        if values.get('action'):
            action_id = self.mh.get_id(values['action'])

            # TODO maybe use a prefetch for this:
            self.mh.cursor.execute(
            "SELECT a.name, a.type, act.view_type, v.type " \
            "FROM ir_action a " \
                "LEFT JOIN ir_action_report report ON (a.id = report.action) " \
                "LEFT JOIN ir_action_act_window act ON (a.id = act.action) " \
                "LEFT JOIN ir_action_wizard wizard ON (a.id = wizard.action) " \
                "LEFT JOIN ir_action_url url ON (a.id = url.action) " \
                "LEFT JOIN ir_action_act_window_view wv on (act.id = wv.act_window_id) " \
                "LEFT JOIN ir_ui_view v on (v.id = wv.view_id) " \
            "WHERE report.id = %d " \
                "OR act.id = %d " \
                "OR wizard.id = %d " \
                "OR url.id = %d " \
            "ORDER by wv.sequence " \
            "LIMIT 1", (action_id, action_id, action_id, action_id))
            action_name, action_type, view_type, view_mode = \
                self.mh.cursor.fetchone()

            values['action'] = '%s,%d' % (action_type, action_id)

            icon = attributes.get('icon', '').encode('utf8')
            if icon:
                values['icon'] = icon
            elif action_type == 'ir.action.wizard':
                values['icon'] = 'STOCK_EXECUTE'
            elif action_type == 'ir.action.report':
                values['icon'] = 'STOCK_PRINT'
            elif action_type == 'ir.action.act_window':
                if view_type == 'tree':
                    values['icon'] = 'STOCK_INDENT'
                elif view_mode and view_mode.startswith('tree'):
                    values['icon'] = 'STOCK_JUSTIFY_FILL'
                elif view_mode and view_mode.startswith('form'):
                    values['icon'] = 'STOCK_NEW'
                elif view_mode and view_mode.startswith('graph'):
                    values['icon'] = 'terp-graph'
                elif view_mode and view_mode.startswith('calendar'):
                    values['icon'] = 'terp-calendar'
            else:
                values['icon'] = 'STOCK_NEW'

        if not values.get('name'):
            if not action_name:
                raise Exception("Please provide at least a 'name' attributes "
                                "or a 'action' attributes on the menuitem tags.")
            else:
                values['name'] = action_name

        self.values = values


    def characters(self, data):
        pass

    def endElement(self, name):
        """Must return the object to use for the next call """
        if name != "menuitem":
            return self
        else:

            res = self.mh.pool.get('ir.model.data').import_record(
                self.mh.cursor, self.mh.user,
                'ir.ui.menu', self.mh.module, self.values, self.xml_id)
            return None


class RecordTagHandler:

    """Taghandler for the tag <record> and all the tags inside it"""

    def __init__(self, master_handler):
        # Remind reference of parent handler
        self.mh = master_handler


    def startElement(self, name, attributes):

        # Manage the top level tag
        if name == "record":
            self.model = self.mh.pool.get(attributes["model"].encode('utf8'))
            assert self.model, "The model %s does not exist !" % \
                    (attributes["model"].encode('utf8'),)

            self.xml_id = attributes["id"].encode('utf8')

            # create/update a dict containing fields values
            self.values = {}

            self.current_field = None
            self.cdata = False

            return self.xml_id

        # Manage included tags:
        elif name == "field":

            field_name = attributes['name'].encode('utf8')
            # Create a new entry in the values
            self.values[field_name] = ""
            # Remind the current name (see characters)
            self.current_field = field_name
            # Put a flag to escape cdata tags
            if field_name == "arch":
                self.cdata = "start"

            # Catch the known attributes
            search_attr = attributes.get('search','').encode('utf8')
            ref_attr = attributes.get('ref', '').encode('utf8')
            eval_attr = attributes.get('eval', '').encode('utf8')

            if search_attr:
                answer = f_obj.browse(
                    cursor, self.mh.user,
                    model.search(self.mh.cursor,self.mh.user, search_attr))

                if not answer: return

                if field_name in model._columns:
                    if model._columns[field_name]._type == 'many2many':
                        self.values[field_name] = [(6, 0, [x['id'] for x in answer])]

                    elif model._columns[field_name]._type == 'many2one':
                        self.values[field_name] = answer[0]['id']

            elif ref_attr:
                self.values[field_name] = self.mh.get_id(ref_attr)

            elif eval_attr:

                import time
                context = {}
                context['time'] = time
                context['version'] = VERSION.rsplit('.', 1)[0]
                context['ref'] = self.mh.get_id
                context['obj'] = lambda *a: 1
                try:
                    import pytz
                except:
                    Logger().notify_channel("init", LOG_INFO,
                            'could not find pytz library')
                    class Pytz(object):
                        all_timezones = []

                    pytz = Pytz()
                    context['pytz'] = pytz
                self.values[field_name] = eval(eval_attr, context)

        else:
            raise Exception("Tags '%s' not supported inside tag record."% (name,))

    def characters(self, data):

        """If whe are in a field tag, consume all the content"""

        if not self.current_field:
            return
        # Escape start cdata tag if necessary
        if self.cdata == "start":
            data = CDATA_START.sub('', data)
            self.start_cdata = "inside"

        self.values[self.current_field] += data.encode('utf8')


    def endElement(self, name):

        """Must return the object to use for the next call, if name is
        not 'record' we return self to keep our hand on the
        process. If name is 'record' we return None to end the
        delegation"""

        if name == "field":
            if not self.current_field:
                raise Exception("Application error"
                                "current_field expected to be set.")
            # Escape end cdata tag :
            if self.cdata == 'inside':
                self.values[self.current_field] =\
                    CDATA_END.sub('', self.values[self.current_field])
                self.cdata = 'done'

            self.current_field = None
            return self

        elif name == "record":
            res = self.mh.pool.get('ir.model.data').import_record(
                self.mh.cursor, self.mh.user,
                self.model._name, self.mh.module, self.values, self.xml_id)

            return None
        else:
            raise Exception("Unexpected closing tag '%s'"% (name,))


class TrytondXmlHandler(sax.handler.ContentHandler):

    def __init__(self, cursor, pool, module,):
        "Register known taghandlers, and manged tags."

        self.pool = pool
        self.cursor = cursor
        self.user = 1
        self.module = module


        # Tag handlders are used to delegate the processing
        self.taghandlerlist = {
            'record': RecordTagHandler(self),
            'menuitem': MenuitemTagHandler(self),
            }
        self.taghandler = None

        # Managed tags are handled by the current class
        self.managedtags= ["data", "tryton"]
        self.idlist = []


    def get_id(self, xml_id):

        module = self.module
        if '.' in xml_id:
            module, xml_id = xml_id.split('.')

        return self.pool.get('ir.model.data').get_id(
            self.cursor, self.user, module, xml_id)

    def startElement(self, name, attributes):
        """Rebind the current handler if necessary and call
        startElement on it"""

        if not self.taghandler:

            if  name in self.taghandlerlist:
                self.taghandler = self.taghandlerlist[name]
                xml_id = self.taghandler.startElement(name, attributes)
                if xml_id : self.idlist.append(xml_id)

            elif name == "data":
                self.noupdate = attributes.get("noupdate", False)

            elif name == "tryton":
                pass

            else:
                Logger().notify_channel("init", LOG_INFO,
                            "Tag", name , "not supported")
                return
        else:
            self.taghandler.startElement(name, attributes)

    def characters(self, data):
        if self.taghandler:
            self.taghandler.characters(data)

    def endElement(self, name):

        # Closing tag found, if we are in a delegation the handler
        # tell us what to do:
        if self.taghandler:
            self.taghandler = self.taghandler.endElement(name)


def convert_xml_import_sax(cursor, module, xmlstream):

    parser = sax.make_parser()
    # Tell the parser we are not interested in XML namespaces
    parser.setFeature(sax.handler.feature_namespaces, 0)

    handler = TrytondXmlHandler(
        cursor=cursor,
        pool=pooler.get_pool(cursor.dbname),
        module=module,
        )

    parser.setContentHandler(handler)
    source = sax.InputSource()
    source.setByteStream(xmlstream)

    parser.parse(source)

    return True


# use  convert_xml_import_sax or convert_xml_import_dom
convert_xml_import = convert_xml_import_sax
