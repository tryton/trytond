from trytond.netsvc import Service, LocalService
from trytond import security

class Object(Service):

    def __init__(self, name="object"):
        Service.__init__(self, name)
        Service.join_group(self, 'web-services')
        Service.export_method(self, self.execute)
        Service.export_method(self, self.exec_workflow)
        Service.export_method(self, self.obj_list)

    def exec_workflow(self, database, user, passwd, object_name, method,
            object_id):
        security.check(database, user, passwd)
        service = LocalService("object_proxy")
        res = service.exec_workflow(database, user, object_name, method,
                object_id)
        return res

    def execute(self, database, user, passwd, object_name, method, *args):
        security.check(database, user, passwd)
        service = LocalService("object_proxy")
        res = service.execute(database, user, object_name, method, *args)
        return res

    def obj_list(self, database, user, passwd):
        security.check(database, user, passwd)
        service = LocalService("object_proxy")
        res = service.obj_list()
        return res
