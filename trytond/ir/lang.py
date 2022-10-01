# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from ast import literal_eval
from decimal import Decimal
from locale import CHAR_MAX

from sql import Table

from trytond.cache import Cache
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model import (
    Check, DeactivableMixin, ModelSQL, ModelView, Unique, fields)
from trytond.modules import create_graph, load_translations
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

Transaction.cache_keys.add('translate_name')


class GroupingError(UserError):
    pass


class DateError(UserError):
    pass


class TranslatableError(UserError):
    pass


class DeleteDefaultError(UserError):
    pass


class Lang(DeactivableMixin, ModelSQL, ModelView):
    "Language"
    __name__ = "ir.lang"
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True, help="RFC 4646 tag.")
    translatable = fields.Boolean('Translatable', readonly=True)
    parent = fields.Char("Parent Code", help="Code of the exceptional parent")
    direction = fields.Selection([
            ('ltr', 'Left-to-right'),
            ('rtl', 'Right-to-left'),
            ], 'Direction', required=True)

    # date
    date = fields.Char("Date", required=True, strip=False)

    am = fields.Char("AM", strip=False)
    pm = fields.Char("PM", strip=False)

    # number
    grouping = fields.Char('Grouping', required=True)
    decimal_point = fields.Char(
        "Decimal Separator", required=True, strip=False)
    thousands_sep = fields.Char("Thousands Separator", strip=False)

    # monetary formatting
    mon_grouping = fields.Char('Grouping', required=True)
    mon_decimal_point = fields.Char(
        "Decimal Separator", required=True, strip=False)
    mon_thousands_sep = fields.Char('Thousands Separator')
    p_sign_posn = fields.Integer('Positive Sign Position', required=True)
    n_sign_posn = fields.Integer('Negative Sign Position', required=True)
    positive_sign = fields.Char("Positive Sign", strip=False)
    negative_sign = fields.Char("Negative Sign", strip=False)
    p_cs_precedes = fields.Boolean('Positive Currency Symbol Precedes')
    n_cs_precedes = fields.Boolean('Negative Currency Symbol Precedes')
    p_sep_by_space = fields.Boolean('Positive Separate by Space')
    n_sep_by_space = fields.Boolean('Negative Separate by Space')

    pg_text_search = fields.Char(
        "PostgreSQL Text Search Configuration", readonly=True)

    _lang_cache = Cache('ir.lang')
    _code_cache = Cache('ir.lang.code', context=False)

    @classmethod
    def __setup__(cls):
        super(Lang, cls).__setup__()

        table = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Unique(table, table.code),
                'ir.msg_language_code_unique'),
            ('check_decimal_point_thousands_sep',
                Check(table, table.decimal_point != table.thousands_sep),
                'decimal_point and thousands_sep must be different!'),
            ]
        cls._buttons.update({
                'load_translations': {},
                'unload_translations': {
                    'invisible': ~Eval('translatable', False),
                    },
                })

    @classmethod
    def search_rec_name(cls, name, clause):
        langs = cls.search([('code',) + tuple(clause[1:])], order=[])
        if langs:
            langs += cls.search([('name',) + tuple(clause[1:])], order=[])
            return [('id', 'in', [l.id for l in langs])]
        return [('name',) + tuple(clause[1:])]

    @classmethod
    def read(cls, ids, fields_names):
        pool = Pool()
        Translation = pool.get('ir.translation')
        Config = pool.get('ir.configuration')
        res = super(Lang, cls).read(ids, fields_names)
        if (Transaction().context.get('translate_name')
                and (not fields_names or 'name' in fields_names)):
            with Transaction().set_context(
                    language=Config.get_language(),
                    translate_name=False):
                res2 = cls.read(ids, ['id', 'code', 'name'])
            for record2 in res2:
                for record in res:
                    if record['id'] == record2['id']:
                        break
                res_trans = Translation.get_ids(cls.__name__ + ',name',
                        'model', record2['code'], [record2['id']])
                record['name'] = (res_trans.get(record2['id'], False)
                    or record2['name'])
        return res

    @staticmethod
    def default_translatable():
        return False

    @staticmethod
    def default_direction():
        return 'ltr'

    @staticmethod
    def default_date():
        return '%m/%d/%Y'

    @staticmethod
    def default_grouping():
        return '[]'

    @staticmethod
    def default_decimal_point():
        return '.'

    @staticmethod
    def default_thousands_sep():
        return ','

    @classmethod
    def default_mon_grouping(cls):
        return '[]'

    @classmethod
    def default_mon_thousands_sep(cls):
        return ','

    @classmethod
    def default_mon_decimal_point(cls):
        return '.'

    @classmethod
    def default_p_sign_posn(cls):
        return 1

    @classmethod
    def default_n_sign_posn(cls):
        return 1

    @classmethod
    def default_negative_sign(cls):
        return '-'

    @classmethod
    def default_positive_sign(cls):
        return ''

    @classmethod
    def default_p_cs_precedes(cls):
        return True

    @classmethod
    def default_n_cs_precedes(cls):
        return True

    @classmethod
    def default_p_sep_by_space(cls):
        return False

    @classmethod
    def default_n_sep_by_space(cls):
        return False

    @classmethod
    @ModelView.button
    def load_translations(cls, languages):
        pool = Pool()
        Module = pool.get('ir.module')
        codes = set()
        cls.write(languages, {'translatable': True})
        for language in languages:
            code = language.code
            while code:
                codes.add(code)
                code = get_parent_language(code)
        modules = Module.search([
                    ('state', '=', 'activated'),
                    ])
        modules = [m.name for m in modules]
        for node in create_graph(modules):
            load_translations(pool, node, codes)

    @classmethod
    @ModelView.button
    def unload_translations(cls, languages):
        pool = Pool()
        Translation = pool.get('ir.translation')
        cls.write(languages, {'translatable': False})
        languages = [l.code for l in languages]
        Translation.delete(Translation.search([
                    ('lang', 'in', languages),
                    ('module', '!=', None),
                    ]))

    @classmethod
    def validate_fields(cls, languages, field_names):
        super().validate_fields(languages, field_names)
        cls.check_grouping(languages, field_names)
        cls.check_date(languages, field_names)
        cls.check_translatable(languages)

    @classmethod
    def check_grouping(cls, langs, fields_names=None):
        '''
        Check if grouping is list of numbers
        '''
        if fields_names and not (fields_names & {'grouping', 'mon_grouping'}):
            return
        for lang in langs:
            for grouping in [lang.grouping, lang.mon_grouping]:
                try:
                    grouping = literal_eval(grouping)
                    for i in grouping:
                        if not isinstance(i, int):
                            raise
                except Exception:
                    raise GroupingError(
                        gettext('ir.msg_language_invalid_grouping',
                            grouping=grouping,
                            language=lang.rec_name))

    @classmethod
    def check_date(cls, langs, field_names=None):
        '''
        Check the date format
        '''
        if field_names and 'date' not in field_names:
            return
        for lang in langs:
            date = lang.date
            try:
                datetime.datetime.now().strftime(date)
            except Exception:
                raise DateError(gettext('ir.msg_language_invalid_date',
                        format=lang.date,
                        language=lang.rec_name))
            if (('%Y' not in lang.date)
                    or ('%b' not in lang.date
                        and '%B' not in lang.date
                        and '%m' not in lang.date
                        and '%-m' not in lang.date)
                    or ('%d' not in lang.date
                        and '%-d' not in lang.date
                        and '%j' not in lang.date
                        and '%-j' not in lang.date)
                    or ('%x' in lang.date
                        or '%X' in lang.date
                        or '%c' in lang.date
                        or '%Z' in lang.date)):
                raise DateError(gettext(
                        'ir.msg_language_invalid_date',
                        format=lang.date,
                        language=lang.rec_name))

    @classmethod
    def check_translatable(cls, langs, field_names=None):
        pool = Pool()
        Config = pool.get('ir.configuration')
        if field_names and 'translatable' not in field_names:
            return
        # Skip check for root because when languages are created from XML file,
        # translatable is not yet set.
        if Transaction().user == 0:
            return True
        for lang in langs:
            if (lang.code == Config.get_language()
                    and not lang.translatable):
                raise TranslatableError(
                    gettext('ir.msg_language_default_translatable',
                        language=lang.rec_name))

    @staticmethod
    def check_xml_record(langs, values):
        return True

    @classmethod
    def get_translatable_languages(cls):
        res = cls._lang_cache.get('translatable_languages')
        if res is None:
            langs = cls.search([
                    ('translatable', '=', True),
                    ])
            res = [x.code for x in langs]
            cls._lang_cache.set('translatable_languages', res)
        return res

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Translation = pool.get('ir.translation')
        # Clear cache
        cls._lang_cache.clear()
        languages = super(Lang, cls).create(vlist)
        Translation._get_language_cache.clear()
        _parents.clear()
        return languages

    @classmethod
    def write(cls, langs, values, *args):
        pool = Pool()
        Translation = pool.get('ir.translation')
        # Clear cache
        cls._lang_cache.clear()
        cls._code_cache.clear()
        super(Lang, cls).write(langs, values, *args)
        Translation._get_language_cache.clear()
        _parents.clear()

    @classmethod
    def delete(cls, langs):
        pool = Pool()
        Config = pool.get('ir.configuration')
        Translation = pool.get('ir.translation')
        for lang in langs:
            if lang.code == Config.get_language():
                raise DeleteDefaultError(
                    gettext('ir.msg_language_delete_default',
                        language=lang.rec_name))
        # Clear cache
        cls._lang_cache.clear()
        cls._code_cache.clear()
        super(Lang, cls).delete(langs)
        Translation._get_language_cache.clear()
        _parents.clear()

    @classmethod
    def get(cls, code=None):
        "Return language instance for the code or the transaction language"
        if code is None:
            code = Transaction().language
        lang_id = cls._code_cache.get(code)
        if not lang_id:
            with Transaction().set_context(active_test=False):
                lang, = cls.search([
                        ('code', '=', code),
                        ])
            cls._code_cache.set(code, lang.id)
        else:
            lang = cls(lang_id)
        return lang

    def _group(self, s, monetary=False):
        # Code from _group in locale.py

        # Iterate over grouping intervals
        def _grouping_intervals(grouping):
            last_interval = 0
            for interval in grouping:
                # if grouping is -1, we are done
                if interval == CHAR_MAX:
                    return
                # 0: re-use last group ad infinitum
                if interval == 0:
                    while True:
                        yield last_interval
                yield interval
                last_interval = interval

        if monetary:
            thousands_sep = self.mon_thousands_sep
            grouping = literal_eval(self.mon_grouping)
        else:
            thousands_sep = self.thousands_sep
            grouping = literal_eval(self.grouping)
        if not grouping:
            return (s, 0)
        if s[-1] == ' ':
            stripped = s.rstrip()
            right_spaces = s[len(stripped):]
            s = stripped
        else:
            right_spaces = ''
        left_spaces = ''
        groups = []
        for interval in _grouping_intervals(grouping):
            if not s or s[-1] not in "0123456789":
                # only non-digit characters remain (sign, spaces)
                left_spaces = s
                s = ''
                break
            groups.append(s[-interval:])
            s = s[:-interval]
        if s:
            groups.append(s)
        groups.reverse()
        return (
            left_spaces + thousands_sep.join(groups) + right_spaces,
            len(thousands_sep) * (len(groups) - 1)
        )

    def format(self, percent, value, grouping=False, monetary=False,
            *additional):
        '''
        Returns the lang-aware substitution of a %? specifier (percent).
        '''
        # Code from format in locale.py

        # Strip a given amount of excess padding from the given string
        def _strip_padding(s, amount):
            lpos = 0
            while amount and s[lpos] == ' ':
                lpos += 1
                amount -= 1
            rpos = len(s) - 1
            while amount and s[rpos] == ' ':
                rpos -= 1
                amount -= 1
            return s[lpos:rpos + 1]

        # this is only for one-percent-specifier strings
        # and this should be checked
        if percent[0] != '%':
            raise ValueError("format() must be given exactly one %char "
                             "format specifier")
        if additional:
            formatted = percent % ((value,) + additional)
        else:
            formatted = percent % value
        # floats and decimal ints need special action!
        if percent[-1] in 'eEfFgG':
            seps = 0
            parts = formatted.split('.')
            if grouping:
                parts[0], seps = self._group(parts[0], monetary=monetary)
            if monetary:
                decimal_point = self.mon_decimal_point
            else:
                decimal_point = self.decimal_point
            formatted = decimal_point.join(parts)
            if seps:
                formatted = _strip_padding(formatted, seps)
        elif percent[-1] in 'diu':
            seps = 0
            if grouping:
                formatted, seps = self._group(formatted, monetary=monetary)
            if seps:
                formatted = _strip_padding(formatted, seps)
        return formatted

    def currency(
            self, val, currency, symbol=True, grouping=False, digits=None):
        """
        Formats val according to the currency settings in lang.
        """
        # Code from currency in locale.py

        # check for illegal values
        if digits is None:
            digits = currency.digits
        if digits == 127:
            raise ValueError("Currency formatting is not possible using "
                             "the 'C' locale.")

        s = self.format(
            '%%.%if' % digits, abs(val), grouping, monetary=True)
        # '<' and '>' are markers if the sign must be inserted
        # between symbol and value
        s = '<' + s + '>'

        if symbol:
            smb = currency.symbol
            precedes = (val < 0 and self.n_cs_precedes
                or self.p_cs_precedes)
            separated = (val < 0 and self.n_sep_by_space
                or self.p_sep_by_space)

            if precedes:
                s = smb + (separated and ' ' or '') + s
            else:
                s = s + (separated and ' ' or '') + smb

        sign_pos = val < 0 and self.n_sign_posn or self.p_sign_posn
        sign = val < 0 and self.negative_sign or self.positive_sign

        if sign_pos == 0:
            s = '(' + s + ')'
        elif sign_pos == 1:
            s = sign + s
        elif sign_pos == 2:
            s = s + sign
        elif sign_pos == 3:
            s = s.replace('<', sign)
        elif sign_pos == 4:
            s = s.replace('>', sign)
        else:
            # the default if nothing specified;
            # this should be the most fitting sign position
            s = sign + s

        return s.replace('<', '').replace('>', '')

    def strftime(self, value, format=None):
        '''
        Convert value to a string as specified by the format argument.
        '''
        pool = Pool()
        Month = pool.get('ir.calendar.month')
        Day = pool.get('ir.calendar.day')
        if format is None:
            format = self.date
            if isinstance(value, datetime.datetime):
                format += ' %H:%M:%S'
        format = format.replace('%x', self.date)
        format = format.replace('%X', '%H:%M:%S')
        if isinstance(value, datetime.date):
            for f, i, klass in (('%A', 6, Day), ('%B', 1, Month)):
                for field, f in [('name', f), ('abbreviation', f.lower())]:
                    locale = klass.locale(self, field=field)
                    format = format.replace(f, locale[value.timetuple()[i]])
        if isinstance(value, datetime.time):
            time = value
        else:
            try:
                time = value.time()
            except AttributeError:
                time = None
        if time:
            if time < datetime.time(12):
                p = self.am or 'AM'
            else:
                p = self.pm or 'PM'
            format = format.replace('%p', p)
        return value.strftime(format)

    def format_number(self, value, digits=None, grouping=True, monetary=None):
        if digits is None:
            d = value
            if not isinstance(d, Decimal):
                d = Decimal(repr(value))
            digits = -int(d.as_tuple().exponent)
        return self.format(
            '%.*f', (digits, value), grouping=grouping, monetary=monetary)

    def format_number_symbol(self, value, symbol, digits=None, grouping=True):
        symbol, position = symbol.get_symbol(value)
        separated = (
            value < 0 and self.n_sep_by_space or self.p_sep_by_space)
        s = self.format_number(value, digits, grouping)
        if position:
            s = s + (separated and ' ' or '') + symbol
        else:
            s = symbol + (separated and ' ' or '') + s
        return s


