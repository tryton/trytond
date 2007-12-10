from trytond.netsvc import Service, LocalService
from trytond import security
import threading
import thread
from trytond import pooler
from trytond.config import CONFIG
import base64


class Report(Service):

    def __init__(self, name='report'):
        Service.__init__(self, name)
        Service.join_group(self, 'web-services')
        Service.export_method(self, self.report)
        Service.export_method(self, self.report_get)
        self._reports = {}
        self.max_id = 0
        self.id_protect = threading.Semaphore()

    def report(self, database, user, passwd, object_name, ids, datas=None,
            context=None):
        if datas is None:
            datas = {}
        if context is None:
            context = {}
        security.check(database, user, passwd)

        self.id_protect.acquire()
        self.max_id += 1
        report_id = self.max_id
        self.id_protect.release()

        self._reports[report_id] = {
                'user': user,
                'result': False,
                'state': False,
                }

        def _go(report_id, user, ids, datas, context):
            cursor = pooler.get_db(database).cursor()
            obj = LocalService('report.' + object_name)
            (result, format) = obj.create(cursor, user, ids, datas, context)
            cursor.close()
            self._reports[report_id]['result'] = result
            self._reports[report_id]['format'] = format
            self._reports[report_id]['state'] = True
            return True

        thread.start_new_thread(_go, (report_id, user, ids, datas, context))
        return report_id

    def _check_report(self, report_id):
        result = self._reports[report_id]
        res = {'state': result['state']}
        if res['state']:
            if CONFIG['reportgz']:
                import zlib
                res2 = zlib.compress(result['result'])
                res['code'] = 'zlib'
            else:
                #CHECKME: why is this needed???
                if isinstance(result['result'], unicode):
                    res2 = result['result'].encode('latin1', 'replace')
                else:
                    res2 = result['result']
            if res2:
                res['result'] = base64.encodestring(res2)
            res['format'] = result['format']
            del self._reports[report_id]
        return res

    def report_get(self, database, user, passwd, report_id):
        security.check(database, user, passwd)

        if report_id in self._reports:
            if self._reports[report_id]['uid'] == user:
                return self._check_report(report_id)
            else:
                raise Exception, 'AccessDenied'
        else:
            raise Exception, 'ReportNotFound'
