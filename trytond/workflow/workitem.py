import wkf_expr
import instance

# TODO: remove triggers

def create(cursor, act_datas, inst_id, ident):
    for act in act_datas:
        cursor.execute("SELECT NEXTVAL('wkf_workitem_id_seq')")
        (id_new,) = cursor.fetchone()
        cursor.execute("INSERT INTO wkf_workitem " \
                "(id, act_id, inst_id, state) VALUES (%d, %s, %s, 'active')",
                (id_new, act['id'], inst_id))
        cursor.execute('SELECT * FROM wkf_workitem WHERE id=%d', (id_new,))
        res = cursor.dictfetchone()
        process(cursor, res, ident)

def process(cursor, workitem, ident, signal=None, force_running=False):
    cursor.execute('SELECT * FROM wkf_activity WHERE id = %d',
            (workitem['act_id'],))
    activity = cursor.dictfetchone()
    triggers = False
    if workitem['state'] == 'active':
        triggers = True
        if not _execute(cursor, workitem, activity, ident):
            return False

    if workitem['state'] == 'running':
        pass

    if workitem['state'] == 'complete' or force_running:
        res = _split_test(cursor, workitem, activity['split_mode'], ident,
                signal)
        triggers = triggers and not res

    if triggers:
        cursor.execute('SELECT * FROM wkf_transition ' \
                'WHERE act_from = %d', (workitem['act_id'],))
        alltrans = cursor.dictfetchall()
        for trans in alltrans:
            if trans['trigger_model']:
                ids = wkf_expr.eval_expr(cursor, ident,
                        trans['trigger_expr_id'])
                for res_id in ids:
                    cursor.execute('SELECT NEXTVAL(\'wkf_triggers_id_seq\')')
                    (new_id,) = cursor.fetchone()
                    cursor.execute('INSERT INTO wkf_triggers ' \
                            '(model, res_id, instance_id, workitem_id, id) ' \
                            'VALUES (%s, %d, %d, %d, %d)',
                            (trans['trigger_model'], res_id,
                                workitem['inst_id'], workitem['id'], new_id))
    return True

def _state_set(cursor, workitem, state):
    cursor.execute('UPDATE wkf_workitem ' \
            'SET state = %s WHERE id = %d', (state, workitem['id']))
    workitem['state'] = state

def _execute(cursor, workitem, activity, ident):
    "send a signal to parent workflow (signal: subflow.signal_name)"

    if (workitem['state'] == 'active') and activity['signal_send']:
        # TODO remove subquery
        cursor.execute("SELECT i.id, w.osv, i.res_id " \
                "FROM wkf_instance i " \
                "LEFT JOIN wkf w " \
                    "ON (i.wkf_id = w.id) " \
                "WHERE i.id in (" \
                    "SELECT inst_id FROM wkf_workitem " \
                    "WHERE subflow_id = %d)", (workitem['inst_id'],))
        for i in cursor.fetchall():
            instance.validate(cursor, i[0], (ident[0], i[1], i[2]),
                    activity['signal_send'], force_running=True)

    if activity['kind'] == 'dummy':
        if workitem['state'] == 'active':
            _state_set(cursor, workitem, 'complete')
    elif activity['kind'] == 'function':
        if workitem['state'] == 'active':
            _state_set(cursor, workitem, 'running')
            wkf_expr.execute(cursor, ident, workitem, activity)
            _state_set(cursor, workitem, 'complete')
    elif activity['kind'] == 'stopall':
        if workitem['state'] == 'active':
            _state_set(cursor, workitem, 'running')
            cursor.execute('DELECT FROM wkf_workitem ' \
                    'WHERE inst_id = %d AND id <> %d',
                    (workitem['inst_id'], workitem['id']))
            if activity['action']:
                wkf_expr.execute(cursor, ident, workitem, activity)
            _state_set(cursor, workitem, 'complete')
    elif activity['kind'] == 'subflow':
        if workitem['state'] == 'active':
            _state_set(cursor, workitem, 'running')
            if activity.get('action', False):
                id_new = wkf_expr.execute(cursor, ident, workitem, activity)
                if not (id_new):
                    cursor.execute('DELETE FROM wkf_workitem ' \
                            'WHERE id = %s', (workitem['id'],))
                    return False
                assert type(id_new) == type(1) or type(id_new) == type(1L), \
                        'Wrong return value: ' + str(id_new) + ' ' + \
                        str(type(id_new))
                cursor.execute('SELECT id FROM wkf_instance ' \
                        'WHERE res_id = %d AND wkf_id = %d',
                        (id_new, activity['subflow_id']))
                (id_new,) = cursor.fetchone()
            else:
                id_new = instance.create(cursor, ident, activity['subflow_id'])
            cursor.execute('UPDATE wkf_workitem ' \
                    'SET subflow_id = %d WHERE id = %d',
                    (id_new, workitem['id']))
            workitem['subflow_id'] = id_new
        if workitem['state'] == 'running':
            cursor.execute("SELECT state FROM wkf_instance " \
                    "WHERE id = %d", (workitem['subflow_id'],))
            (state,) = cursor.fetchone()
            if state == 'complete':
                _state_set(cursor, workitem, 'complete')
    return True

