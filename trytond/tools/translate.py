import os
from os.path import join
import fnmatch
import csv, xml.dom, re
from trytond import pooler
from trytond.netsvc import Logger, LOG_ERROR, LOG_WARNING, LOG_INFO, _SERVICE
from misc import UpdateableStr, file_open, get_languages
from trytond.config import CONFIG


class TINY(csv.excel):
    lineterminator = '\n'

csv.register_dialect("TINY", TINY)

# TODO: a caching method
def translate(cursor, user, name, source_type, lang, source=None):
    if source and name:
        cursor.execute('SELECT value FROM ir_translation ' \
                'WHERE lang = %s AND type = %s AND name = %s AND src = %s',
                (lang, source_type, str(name), source))
    elif name:
        cursor.execute('SELECT value FROM ir_translation ' \
                'WHERE lang = %s AND type = %s AND name = %s',
                (lang, source_type, str(name)))
    elif source:
        cursor.execute('SELECT value FROM ir_translation ' \
                'WHERE lang = %s AND type = %s AND src = %s',
                (lang, source_type, source))
    res_trans = cursor.fetchone()
    res = res_trans and res_trans[0] or False
    return res

def translate_code(cursor, user, source, context):
    lang = context.get('language', False)
    if lang:
        return translate(cursor, user, None, 'code', lang, source)
    else:
        return source

#_ = lambda source: translate_code(cursor, user, source, context)

def trans_parse_view(view):
    res = []
    if view.hasAttribute("string"):
        string = view.getAttribute('string')
        if string:
            res.append(string.encode("utf8"))
    if view.hasAttribute("sum"):
        string = view.getAttribute('sum')
        if string:
            res.append(string.encode("utf8"))
    for child_view in [i for i in view.childNodes \
            if (i.nodeType == i.ELEMENT_NODE)]:
        res.extend(trans_parse_view(child_view))
    return res

# tests whether an object is in a list of modules
def in_modules(object_name, modules):
    if 'all' in modules:
        return True

    module_dict = {
        'ir': 'base',
        'res': 'base',
        'workflow': 'base',
    }
    module = object_name.split('.')[0]
    module = module_dict.get(module, module)
    return module in modules

