#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import time
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, Or
from trytond.tools import Cache, safe_eval
from trytond.backend import TableHandler
from trytond.tools import reduce_ids


class Trigger(ModelSQL, ModelView):
    "Trigger"
    _name = 'ir.trigger'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active', select=2)
    model = fields.Many2One('ir.model', 'Model', required=True, select=1)
    on_time = fields.Boolean('On Time', select=1, states={
        'invisible': Or(Eval('on_create', False), Eval('on_write', False),
            Eval('on_delete', False)),
        }, depends=['on_create', 'on_write', 'on_delete'],
        on_change=['on_time'])
    on_create = fields.Boolean('On Create', select=1, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'],
        on_change=['on_create'])
    on_write = fields.Boolean('On Write', select=1, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'],
        on_change=['on_write'])
    on_delete = fields.Boolean('On Delete', select=1, states={
        'invisible': Eval('on_time', False),
        }, depends=['on_time'],
        on_change=['on_delete'])
    condition = fields.Char('Condition', required=True,
            help='A Python statement evaluated with record represented by '
            '"self"\nIt triggers the action if true.')
    limit_number = fields.Integer('Limit Number', help='Limit the number of '
            'call to "Action Function" by records.\n'
            '0 for no limit.')
    minimum_delay = fields.Float('Minimum Delay', help='Set a minimu delay '
            'in minutes between call to "Action Function" for the same record.\n'
            '0 for no delay.')
    action_model = fields.Many2One('ir.model', 'Action Model', required=True)
    action_function = fields.Char('Action Function', required=True)

    def __init__(self):
        super(Trigger, self).__init__()
        self._sql_constraints += [
            ('on_exclusive',
                'CHECK(NOT(on_time AND (on_create OR on_write OR on_delete)))',
                '"On Time" and others are mutually exclusive!'),
        ]
        self._constraints += [
            ('check_condition', 'invalid_condition'),
        ]
        self._error_messages.update({
            'invalid_condition': 'Condition must be a python expression!',
        })
        self._order.insert(0, ('name', 'ASC'))

    def check_condition(self, cursor, user, ids):
        '''
        Check condition
        '''
        for trigger in self.browse(cursor, user, ids):
            try:
                compile(trigger.condition, '', 'eval')
            except (SyntaxError, TypeError):
                return False
        return True

    def default_active(self, cursor, user, context=None):
        return True

    def on_change_on_time(self, cursor, user, values, context=None):
        if values.get('on_time'):
            return {
                    'on_create': False,
                    'on_write': False,
                    'on_delete': False,
                    }
        return {}

    def on_change_on_create(self, cursor, user, values, context=None):
        if values.get('on_create'):
            return {
                    'on_time': False,
                    }
        return {}

    def on_change_on_write(self, cursor, user, values, context=None):
        if values.get('on_write'):
            return {
                    'on_time': False,
                    }
        return {}

    def on_change_on_delete(self, cursor, user, values, context=None):
        if values.get('on_delete'):
            return {
                    'on_time': False,
                    }
        return {}

    @Cache('ir_trigger.get_triggers')
    def get_triggers(self, cursor, user, model_name, mode):
        """
        Return trigger ids for a model and a mode

        :param cursor: the database cursor
        :param user: the user id
        :param model_name: the name of the model
        :param mode: the mode that can be 'create', 'write', 'delete' or 'time'
        :return: a list of ir.trigger ids
        """
        assert mode in ['create', 'write', 'delete', 'time'], \
                'Invalid trigger mode'

        if user == 0:
            return [] # XXX is it want we want?

        trigger_ids = self.search(cursor, user, [
            ('model.model', '=', model_name),
            ('on_%s' % mode, '=', True),
            ])
        return trigger_ids

    def eval(self, cursor, user, trigger, record, context=None):
        """
        Evaluate the condition of trigger

        :param cursor: the database cursor
        :param user: the user id
        :param trigger: a BrowseRecord of ir.trigger
        :param record: a BrowseRecord of the tested model
        :param context: the context
        :return: a boolean
        """
        if context is None:
            context = {}
        model_obj = self.pool.get(trigger.model.model)
        env = {}
        env.update(context)
        env['current_date'] = datetime.datetime.today()
        env['time'] = time
        env['context'] = context
        env['self'] = record
        return bool(safe_eval(trigger.condition, env))

    def trigger_action(self, cursor, user, ids, trigger_id, context=None):
        """
        Trigger the action define on trigger_id for the ids

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the list of record ids triggered
        :param trigger_id: the trigger id
        :param context: the context
        """
        trigger_log_obj = self.pool.get('ir.trigger.log')
        trigger = self.browse(cursor, user, trigger_id, context=context)
        model_obj = self.pool.get(trigger.action_model.model)

        # Filter on limit_number
        if trigger.limit_number:
            new_ids = []
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('"record_id"', sub_ids)
                cursor.execute('SELECT "record_id", COUNT(1) FROM "%s" '
                        'WHERE %s AND "trigger" = %%s '
                        'GROUP BY "record_id"'
                        % (trigger_log_obj._table, red_sql),
                        red_ids + [trigger.id])
                number = dict(cursor.fetchall())
                for record_id in sub_ids:
                    if record_id not in number:
                        new_ids.append(record_id)
                        continue
                    if number[record_id] < trigger.limit_number:
                        new_ids.append(record_id)
            ids = new_ids

        # Filter on minimum_delay
        if trigger.minimum_delay:
            new_ids = []
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('"record_id"', sub_ids)
                cursor.execute('SELECT "record_id", MAX("create_date") '
                        'FROM "%s" '
                        'WHERE %s AND "trigger" = %%s '
                        'GROUP BY "record_id"'
                        % (trigger_log_obj._table, red_sql),
                        red_ids + [trigger.id])
                delay = dict(cursor.fetchall())
                for record_id in sub_ids:
                    if record_id not in delay:
                        new_ids.append(record_id)
                        continue
                    # SQLite return string for MAX
                    if isinstance(delay[record_id], basestring):
                        datepart, timepart = delay[record_id].split(" ")
                        year, month, day = map(int, datepart.split("-"))
                        timepart_full = timepart.split(".")
                        hours, minutes, seconds = map(int, timepart_full[0].split(":"))
                        if len(timepart_full) == 2:
                            microseconds = int(timepart_full[1])
                        delay[record_id] = datetime.datetime(year, month, day,
                                hours, minutes, seconds, microseconds)
                    if datetime.datetime.now() - delay[record_id] \
                            >= datetime.timedelta(minutes=trigger.minimum_delay):
                        new_ids.append(record_id)
            ids = new_ids

        if ids:
            getattr(model_obj, trigger.action_function)(cursor, user, ids,
                    trigger_id, context=context)
        if trigger.limit_number or trigger.minimum_delay:
            for record_id in ids:
                trigger_log_obj.create(cursor, user, {
                    'trigger': trigger.id,
                    'record_id': record_id,
                    }, context=context)

    def trigger_time(self, cursor, user, context=None):
        '''
        Trigger time actions

        :param cursor: the database cursor
        :param user: the user id
        :param context: the context
        '''
        trigger_ids = self.search(cursor, user, [
            ('on_time', '=', True),
            ], context=context)
        for trigger in self.browse(cursor, user, trigger_ids, context=context):
            model_obj = self.pool.get(trigger.model.model)
            triggered_ids = []
            # TODO add a domain
            record_ids = model_obj.search(cursor, user, [], context=context)
            for record in model_obj.browse(cursor, user, record_ids,
                    context=context):
                if self.eval(cursor, user, trigger, record, context=context):
                    triggered_ids.append(record.id)
            if triggered_ids:
                self.trigger_action(cursor, user, triggered_ids, trigger.id,
                        context=context)

    def create(self, cursor, user, values, context=None):
        res = super(Trigger, self).create(cursor, user, values, context=context)
        # Restart the cache on the get_triggers method of ir.trigger
        self.get_triggers(cursor.dbname)
        return res

    def write(self, cursor, user, ids, values, context=None):
        res = super(Trigger, self).write(cursor, user, ids, values,
                context=context)
        # Restart the cache on the get_triggers method of ir.trigger
        self.get_triggers(cursor.dbname)
        return res

    def delete(self, cursor, user, ids, context=None):
        res = super(Trigger, self).delete(cursor, user, ids, context=context)
        # Restart the cache on the get_triggers method of ir.trigger
        self.get_triggers(cursor.dbname)
        return res

Trigger()


class TriggerLog(ModelSQL):
    'Trigger Log'
    _name = 'ir.trigger.log'
    _description = __doc__
    trigger = fields.Many2One('ir.trigger', 'Trigger', required=True)
    record_id = fields.Integer('Record ID', required=True)

    def init(self, cursor, module_name):
        super(TriggerLog, self).init(cursor, module_name)

        table = TableHandler(cursor, self, module_name)
        table.index_action(['trigger', 'record_id'], 'add')

TriggerLog()
