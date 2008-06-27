#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"""
SPEC: Execute "model.function(*eval(args))" periodically
   date        : date to execute the job or NULL if directly
   delete_after: delete the ir.cron entry after execution
   interval_*  : period
   max_repeat  : number of execution or NULL if endlessly
"""

from mx import DateTime
import time
from trytond import pooler
from trytond.osv import fields, OSV
from trytond.netsvc import Agent

_INTERVALTYPES = {
    'work_days': lambda interval: DateTime.RelativeDateTime(days=interval),
    'days': lambda interval: DateTime.RelativeDateTime(days=interval),
    'hours': lambda interval: DateTime.RelativeDateTime(hours=interval),
    'weeks': lambda interval: DateTime.RelativeDateTime(days=7*interval),
    'months': lambda interval: DateTime.RelativeDateTime(months=interval),
    'minutes': lambda interval: DateTime.RelativeDateTime(minutes=interval),
}

class Cron(OSV, Agent):
    "Cron"
    _name = "ir.cron"
    _description = __doc__
    name = fields.Char('Name', size=60, required=True)
    user = fields.Many2One('res.user', 'User', required=True)
    active = fields.Boolean('Active')
    interval_number = fields.Integer('Interval Number')
    interval_type = fields.Selection( [
       ('minutes', 'Minutes'),
       ('hours', 'Hours'),
       ('work_days', 'Work Days'),
       ('days', 'Days'),
       ('weeks', 'Weeks'),
       ('months', 'Months'),
       ], 'Interval Unit')
    numbercall = fields.Integer('Number of calls',
       help='Number of time the function is called,\n' \
               'a negative number indicates that the function ' \
               'will always be called')
    doall = fields.Boolean('Repeat missed')
    nextcall = fields.DateTime('Next call date', required=True)
    model = fields.Char('Model', size=64)
    function = fields.Char('Function', size=64)
    args = fields.Text('Arguments')
    priority = fields.Integer('Priority',
       help='0=Very Urgent\n10=Not urgent')

    def default_nextcall(self, cursor, user, context=None):
        return time.strftime('%Y-%m-%d %H:%M:%S')

    def default_priority(self, cursor, user, context=None):
        return 5

    def default_user(self, cursor, user, context=None):
        return user

    def default_interval_number(self, cursor, user, context=None):
        return 1

    def default_interval_type(self, cursor, user, context=None):
        return 'months'

    def default_numbercall(self, cursor, user, context=None):
        return 1

    def default_active(self, cursor, user, context=None):
        return 1

    def default_doall(self, cursor, user, context=None):
        return 1

    def _callback(self, cursor, user, model, func, args):
        args = (args or []) and eval(args)
        obj = self.pool.get(model)
        if obj and hasattr(obj, func):
            fct = getattr(obj, func)
            fct(cursor, user, *args)

    def pool_jobs(self, db_name):
        #TODO Error treatment: exception, request, ... -> send request to user
        now = DateTime.now()
        try:
            cursor = pooler.get_db(db_name).cursor()
        except:
            return False

        try:
            cursor.execute('SELECT * FROM ir_cron ' \
                    'WHERE numbercall <> 0 ' \
                        'AND active ' \
                        'AND nextcall <= now() ' \
                        'ORDER BY priority')
            for job in cursor.dictfetchall():
                nextcall = DateTime.strptime(str(job['nextcall']),
                        '%Y-%m-%d %H:%M:%S')
                numbercall = job['numbercall']
                done = False
                while nextcall < now and numbercall:
                    if numbercall > 0:
                        numbercall -= 1
                    if not done or job['doall']:
                        self._callback(cursor, job['user'], job['model'],
                                job['function'], job['args'])
                    if numbercall:
                        nextcall += _INTERVALTYPES[job['interval_type']](
                                job['interval_number'])
                    done = True
                addsql = ''
                if not numbercall:
                    addsql = ', active=False'
                cursor.execute("UPDATE ir_cron SET nextcall = %s, " \
                            "numbercall = %s" + addsql + " " \
                            "WHERE id = %s",
                            (nextcall.strftime('%Y-%m-%d %H:%M:%S'),
                                numbercall, job['id']))
                cursor.commit()
        finally:
            cursor.close()

Cron()