def trans_generate(lang, modules, dbname=None):
    logger = Logger()
    if not dbname:
        dbname = CONFIG['db_name']
    pool = pooler.get_pool(dbname)
    trans_obj = pool.get('ir.translation')
    model_data_obj = pool.get('ir.model.data')
    cursor = pooler.get_db(dbname).cursor()
    user = 1
    objects = pool.obj_pool.items()
    objects.sort()
    out = [["type", "name", "res_id", "src", "value"]]

    to_translate = []

    # object fields
    for obj_name, obj in objects:
        if in_modules(obj_name, modules):
            for field_name, field_def in obj._columns.iteritems():
                name = obj_name + "," + field_name
                value = ""
                if lang:
                    cursor.execute("SELECT * FROM ir_translation " \
                            "WHERE type = 'field' AND name = %s AND lang = %s",
                            (name, lang))
                    res = cursor.dictfetchall()
                    if len(res):
                        value = res[0]['value']
                out.append(["field", name, "0",
                    field_def.string.encode('utf8'), value])
                if field_def.help:
                    value = ''
                    if lang:
                        cursor.execute('SELECT * FROM ir_translation ' \
                                'WHERE type=\'help\' ' \
                                    'AND name = %s ' \
                                    'AND lang = %s', (name, lang))
                        res = cursor.dictfetchall()
                        if res:
                            value = res[0]['value']
                    out.append(['help', name, '0',
                        field_def.help.encode('utf8'), value])
                if field_def.translate:
                    ids = obj.search(obj, cursor, user, [])
                    obj_values = obj.read(cursor, user, ids, [field_name])
                    for obj_value in obj_values:
                        trans = ""
                        if lang:
                            cursor.execute("SELECT * " \
                                    "FROM ir_translation " \
                                    "WHERE type='model' " \
                                        "AND name=%s AND res_id=%d AND lang=%s",
                                        (name, obj_value['id'], lang))
                            res = cursor.dictfetchall()
                            if len(res):
                                trans = res[0]['value']

                        res_id = obj_value['id']
                        if obj_name in ('ir.model', 'ir.ui.menu'):
                            res_id = 0
                        model_data_ids = model_data_obj.search(cursor, user, [
                            ('model', '=', obj_name),
                            ('res_id', '=', obj_value['id']),
                            ])
                        if model_data_ids:
                            model_data = model_data_obj.browse(cursor, user,
                                    model_data_ids[0])
                            res_id = model_data.module + '.' + model_data.name

                        out.append(["model", name, res_id,
                            obj_value[field_name], trans])
                if hasattr(field_def, 'selection') \
                        and isinstance(field_def.selection, (list, tuple)):
                    for key, val in field_def.selection:
                        to_translate.append(["selection", name,
                            [val.encode('utf8')]])

    # reports (xsl and rml)
    obj = pool.get("ir.actions.report.xml")
    for i in obj.read(cursor, user, obj.search(cursor, user, [])):
        if in_modules(i["model"], modules):
            name = i["report_name"]
            fname = ""
            xmlstr = None
            report_type = None
            parse_func = None
            try:
                xmlstr = file_open(fname).read()
                document = xml.dom.minidom.parseString(xmlstr)
                to_translate.append([report_type, name,
                    parse_func(document.documentElement)])
            except IOError:
                if fname:
                    logger.notify_channel("init", LOG_WARNING,
                            "couldn't export translation for report %s %s %s" %\
                                    (name, report_type, fname))
    # views
    obj = pool.get("ir.ui.view")
    for i in obj.read(cursor, user, obj.search(cursor, user, [])):
        if in_modules(i["model"], modules):
            document = xml.dom.minidom.parseString(i['arch'])
            to_translate.append(["view", i['model'],
                trans_parse_view(document.documentElement)])

    # wizards
    for service_name, obj in _SERVICE.iteritems():
        if service_name.startswith('wizard.'):
            for state_name, state_def in obj.states.iteritems():
                if 'result' in state_def:
                    result = state_def['result']
                    if result['type'] != 'form':
                        continue

                    name = obj.wiz_name + ',' + state_name

                    # export fields
                    for field_name, field_def in result['fields'].iteritems():
                        if 'string' in field_def:
                            source = field_def['string']
                            res_name = name + ',' + field_name
                            to_translate.append(["wizard_field", res_name,
                                [source]])

                    # export arch
                    arch = result['arch']
                    if not isinstance(arch, UpdateableStr):
                        document = xml.dom.minidom.parseString(arch)
                        to_translate.append(["wizard_view", name,
                            trans_parse_view(document.documentElement)])

                    # export button labels
                    for but_args in result['state']:
                        button_name = but_args[0]
                        button_label = but_args[1]
                        res_name = name + ',' + button_name
                        to_translate.append(["wizard_button", res_name,
                            [button_label]])

    # code
    for root, dirs, files in os.walk(CONFIG['root_path']):
        for fname in fnmatch.filter(files, '*.py'):
            frelativepath = join(root, fname)
            code_string = file_open(frelativepath, subdir='').read()

# TODO: add support for """ and '''... These should use the DOTALL flag
# DOTALL
#     Make the "." special character match any character at all, including a
#     newline; without this flag, "." will match anything except a newline.
            # *? is the non-greedy version of the * qualifier
            for i in re.finditer(
                '[^a-zA-Z0-9_]_\([\s]*["\'](.*?)["\'][\s]*\)',
                code_string):
                source = i.group(1).encode('utf8')
# TODO: check whether the same string has already been exported
                res = trans_obj._get_source(cursor, frelativepath, 'code',
                        lang, source) or ''
                out.append(["code", frelativepath, "0", source, res])

    # translate strings marked as to be translated
    for ttype, name, sources in to_translate:
        for source in sources:
            trans = trans_obj._get_source(cursor, name, ttype, lang,
                    source)
            out.append([ttype, name, "0", source, trans or ''])

    cursor.close()
    return out

