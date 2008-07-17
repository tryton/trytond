#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import time
from trytond.osv import fields, OSV
from string import Template


class SequenceType(OSV):
    "Sequence type"
    _name = 'ir.sequence.type'
    _description = __doc__
    name = fields.Char('Sequence Name', required=True)
    code = fields.Char('Sequence Code', required=True)

SequenceType()


class Sequence(OSV):
    "Sequence"
    _name = 'ir.sequence'
    _description = __doc__
    name = fields.Char('Sequence Name', required=True)
    code = fields.Selection('code_get', 'Sequence Code', required=True)
    active = fields.Boolean('Active')
    prefix = fields.Char('Prefix')
    suffix = fields.Char('Suffix')
    number_next = fields.Integer('Next Number')
    number_increment = fields.Integer('Increment Number')
    padding = fields.Integer('Number padding')

    def __init__(self):
        super(Sequence, self).__init__()
        self._constraints += [
            ('check_prefix_suffix', 'Invalid prefix/suffix',
                ['prefix', 'suffix']),
        ]
        self._error_messages.update({
            'missing': 'Missing sequence!',
            })

    def default_active(self, cursor, user, context=None):
        return 1

    def default_number_increment(self, cursor, user, context=None):
        return 1

    def default_number_next(self, cursor, user, context=None):
        return 1

    def default_padding(self, cursor, user, context=None):
        return 0

    def code_get(self, cursor, user, context=None):
        cursor.execute('select code, name from ir_sequence_type')
        return cursor.fetchall()

    def check_prefix_suffix(self, cursor, user, ids):
        "Check prefix and suffix"

        for sequence in self.browse(cursor, user, ids):
            try:
                self._process(sequence.prefix)
                self._process(sequence.suffix)
            except:
                return False
        return True

    def _process(self, string):
        return Template(string or '').substitute(
                year=time.strftime('%Y'),
                month=time.strftime('%m'),
                day=time.strftime('%d'),
                )

    def get_id(self, cursor, user, sequence_id, test='id=%s', context=None):
        cursor.execute('lock table ir_sequence')
        cursor.execute('SELECT id, number_next, number_increment, prefix, ' \
                    'suffix, padding ' \
                'FROM ir_sequence ' \
                'WHERE ' + test + ' AND active = True', (sequence_id,))
        res = cursor.dictfetchone()
        if res:
            cursor.execute('UPDATE ir_sequence ' \
                    'SET number_next = number_next + number_increment ' \
                    'WHERE id = %s AND active = True', (res['id'],))
            if res['number_next']:
                return self._process(res['prefix']) + \
                        '%%0%sd' % res['padding'] % res['number_next'] + \
                        self._process(res['suffix'])
            else:
                return self._process(res['prefix']) + \
                        self._process(res['suffix'])
        self.raise_user_error(cursor, 'missing', context=context)

    def get(self, cursor, user, code, context=None):
        return self.get_id(cursor, user, code, test='code=%s', context=context)

Sequence()
