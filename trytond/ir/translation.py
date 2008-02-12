"Translation"
import base64
from StringIO import StringIO
import csv
from trytond.osv import fields, OSV, Cacheable
from trytond.wizard import Wizard, WizardOSV
from trytond import tools

TRANSLATION_TYPE = [
    ('field', 'Field'),
    ('model', 'Model'),
    ('odt', 'ODT'),
    ('selection', 'Selection'),
    ('view', 'View'),
    ('wizard_button', 'Wizard Button'),
    ('help', 'Help'),
]

HEADER = ['type', 'name', 'res_id', 'src', 'value', 'fuzzy']


class TRYTON(csv.excel):
    lineterminator = '\n'

csv.register_dialect("TRYTON", TRYTON)


class Translation(OSV, Cacheable):
    "Translation"
    _name = "ir.translation"
    _description = __doc__

    def _get_language(self, cursor, user, context):
        lang_obj = self.pool.get('ir.lang')
        lang_ids = lang_obj.search(cursor, user, [], context=context)
        langs = lang_obj.browse(cursor, user, lang_ids, context=context)
        res = [(lang.code, lang.name) for lang in langs]
        return res

    _columns = {
        'name': fields.Char('Field Name', size=128, required=True),
        'res_id': fields.Integer('Resource ID'),
        'lang': fields.Selection(_get_language, string='Language', size=5),
        'type': fields.Selection(TRANSLATION_TYPE, string='Type', size=16,
            required=True),
        'src': fields.Text('Source'),
        'value': fields.Text('Translation Value'),
        'module': fields.Char('Module', size=128, readonly=True),
        'fuzzy': fields.Boolean('Fuzzy'),
    }
    _defaults = {
        'fuzzy': lambda *a: 0,
    }
    _sql_constraints = [
        ('translation_uniq', 'UNIQUE (name, res_id, lang, type, src)',
            'Translation must be unique'),
    ]
    _sql = """
        CREATE INDEX ir_translation_ltn ON ir_translation (lang, type, name);
        CREATE INDEX ir_translation_res_id ON ir_translation (res_id);
    """

    def _get_ids(self, cursor, name, ttype, lang, ids):
        translations, to_fetch = {}, []
        if name.split(',')[0] == 'ir.model.fields':
            model_fields_obj = self.pool.get('ir.model.fields')
            field_name = name.split(',')[1]
            if field_name == 'field_description':
                ttype = 'field'
            else:
                ttype = 'help'
            for field in model_fields_obj.read(cursor, 1, ids,
                    ['model', 'name']):
                name = field['model'] + ',' + field['name']
                translations[field['id']] = self._get_source(cursor,
                        name, ttype, lang)
            return translations
        for obj_id in ids:
            trans = self.get((lang, name, obj_id))
            if trans is not None:
                translations[obj_id] = trans
            else:
                to_fetch.append(obj_id)
        if to_fetch:
            cursor.execute('SELECT res_id, value ' \
                    'FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type = %s ' \
                        'AND name = %s ' \
                        'AND res_id in (' + \
                            ','.join([str(x) for x in to_fetch]) + ')',
                    (lang, ttype, name))
            for res_id, value in cursor.fetchall():
                self.add((lang, ttype, name, res_id), value)
                translations[res_id] = value
        for res_id in ids:
            if res_id not in translations:
                self.add((lang, ttype, name, res_id), False)
                translations[res_id] = False
        return translations

    def _set_ids(self, cursor, user, name, ttype, lang, ids, value):
        if name.split(',')[0] == 'ir.model.fields':
            model_fields_obj = self.pool.get('ir.model.fields')
            field_name = name.split(',')[1]
            if field_name == 'field_description':
                ttype = 'field'
            else:
                ttype = 'help'
            for field in model_fields_obj.browse(cursor, user, ids):
                name = field.model + ',' + field.name
                ids2 = self.search(cursor, user, [
                    ('lang', '=', lang),
                    ('type', '=', ttype),
                    ('name', '=', name),
                    ])
                if not ids2:
                    self.create(cursor, user, {
                        'name': name,
                        'lang': lang,
                        'type': ttype,
                        'src': field[field_name],
                        'value': value,
                        })
                else:
                    self.write(cursor, user, ids, {
                        'src': field[field_name],
                        'value': value,
                        })
            return len(ids)
        for obj_id in ids:
            ids2 = self.search(cursor, user, [
                ('lang', '=', lang),
                ('type', '=', ttype),
                ('name', '=', name),
                ('res_id', '=', obj_id),
                ])
            if not ids2:
                self.create(cursor, user, {
                    'name': name,
                    'lang': lang,
                    'type': ttype,
                    'res_id': obj_id,
                    'value': value,
                    })
            else:
                self.write(cursor, user, ids2, {
                    'value': value,
                    })
        return len(ids)

    def _get_source(self, cursor, name, ttype, lang, source=None):
        trans = self.get((lang, ttype, name, source))
        if trans is not None:
            return trans

        if source:
            source = source.strip().replace('\n',' ')
            if isinstance(source, unicode):
                source = source.encode('utf8')
            cursor.execute('SELECT value ' \
                    'FROM ir_translation ' \
                    'WHERE lang=%s ' \
                        'AND type=%s ' \
                        'AND name=%s ' \
                        'AND src=%s',
                    (lang, ttype, str(name), source))
        else:
            cursor.execute('SELECT value ' \
                    'FROM ir_translation ' \
                    'WHERE lang=%s ' \
                        'AND type=%s ' \
                        'AND name=%s',
                    (lang, ttype, str(name)))
        res = cursor.fetchone()
        if res:
            self.add((lang, ttype, name, source), res[0])
            return res[0]
        else:
            self.add((lang, ttype, name, source), False)
            return False

    def unlink(self, cursor, user, ids, context=None):
        self.clear()
        return super(Translation, self).unlink(cursor, user, ids,
                context=context)

    def create(self, cursor, user, vals, context=None):
        self.clear()
        if vals.get('type', '') in ('odt', 'view', 'wizard_button',
                'selection'):
            cursor.execute('SELECT module FROM ir_translation ' \
                    'WHERE name = %s ' \
                        'AND res_id = %d ' \
                        'AND lang = %s ' \
                        'AND type = %s ' \
                        'AND src = %s ',
                    (vals.get('name', ''), vals.get('res_id', 0), 'en_US',
                        vals.get('type', ''), vals.get('src', '')))
            if cursor.rowcount:
                vals = vals.copy()
                vals['module'] = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT module, src FROM ir_translation ' \
                    'WHERE name = %s ' \
                        'AND res_id = %d ' \
                        'AND lang = %s ' \
                        'AND type = %s',
                    (vals.get('name', ''), vals.get('res_id', 0), 'en_US',
                        vals.get('type', '')))
            if cursor.rowcount:
                vals = vals.copy()
                vals['module'], vals['src'] = cursor.fetchone()
        return super(Translation, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        self.clear()
        return super(Translation, self).write(cursor, user, ids, vals,
                context=context)

    def translation_import(self, cursor, user, lang, module, datas,
            context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['module'] = module
        model_data_obj = self.pool.get('ir.model.data')
        model_data_ids = model_data_obj.search(cursor, user, [
            ('module', '=', module),
            ], context=context)
        fs_id2db_id = {}
        for model_data in model_data_obj.browse(cursor, user, model_data_ids,
                context=context):
            fs_id2db_id.setdefault(model_data.model, {})
            fs_id2db_id[model_data.model][model_data.fs_id] = model_data.db_id

        translation_ids = []
        reader = csv.reader(datas)
        for row in reader:
            break
        for row in reader:
            ttype = row[0]
            name = row[1]
            res_id = row[2]
            src = row[3]
            value = row[4]
            fuzzy = int(row[5])

            model = name.split(',')[0]
            if model in fs_id2db_id:
                res_id = fs_id2db_id[model].get(res_id, res_id)

            if ttype in ('odt', 'view', 'wizard_button', 'selection'):
                ids = self.search(cursor, user, [
                    ('name', '=', name),
                    ('res_id', '=', int(res_id)),
                    ('lang', '=', lang),
                    ('type', '=', ttype),
                    ('src', '=', src),
                    ], context=context)
            elif ttype in('field', 'model','help'):
                ids = self.search(cursor, user, [
                    ('name', '=', name),
                    ('res_id', '=', int(res_id)),
                    ('lang', '=', lang),
                    ('type', '=', ttype),
                    ], context=context)

            if not ids:
                translation_ids.append(self.create(cursor, user, {
                    'name': name,
                    'res_id': int(res_id),
                    'lang': lang,
                    'type': ttype,
                    'src': src,
                    'value': value,
                    'fuzzy': fuzzy,
                    }, context=ctx))
            else:
                cursor.execute('SELECT id FROM ir_translation ' \
                        'WHERE (write_uid IS NULL OR write_uid = 0) ' \
                            'AND id IN ' \
                                '(' + ','.join(['%d' for x in ids]) + ')',
                        ids)
                ids2 = [x[0] for x in cursor.fetchall()]
                if ids2:
                    self.write(cursor, user, ids2, {
                        'value': value,
                        'fuzzy': fuzzy,
                        }, context=ctx)
                translation_ids += ids

        cursor.execute('DELETE FROM ir_translation ' \
                'WHERE module = %s ' \
                    'AND lang = %s ' \
                    'AND id NOT IN ' \
                        '(' + ','.join(['%s' for x in translation_ids]) + ')',
                (module, lang) + tuple(translation_ids))
        return len(translation_ids)

    def translation_export(self, cursor, user, lang, module, context=None):
        model_data_obj = self.pool.get('ir.model.data')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('module', '=', module),
            ], context=context)
        db_id2fs_id = {}
        for model_data in model_data_obj.browse(cursor, user, model_data_ids,
                context=context):
            db_id2fs_id.setdefault(model_data.model, {})
            db_id2fs_id[model_data.model][model_data.db_id] = model_data.fs_id

        buf = StringIO()
        writer = csv.writer(buf, 'TRYTON')
        writer.writerow(HEADER)

        translation_ids = self.search(cursor, user, [
            ('lang', '=', lang),
            ('module', '=', module),
            ], order="type, name, src, res_id", context=context)
        for translation in self.browse(cursor, user, translation_ids,
                context=context):
            row = []
            for field in HEADER:
                if field == 'res_id':
                    res_id = translation[field]
                    if res_id:
                        model = translation.name.split(',')[0]
                        if model in db_id2fs_id:
                            res_id = db_id2fs_id[model].get(res_id, res_id)
                    row.append(res_id)
                else:
                    row.append(translation[field])
            writer.writerow(row)

        file_data = buf.getvalue()
        buf.close()
        return file_data

