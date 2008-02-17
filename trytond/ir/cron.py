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

NEXT_WAIT = 60

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
    _columns = {
        'name': fields.char('Name', size=60, required=True),
        'user': fields.many2one('res.user', 'User', required=True),
        'active': fields.boolean('Active'),
        'interval_number': fields.integer('Interval Number'),
        'interval_type': fields.selection( [
            ('minutes', 'Minutes'),
            ('hours', 'Hours'),
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
            ], 'Interval Unit'),
        'numbercall': fields.integer('Number of calls',
            help='Number of time the function is called,\n' \
                    'a negative number indicates that the function ' \
                    'will always be called'),
        'doall' : fields.boolean('Repeat missed'),
        'nextcall' : fields.datetime('Next call date', required=True),
        'model': fields.char('Model', size=64),
        'function': fields.char('Function', size=64),
        'args': fields.text('Arguments'),
        'priority': fields.integer('Priority',
            help='0=Very Urgent\n10=Not urgent')
    }

    _defaults = {
        'nextcall' : lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'priority' : lambda *a: 5,
        'user' : lambda obj,cursor,user,context: user,
        'interval_number' : lambda *a: 1,
        'interval_type' : lambda *a: 'months',
        'numbercall' : lambda *a: 1,
        'active' : lambda *a: 1,
        'doall' : lambda *a: 1
    }

    def _callback(self, cursor, user, model, func, args):
        args = (args or []) and eval(args)
        obj = self.pool.get(model)
        if obj and hasattr(obj, func):
            fct = getattr(obj, func)
            fct(cursor, user, *args)

    def pool_jobs(self, db_name, check=False):
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
                nextcall = DateTime.strptime(job['nextcall'],
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
                            "numbercall = %d" + addsql + " " \
                            "WHERE id = %d",
                            (nextcall.strftime('%Y-%m-%d %H:%M:%S'),
                                numbercall, job['id']))
                cursor.commit()
        finally:
            cursor.close()
        #TODO improved to do at the min(min(nextcalls), time() + NEWT_WAIT)
        if not check:
            self.set_alarm(self.pool_jobs, int(time.time()) + NEXT_WAIT,
                    [db_name])

Cron()