def trans_load(db_name, filename, lang, strict=False):
    logger = Logger()
    data = ''
    try:
        data = file(filename,'r').read().split('\n')
    except IOError:
        logger.notify_channel("init", LOG_ERROR, "couldn't read file")
    return trans_load_data(db_name, data, lang, strict=strict)

def trans_load_data(db_name, data, lang, strict=False, lang_name=None):
    logger = Logger()
    logger.notify_channel("init", LOG_INFO,
            'loading translation file for language %s' % (lang))
    pool = pooler.get_pool(db_name)
    lang_obj = pool.get('res.lang')
    trans_obj = pool.get('ir.translation')
    model_data_obj = pool.get('ir.model.data')
    try:
        user = 1
        cursor = pooler.get_db(db_name).cursor()

        ids = lang_obj.search(cursor, user, [('code', '=', lang)])
        if not ids:
            if not lang_name:
                lang_name = lang
                languages = get_languages()
                if lang in languages:
                    lang_name = languages[lang]
            ids = lang_obj.create(cursor, user, {
                'code': lang,
                'name': lang_name,
                'translatable': 1,
                })
        else:
            lang_obj.write(cursor, user, ids, {'translatable':1})

        reader = csv.reader(data)
        # read the first line of the file (it contains columns titles)
        for row in reader:
            first = row
            break

        # read the rest of the file
        line = 1
        for row in reader:
            line += 1
            try:
                # skip empty rows and rows where the translation field is empty
                if (not row) or (not row[4]):
                    continue

                # dictionary which holds values for this line of the csv file
                # {'language': ..., 'type': ..., 'name': ..., 'res_id': ...,
                #  'src': ..., 'value': ...}
                dic = {'language': lang}
                for i in range(len(first)):
                    dic[first[i]] = row[i]

                try:
                    dic['res_id'] = int(dic['res_id'])
                except:
                    model_data_ids = model_data_obj.search(cursor, user, [
                        ('model', '=', dic['name'].split(',')[0]),
                        ('module', '=', dic['res_id'].split('.', 1)[0]),
                        ('name', '=', dic['res_id'].split('.', 1)[1]),
                        ])
                    if model_data_ids:
                        dic['res_id'] = model_data_obj.browse(cursor, user,
                                model_data_ids[0]).res_id
                    else:
                        dic['res_id'] = False

                if dic['type'] == 'model' and not strict:
                    (model, field) = dic['name'].split(',')

                    # get the ids of the resources of this model which share
                    # the same source
                    obj = pool.get(model)
                    if obj:
                        obj_ids = obj.search(cursor, user,
                                [(field, '=', dic['src'])])

                        # if the resource id (res_id) is in that list, use it,
                        # otherwise use the whole list
                        obj_ids = (dic['res_id'] in obj_ids) \
                                and [dic['res_id']] or obj_ids
                        for res_id in obj_ids:
                            dic['res_id'] = res_id
                            trans_ids = trans_obj.search(cursor, user, [
                                ('lang', '=', lang),
                                ('type', '=', dic['type']),
                                ('name', '=', dic['name']),
                                ('src', '=', dic['src']),
                                ('res_id', '=', dic['res_id'])
                            ])
                            if trans_ids:
                                trans_obj.write(cursor, user, trans_ids,
                                        {'value': dic['value']})
                            else:
                                trans_obj.create(cursor, user, dic)
                else:
                    trans_ids = trans_obj.search(cursor, user, [
                        ('lang', '=', lang),
                        ('type', '=', dic['type']),
                        ('name', '=', dic['name']),
                        ('src', '=', dic['src'])
                    ])
                    if trans_ids:
                        trans_obj.write(cursor, user, trans_ids,
                                {'value': dic['value']})
                    else:
                        trans_obj.create(cursor, user, dic)
                cursor.commit()
            except Exception, exp:
                logger.notify_channel('init', LOG_ERROR,
                        'Import error: %s on line %d: %s!' % \
                                (str(exp), line, row))
                cursor.rollback()
                cursor.close()
                cursor = pooler.get_db(db_name).cursor()
        cursor.close()
        logger.notify_channel("init", LOG_INFO,
                "translation file loaded succesfully")
    except IOError:
        logger.notify_channel("init", LOG_ERROR, "couldn't read file")