class LangConfigStart(ModelView):
    "Configure languages"
    __name__ = 'ir.lang.config.start'

    languages = fields.Many2Many('ir.lang', None, None, "Languages")

    @classmethod
    def default_languages(cls):
        pool = Pool()
        Lang = pool.get('ir.lang')
        return [x.id for x in Lang.search([('translatable', '=', True)])]


class LangConfig(Wizard):
    'Configure languages'
    __name__ = 'ir.lang.config'

    start = StateView('ir.lang.config.start',
        'ir.lang_config_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Load', 'load', 'tryton-ok', default=True),
            ])
    load = StateTransition()

    def transition_load(self):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Lang.load_translations(list(self.start.languages))
        untranslated_languages = Lang.search([
                ('id', 'not in', [l.id for l in self.start.languages]),
                ('translatable', '=', True),
                ])
        Lang.unload_translations(untranslated_languages)
        return 'end'


def get_parent_language(code):
    if code not in _parents:
        # Use SQL because it is used by load_module_graph
        cursor = Transaction().connection.cursor()
        lang = Table('ir_lang')
        cursor.execute(*lang.select(lang.code, lang.parent))
        _parents.update(cursor)
    if _parents.get(code):
        return _parents[code]
    for sep in ['@', '_']:
        if sep in code:
            return code.rsplit(sep, 1)[0]


_parents = {}