Translation()


class TranslationUpdateInit(WizardOSV):
    "Update translation - language"
    _name = 'ir.translation.update.init'
    _description = __doc__

    def _get_language(self, cursor, user, context):
        lang_obj = self.pool.get('ir.lang')
        lang_ids = lang_obj.search(cursor, user, [('translatable', '=', True)],
                context=context)
        langs = lang_obj.browse(cursor, user, lang_ids, context=context)
        res = [(lang.code, lang.name) for lang in langs if lang.code != 'en_US']
        return res

    _columns = {
        'lang': fields.Selection(_get_language, string='Language', size=5,
            required=True),
    }

TranslationUpdateInit()


class TranslationUpdate(Wizard):
    "Update translation"
    _name = "ir.translation.update"

    def _update_translation(self, cursor, user, data, context):
        translation_obj = self.pool.get('ir.translation')
        cursor.execute('SELECT name, res_id, type, src ' \
                'FROM ir_translation ' \
                'WHERE lang=\'en_US\' ' \
                    'AND type in (\'odt\', \'view\', \'wizard_button\', ' \
                    ' \'selection\') ' \
                'EXCEPT SELECT name, res_id, type, src ' \
                'FROM ir_translation ' \
                'WHERE lang=%s ' \
                    'AND type in (\'odt\', \'view\', \'wizard_button\', ' \
                    ' \'selection\')',
                (data['form']['lang'],))
        for row in cursor.dictfetchall():
            translation_obj.create(cursor, user, {
                'name': row['name'],
                'res_id': row['res_id'],
                'lang': data['form']['lang'],
                'type': row['type'],
                'src': row['src'],
                })
        cursor.execute('SELECT name, res_id, type ' \
                'FROM ir_translation ' \
                'WHERE lang=\'en_US\' ' \
                    'AND type in (\'field\', \'model\', \'help\') ' \
                'EXCEPT SELECT name, res_id, type ' \
                'FROM ir_translation ' \
                'WHERE lang=%s ' \
                    'AND type in (\'field\', \'model\', \'help\')',
                (data['form']['lang'],))
        for row in cursor.dictfetchall():
            translation_obj.create(cursor, user, {
                'name': row['name'],
                'res_id': row['res_id'],
                'lang': data['form']['lang'],
                'type': row['type'],
                })
        cursor.execute('SELECT name, res_id, type, src ' \
                'FROM ir_translation ' \
                'WHERE lang=\'en_US\' ' \
                    'AND type in (\'field\', \'model\', \'selection\', ' \
                        '\'help\') ' \
                'EXCEPT SELECT name, res_id, type, src ' \
                'FROM ir_translation ' \
                'WHERE lang=%s ' \
                    'AND type in (\'field\', \'model\', \'selection\', ' \
                        '\'help\')',
                (data['form']['lang'],))
        for row in cursor.dictfetchall():
            cursor.execute('UPDATE ir_translation ' \
                    'SET fuzzy = True, ' \
                        'src = %s ' \
                    'WHERE name = %s ' \
                        'AND res_id = %d ' \
                        'AND type = %s ' \
                        'AND lang = %s',
                    (row['src'], row['name'], row['res_id'], row['type'],
                        data['form']['lang']))
        cursor.execute('UPDATE ir_translation ' \
                'SET fuzzy = False ' \
                'WHERE (value = \'\' OR value IS NULL) ' \
                    'AND lang = %s', (data['form']['lang'],))
        return {}

    def _action_translation_open(self, cursor, user, data, context):
        return {
            'domain': str([('lang', '=', data['form']['lang'])]),
            'name': 'Translations',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'ir.translation',
            'view_id': False,
            'type': 'ir.action.act_window',
        }

    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'ir.translation.update.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('start', 'Start Upgrade','gtk-ok', True),
                ],
            },
        },
        'start': {
            'actions': [_update_translation],
            'result': {
                'type': 'action',
                'action': _action_translation_open,
                'state': 'end',
            },
        },
    }

