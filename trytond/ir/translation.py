"Translation"
from trytond.osv import fields, OSV, Cacheable
from trytond import tools

TRANSLATION_TYPE = [
    ('field', 'Field'),
    ('model', 'Model'),
    ('rml', 'RML'),
    ('selection', 'Selection'),
    ('view', 'View'),
    ('wizard_button', 'Wizard Button'),
    ('wizard_field', 'Wizard Field'),
    ('wizard_view', 'Wizard View'),
    ('xsl', 'XSL'),
    ('help', 'Help'),
]

class Translation(OSV, Cacheable):
    "Translation"
    _name = "ir.translation"
    _log_access = False
    _description = __doc__

    def _get_language(self, cursor, user, context):
        lang_obj = self.pool.get('res.lang')
        lang_ids = lang_obj.search(cursor, user, [('translatable', '=', True)],
                context=context)
        langs = lang_obj.browse(cursor, user, lang_ids, context=context)
        res = [(lang.code, lang.name) for lang in langs]
        for lang_dict in tools.scan_languages():
            if lang_dict not in res:
                res.append(lang_dict)
        return res

    _columns = {
        'name': fields.char('Field Name', size=128, required=True),
        'res_id': fields.integer('Resource ID'),
        'lang': fields.selection(_get_language, string='Language', size=5),
        'type': fields.selection(TRANSLATION_TYPE, string='Type', size=16),
        'src': fields.text('Source'),
        'value': fields.text('Translation Value'),
    }
    _sql = """
        CREATE INDEX ir_translation_ltn ON ir_translation (lang, type, name);
        CREATE INDEX ir_translation_res_id ON ir_translation (res_id);
    """

    def _get_ids(self, cursor, name, ttype, lang, ids):
        translations, to_fetch = {}, []
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
        cursor.execute('DELETE FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name = %s ' \
                    'AND res_id IN (' + ','.join([str(x) for x in ids]) + ')',
                (lang, ttype, name))
        for obj_id in ids:
            self.create(cursor, user, {
                'lang': lang,
                'type': ttype,
                'name': name,
                'res_id': obj_id,
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
            cursor.execute('select value ' \
                    'from ir_translation ' \
                    'where lang=%s ' \
                        'and type=%s ' \
                        'and name=%s ' \
                        'and src=%s',
                    (lang, ttype, str(name), source))
        else:
            cursor.execute('select value ' \
                    'from ir_translation ' \
                    'where lang=%s ' \
                        'and type=%s ' \
                        'and name=%s',
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
        return super(Translation, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        self.clear()
        return super(Translation, self).write(cursor, user, ids, vals,
                context=context)

Translation()
