from trytond.netsvc import Service, LocalService
from trytond import security


class Wizard(Service):

    def __init__(self, name='wizard'):
        Service.__init__(self, name)
        Service.join_group(self, 'web-services')
        Service.export_method(self, self.execute)
        Service.export_method(self, self.create)
        self.max_id = 0
        self.wiz_datas = {}
        self.wiz_name = {}
        self.wiz_uid = {}

    def _execute(self, database, user, wiz_id, datas, action, context):
        self.wiz_datas[wiz_id].update(datas)
        wiz = LocalService('wizard_proxy')
        return wiz.execute(database, user, self.wiz_name[wiz_id],
                self.wiz_datas[wiz_id], action, context)

    def create(self, database, user, passwd, wiz_name, datas=None):
        security.check(database, user, passwd)
        # FIXME: this is not thread-safe
        self.max_id += 1
        self.wiz_datas[self.max_id] = {}
        self.wiz_name[self.max_id] = wiz_name
        self.wiz_uid[self.max_id] = user
        return self.max_id

    #TODO: remove wiz_id not usefull
    def execute(self, database, user, passwd, wiz_id, datas, *args):
        security.check(database, user, passwd)
        if wiz_id in self.wiz_uid:
            if self.wiz_uid[wiz_id] == user:
                return self._execute(database, user, wiz_id, datas, *args)
            else:
                raise Exception, 'AccessDenied'
        else:
            raise Exception, 'WizardNotFound'
