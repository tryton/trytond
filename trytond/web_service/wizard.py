from trytond.netsvc import Service, LocalService
from trytond import security
from threading import Semaphore
from random import randint
from sys import maxint
from trytond.tools import Cache


class Wizard(Service):

    def __init__(self, name='wizard'):
        Service.__init__(self, name)
        Service.join_group(self, 'web-services')
        Service.export_method(self, self.execute)
        Service.export_method(self, self.create)
        Service.export_method(self, self.delete)
        self.wiz_datas = {}
        self.wiz_name = {}
        self.wiz_uid = {}
        self._semaphore = Semaphore()

    def _execute(self, database, user, wiz_id, datas, action, context):
        self.wiz_datas[wiz_id].update(datas)
        wiz = LocalService('wizard_proxy')
        return wiz.execute(database, user, self.wiz_name[wiz_id],
                self.wiz_datas[wiz_id], action, context)

    def create(self, database, user, passwd, wiz_name, datas=None):
        security.check(database, user, passwd)
        Cache.clean(database)
        self._semaphore.acquire()
        wiz_id = 0
        while True:
            wiz_id = randint(0, maxint)
            if wiz_id not in self.wiz_name:
                break
        self.wiz_datas[wiz_id] = {}
        self.wiz_name[wiz_id] = wiz_name
        self.wiz_uid[wiz_id] = user
        self._semaphore.release()
        return wiz_id

    def execute(self, database, user, passwd, wiz_id, datas, *args):
        security.check(database, user, passwd)
        Cache.clean(database)
        if wiz_id in self.wiz_uid:
            if self.wiz_uid[wiz_id] == user:
                return self._execute(database, user, wiz_id, datas, *args)
            else:
                raise Exception, 'AccessDenied'
        else:
            raise Exception, 'WizardNotFound'

    def delete(self, database, user, passwd, wiz_id):
        security.check(database, user, passwd)
        Cache.clean(database)
        if wiz_id in self.wiz_uid:
            if self.wiz_uid[wiz_id] == user:
                self._semaphore.acquire()
                del self.wiz_datas[wiz_id]
                del self.wiz_name[wiz_id]
                del self.wiz_uid[wiz_id]
                self._semaphore.release()
                return wiz_id
            else:
                raise Exception, 'AccessDenied'
        else:
            raise Exception, 'WizardNotFound'
