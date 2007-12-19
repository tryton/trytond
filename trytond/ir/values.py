"Values"
from trytond.osv import OSV, fields
import pickle

class Values(OSV):
    "Values"
    _name = 'ir.values'
    _description = __doc__

    def _value_unpickle(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            value = report[name[:-9]]
            if not report.object and value:
                try:
                    value = str(pickle.loads(value))
                except:
                    pass
            res[report.id] = value
        return res

    def _value_pickle(self, cursor, user, obj_id, name, value, arg,
            context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        if 'read_delta' in ctx:
            del ctx['read_delta']
        values = self.browse(cursor, user, obj_id, context=context)
        if not values.object:
            value = pickle.dumps(eval(value))
        self.write(cursor, user, obj_id, {name[:-9]: value}, context=ctx)

    _columns = {
        'name': fields.char('Name', size=128),
        'model': fields.char('Model', size=128),
        'value': fields.text('Value'),
        'value_unpickle': fields.function(_value_unpickle,
            fnct_inv=_value_pickle, method=True, type='text', string='Value'),
        'object': fields.boolean('Is Object'),
        'key': fields.char('Type', size=128),
        'key2': fields.char('Value', size=256),
        'meta': fields.text('Meta Datas'),
        'meta_unpickle': fields.function(_value_unpickle,
            fnct_inv=_value_pickle, method=True, type='text',
            string='Meta Datas'),
        'res_id': fields.integer('Resource ID'),
        'user_id': fields.many2one('res.user', 'User', ondelete='cascade'),


        #TODO add in company module
        #'company_id': fields.many2one('res.company', 'Company')
    }
    _defaults = {
        'key': lambda *a: 'action',
        'key2': lambda *a: 'tree_but_open',
        #'company_id': lambda *a: False,
    }

    def _auto_init(self, cursor):
        super(Values, self)._auto_init(cursor)
        cursor.execute('SELECT indexname FROM pg_indexes ' \
                'WHERE indexname = \'ir_values_key_model_key2_index\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX ir_values_key_model_key2_index ' \
                    'ON ir_values (key, model, key2)')
            cursor.commit()

    def set(self, cursor, user, key, key2, name, models, value, replace=True,
            isobject=False, meta=False, preserve_user=False): #, company=False):
        if type(value)==type(u''):
            value = value.encode('utf8')
        if not isobject:
            value = pickle.dumps(value)
        if meta:
            meta = pickle.dumps(meta)
        ids_res = []
        for model in models:
            if type(model)==type([]) or type(model)==type(()):
                model, res_id = model
            else:
                res_id = False
            if replace:
                if key in ('meta', 'default'):
                    ids = self.search(cursor, user, [
                        ('key', '=', key),
                        ('key2', '=', key2),
                        ('name', '=', name),
                        ('model', '=', model),
                        ('res_id', '=', res_id),
                        ('user_id', '=', preserve_user and user)
                        ])
                else:
                    ids = self.search(cursor, user, [
                        ('key', '=', key),
                        ('key2', '=', key2),
                        ('value', '=', value),
                        ('model', '=', model),
                        ('res_id', '=', res_id),
                        ('user_id', '=', preserve_user and user)
                        ])
                self.unlink(cursor, user, ids)
            vals = {
                'name': name,
                'value': value,
                'model': model,
                'object': isobject,
                'key': key,
                'key2': key2 and key2[:200],
                'meta': meta,
                'user_id': preserve_user and user,
            }
#            if company:
#                cid = self.pool.get('res.user').browse(cursor, user, user,
#                        context={}).company_id.id
#                vals['company_id'] = cid
            if res_id:
                vals['res_id'] = res_id
            ids_res.append(self.create(cursor, user, vals))
        return ids_res

    def get(self, cursor, user, key, key2, models, meta=False, context=None,
            res_id_req=False, without_user=True, key2_req=True):
        result = []
        for model in models:
            if type(model)==type([]) or type(model)==type(()):
                model, res_id = model
            else:
                res_id = False
            where1 = ['key = %s', 'model = %s']
            where2 = [key, str(model)]
            where_opt = []
            if key2:
                where1.append('key2 = %s')
                where2.append(key2[:200])
            else:
                dest = where1
                if not key2_req or meta:
                    dest = where_opt
                dest.append('key2 IS NULL')

            if res_id_req and (models[-1][0]==model):
                if res_id:
                    where1.append('res_id = %d' % (res_id,))
                else:
                    where1.append('(res_id IS NULL)')
            elif res_id:
                if (models[-1][0]==model):
                    where1.append('(res_id = %d OR (res_id IS NULL))' % (res_id,))
                    where_opt.append('res_id = %d' % (res_id,))
                else:
                    where1.append('res_id = %d' % (res_id,))

#            if not without_user:
            where_opt.append('user_id = %d' % (user,))


            result = []
            test = True
            while test:
                if not where_opt:
                    cursor.execute('SELECT id FROM ir_values ' \
                            'where ' + ' and '.join(where1) + ' ' \
                                'AND user_id IS NULL', where2)
                else:
                    cursor.execute('select id FROM ir_values ' \
                            'where ' + ' and '.join(where1 + where_opt),
                            where2)
                result.extend([x[0] for x in cursor.fetchall()])
                if len(where_opt):
                    where_opt.pop()
                else:
                    test = False

            if result:
                break

        if not result:
            return []
#        cid = self.pool.get('res.user').browse(cursor, user, user,
#                context={}).company_id.id
        cursor.execute('SELECT id, name, value, object, meta, key ' \
                'FROM ir_values ' \
                'WHERE id IN (' + ','.join([str(x) for x in result])+') ' \
                    #'AND (company_id IS NULL OR company_id = %d) '\
                'ORDER BY user_id')#, (cid,))
        result = cursor.fetchall()

        def _result_get(i, keys):
            if i[1] in keys:
                return False
            keys.append(i[1])
            if i[3]:
                model, obj_id = i[2].split(',')
                try:
                    obj_id = int(obj_id)
                except:
                    return False
                datas = self.pool.get(model).read(cursor, user, [obj_id], False,
                        context=context)
                if not len(datas):
                    #ir_del(cursor, user, i[0])
                    return False
                def clean(j):
                    for key in (
                            'report_sxw_content',
                            'report_rml_content',
                            'report_sxw', 'report_rml',
                            'report_sxw_content_data',
                            'report_rml_content_data',
                            ):
                        if key in j:
                            del j[key]
                    return j
                datas = clean(datas[0])
            else:
                datas = pickle.loads(i[2])
            if meta:
                meta2 = pickle.loads(i[4])
                return (i[0], i[1], datas, meta2)
            return (i[0], i[1], datas)
        keys = []
        res = filter(bool, map(lambda x: _result_get(x, keys), list(result)))
        return res

Values()
