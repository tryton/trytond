"Rule"
from trytond.osv import fields, OSV
from trytond.tools import Cache
import time


class RuleGroup(OSV):
    "Rule group"
    _name = 'ir.rule.group'
    _description = __doc__
    name = fields.Char('Name', size=128, select=1)
    model = fields.Many2One('ir.model', 'Model', select=1,
       required=True)
    global_p = fields.Boolean('Global', select=1,
       help="Make the rule global \n" \
               "or it needs to be put on a group or user")
    rules = fields.One2Many('ir.rule', 'rule_group', 'Tests',
       help="The rule is satisfied if at least one test is True")
    groups = fields.Many2Many('res.group', 'group_rule_group_rel',
       'rule_group_id', 'group_id', 'Groups')
    users = fields.Many2Many('res.user', 'user_rule_group_rel',
       'rule_group_id', 'user_id', 'Users')
    _order = 'model, global_p DESC'

    def default_global_p(self, cursor, user, context=None):
        return 1

    def unlink(self, cursor, user, ids, context=None):
        res = super(RuleGroup, self).unlink(cursor, user, ids,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get()
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(RuleGroup, self).create(cursor, user, vals,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get()
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(RuleGroup, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.pool.get('ir.rule').domain_get()
        return res

RuleGroup()


class Rule(OSV):
    "Rule"
    _name = 'ir.rule'
    _rec_name = 'field'
    _description = __doc__
    field = fields.Many2One('ir.model.field', 'Field',
       domain="[('model', '=', parent.model)]", select=1,
       required=True)
    operator = fields.Selection([
       ('=', '='),
       ('<>', '<>'),
       ('<=', '<='),
       ('>=', '>='),
       ('in', 'in'),
       ('child_of', 'child_of'),
       ], 'Operator', required=True)
    operand = fields.Selection('get_operand','Operand', size=64, required=True)
    rule_group = fields.Many2One('ir.rule.group', 'Group', select=2,
       required=True, ondelete="cascade")

    def _operand_get(self, cursor, user, obj_name='', level=3, recur=None, root_tech='', root=''):
        res = {}
        if not obj_name:
            obj_name = 'res.user'
        res.update({"False": "False", "True": "True", "user.id": "User"})
        if not recur:
            recur = []
        obj_fields = self.pool.get(obj_name).fields_get(cursor, user)
        key = obj_fields.keys()
        key.sort()
        for k in key:

            if obj_fields[k]['type'] in ('many2one'):
                res[root + '/' + obj_fields[k]['string']] = \
                        root_tech + '.' + k + '.id'

            elif obj_fields[k]['type'] in ('many2many', 'one2many'):
                res[root + '/' + obj_fields[k]['string']] = \
                        '[x.id for x in ' + root_tech + '.' + k + ']'
            else:
                res[root + '/' + obj_fields[k]['string']] = \
                        root_tech + '.' + k

            if (obj_fields[k]['type'] in recur) and (level>0):
                res.update(self._operand_get(cursor, user,
                    obj_fields[k]['relation'], level-1,
                    recur, root_tech + '.' + k, root + '/' + \
                            obj_fields[k]['string']))

        return res

    def get_operand(self, cursor, user, context):
        res = []
        operands = self._operand_get(cursor, user, 'res.user', level=1,
                recur=['many2one'], root_tech='user', root='User')
        for i in operands.keys():
            res.append((i, i))
        return res

    def domain_get(self, cursor, user, model_name):
        # root user above constraint
        if user == 0:
            return '', []

        cursor.execute("SELECT r.id FROM ir_rule r " \
                "JOIN (ir_rule_group g " \
                    "JOIN ir_model m ON (g.model = m.id)) " \
                    "ON (g.id = r.rule_group) " \
                "WHERE m.model = %s "
                    "AND (g.id IN (" \
                            "SELECT rule_group_id FROM user_rule_group_rel " \
                                "WHERE user_id = %s " \
                            "UNION SELECT rule_group_id " \
                                "FROM group_rule_group_rel g_rel " \
                                "JOIN res_group_user_rel u_rel " \
                                    "ON (g_rel.group_id = u_rel.gid) " \
                                "WHERE u_rel.uid = %s) "
                    "OR g.global_p)", (model_name, user, user))
        ids = [x[0] for x in cursor.fetchall()]
        if not ids:
            return '', []
        obj = self.pool.get(model_name)
        clause = {}
        clause_global = {}
        operand2query = self._operand_get(cursor, user, 'res.user', level=1,
                recur=['many2one'], root_tech='user', root='User')
        # Use root user to prevent recursion
        for rule in self.browse(cursor, 0, ids):
            dom = eval("[('%s', '%s', %s)]" % \
                    (rule.field.name, rule.operator,
                        operand2query[rule.operand]),
                    {'user': self.pool.get('res.user').browse(cursor, 0,
                        user), 'time': time})

            if rule.rule_group['global_p']:
                clause_global.setdefault(rule.rule_group.id, [])
                clause_global[rule.rule_group.id].append(
                        obj._where_calc(cursor, user, dom, active_test=False))
            else:
                clause.setdefault(rule.rule_group.id, [])
                clause[rule.rule_group.id].append(
                        obj._where_calc(cursor, user, dom, active_test=False))

        def _query(clauses, test):
            query = ''
            val = []
            for groups in clauses.values():
                if not groups:
                    continue
                if len(query):
                    query += ' '+test+' '
                query += '('
                first = True
                for group in groups:
                    if not first:
                        query += ' OR '
                    first = False
                    query += '('
                    first2 = True
                    for clause in group[0]:
                        if not first2:
                            query += ' AND '
                        first2 = False
                        query += clause
                    query += ')'
                    val += group[1]
                query += ')'
            return query, val

        query = ''
        val = []

        # Test if there is no rule_group that have no rule
        cursor.execute("""SELECT g.id FROM
            ir_rule_group g
                JOIN ir_model m ON (g.model = m.id)
            WHERE m.model = %s
                AND (g.id NOT IN (SELECT rule_group FROM ir_rule))
                AND (g.id IN (SELECT rule_group_id FROM user_rule_group_rel
                    WHERE user_id = %s
                    UNION SELECT rule_group_id FROM group_rule_group_rel g_rel
                        JOIN res_group_user_rel u_rel
                            ON g_rel.group_id = u_rel.gid
                        WHERE u_rel.uid = %s))""", (model_name, user, user))
        if not cursor.fetchall():
            query, val = _query(clause, 'OR')

        query_global, val_global = _query(clause_global, 'AND')
        if query_global:
            if query:
                query = '('+query+') AND '+query_global
                val.extend(val_global)
            else:
                query = query_global
                val = val_global

        return query, val
    domain_get = Cache()(domain_get)

    def unlink(self, cursor, user, ids, context=None):
        res = super(Rule, self).unlink(cursor, user, ids, context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.domain_get()
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(Rule, self).create(cursor, user, vals, context=context)
        # Restart the cache on the domain_get method of ir.rule
        self.domain_get()
        return res

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Rule, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the domain_get method
        self.domain_get()
        return res

Rule()