TranslationUpdate()


class TranslationExportInit(WizardOSV):
    "Export translation - language and module"
    _name = 'ir.translation.export.init'
    _description = __doc__

    def _get_language(self, cursor, user, context):
        lang_obj = self.pool.get('ir.lang')
        lang_ids = lang_obj.search(cursor, user, [], context=context)
        langs = lang_obj.browse(cursor, user, lang_ids, context=context)
        res = [(lang.code, lang.name) for lang in langs]
        return res

    def _get_module(self, cursor, user, context):
        module_obj = self.pool.get('ir.module.module')
        module_ids = module_obj.search(cursor, user, [], context=context)
        modules = module_obj.browse(cursor, user, module_ids, context=context)
        res =  [(module.name, module.shortdesc or module.name) \
                for module in modules]
        return res

    _columns = {
        'lang': fields.Selection(_get_language, string='Language', size=5,
            required=True),
        'module': fields.Selection(_get_module, string='Module', size=128,
            required=True),
    }

TranslationExportInit()


class TranslationExportStart(WizardOSV):
    "Export translation - file"
    _description = __doc__
    _name = 'ir.translation.export.start'
    _columns = {
        'file': fields.Binary('File', readonly=True),
    }

TranslationExportStart()


class TranslationExport(Wizard):
    "Export translation"
    _name = "ir.translation.export"

    def _export_translation(self, cursor, user, data, context):
        translation_obj = self.pool.get('ir.translation')
        file_data = translation_obj.translation_export(cursor, user,
                data['form']['lang'], data['form']['module'], context=context)
        return {
            'file': base64.encodestring(file_data),
        }

    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'ir.translation.export.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('start', 'Start Export', 'gtk-ok', True),
                ],
            },
        },
        'start': {
            'actions': [_export_translation],
            'result': {
                'type': 'form',
                'object': 'ir.translation.export.start',
                'state': [
                    ('end', 'Close', 'gtk-close'),
                ],
            },
        },
    }

TranslationExport()
