from trytond import netsvc
from trytond import pooler


class EnvCall(object):

    def __init__(self, wf_service, d_arg):
        self.wf_service = wf_service
        self.d_arg = d_arg

    def __call__(self, *args):
        arg = self.d_arg + args
        return self.wf_service.execute_cr(*arg)


class Env(dict):

    def __init__(self, wf_service, cursor, user, model, ids):
        super(Env, self).__init__()
        self.wf_service = wf_service
        self.cursor = cursor
        self.user = user
        self.model = model
        self.ids = ids
        self.obj = pooler.get_pool(cursor.dbname).get(model)
        self.columns = self.obj._columns.keys() + \
                self.obj._inherit_fields.keys()

    def __getitem__(self, key):
        if (key in self.columns) and (not super(Env, self).__contains__(key)):
            res = self.wf_service.execute_cr(self.cursor, self.user,
                    self.model, 'read', self.ids, [key])[0][key]
            super(Env, self).__setitem__(key, res)
            return res
        elif key in dir(self.obj):
            return EnvCall(self.wf_service, (self.cursor, self.user, self.model,
                key, self.ids))
        else:
            return super(Env, self).__getitem__(key)

def eval_expr(cursor, ident, action):
    res = False
    for line in action.split('\n'):
        user = ident[0]
        model = ident[1]
        ids = [ident[2]]
        if line == 'True':
            res = True
        elif line =='False':
            res = False
        else:
            wf_service = netsvc.LocalService("object_proxy")
            env = Env(wf_service, cursor, user, model, ids)
            res = eval(line, env)
    return res

def execute(cursor, ident, activity):
    return eval_expr(cursor, ident, activity['action'])

def check(cursor, ident, transition, signal):
    res = True
    if transition['signal']:
        res = (signal == transition['signal'])

    if transition['group']:
        user = ident[0]
        serv = netsvc.LocalService('object_proxy')
        user_groups = serv.execute_cr(cursor, user, 'res.user', 'read', user,
                ['groups'])['groups']
        res = transition['group'] in user_groups
    res = res and eval_expr(cursor, ident, transition['condition'])
    return res