def _split_test(cursor, workitem, split_mode, ident, signal=None):
    test = False
    transitions = []
    cursor.execute('SELECT * FROM wkf_transition ' \
            'WHERE act_from = %d', (workitem['act_id'],))
    alltrans = cursor.dictfetchall()
    if split_mode == 'XOR' or split_mode == 'OR':
        for transition in alltrans:
            if wkf_expr.check(cursor, workitem, ident, transition, signal):
                test = True
                transitions.append((transition['id'], workitem['inst_id']))
                if split_mode == 'XOR':
                    break
    else:
        test = True
        for transition in alltrans:
            if not wkf_expr.check(cursor, workitem, ident, transition, signal):
                test = False
                break
            cursor.execute('SELECT COUNT(*) ' \
                    'FROM wkf_witm_trans WHERE trans_id = %d AND inst_id = %d',
                    (transition['id'], workitem['inst_id']))
            (count,) = cursor.fetchone()
            if not count:
                transitions.append((transition['id'], workitem['inst_id']))
    if test and len(transitions):
        cursor.executemany('INSERT INTO wkf_witm_trans ' \
                '(trans_id, inst_id) values (%d, %d)', transitions)
        cursor.execute('DELETE FROM wkf_workitem WHERE id = %d',
                (workitem['id'],))
        for transition in transitions:
            _join_test(cursor, transition[0], transition[1], ident)
        return True
    return False

def _join_test(cursor, trans_id, inst_id, ident):
    # TODO remove the subquery
    cursor.execute('SELECT * FROM wkf_activity ' \
            'WHERE id = (SELECT act_to FROM wkf_transition WHERE id = %d)',
            (trans_id,))
    activity = cursor.dictfetchone()
    if activity['join_mode'] == 'XOR':
        create(cursor, [activity], inst_id, ident)
        cursor.execute('DELETE FROM wkf_witm_trans ' \
                'WHERE inst_id = %d AND trans_id = %d', (inst_id, trans_id))
    else:
        cursor.execute('SELECT id FROM wkf_transition ' \
                'WHERE act_to = %d', (activity['id'],))
        trans_ids = cursor.fetchall()
        delete = True
        for (trans_id,) in trans_ids:
            cursor.execute('SELECT COUNT(*) FROM wkf_witm_trans ' \
                    'WHERE trans_id = %d AND inst_id = %d',
                    (trans_id, inst_id))
            (count,) = cursor.fetchone()
            if not count:
                delete = False
                break
        if delete:
            for (trans_id,) in trans_ids:
                cursor.execute('DELETE FROM wkf_witm_trans ' \
                        'WHERE trans_id = %d AND inst_id = %d',
                        (trans_id, inst_id))
            create(cursor, [activity], inst_id, ident)
