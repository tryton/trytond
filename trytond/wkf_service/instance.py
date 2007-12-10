import workitem

def create(cursor, ident, wkf_id):
    (user, res_type, res_id) = ident
    cursor.execute("SELECT NEXTVAL('wkf_instance_id_seq')")
    (id_new,) = cursor.fetchone()
    cursor.execute('INSERT INTO wkf_instance ' \
            '(id, res_type, res_id, uid, wkf_id) VALUES (%d,%s,%s,%s,%s)',
            (id_new, res_type, res_id, user, wkf_id))
    cursor.execute('SELECT * FROM wkf_activity ' \
            'WHERE flow_start = True and wkf_id = %d', (wkf_id,))
    res = cursor.dictfetchall()
    workitem.create(cursor, res, id_new, ident)
    update(cursor, id_new, ident)
    return id_new

def delete(cursor, ident):
    (user, res_type, res_id) = ident
    cursor.execute('DELETE FROM wkf_instance ' \
            'WHERE res_id = %d AND res_type = %s', (res_id, res_type))

def validate(cursor, inst_id, ident, signal, force_running=False):
    cursor.execute("SELECT * FROM wkf_workitem WHERE inst_id = %d", (inst_id,))
    for witem in cursor.dictfetchall():
        workitem.process(cursor, witem, ident, signal, force_running)
    return _update_end(cursor, inst_id, ident)

def update(cursor, inst_id, ident):
    cursor.execute("SELECT * FROM wkf_workitem WHERE inst_id = %d", (inst_id,))
    for witem in cursor.dictfetchall():
        workitem.process(cursor, witem, ident)
    return _update_end(cursor, inst_id, ident)

def _update_end(cursor, inst_id, ident):
    cursor.execute('SELECT state, flow_stop FROM wkf_workitem w ' \
            'LEFT JOIN wkf_activity a ' \
                'ON (a.id = w.act_id) WHERE w.inst_id = %d', (inst_id,))
    res = True
    for row in cursor.fetchall():
        if (row[0] != 'complete') or not row[1]:
            res = False
            break
    if res:
        cursor.execute('SELECT DISTINCT a.name FROM wkf_activity a ' \
                'LEFT JOIN wkf_workitem w ' \
                    'ON (a.id = w.act_id) ' \
                'WHERE w.inst_id = %d', (inst_id,))
        act_names = cursor.fetchall()
        cursor.execute("UPDATE wkf_instance " \
                "SET state = 'complete' WHERE id = %d", (inst_id,))
        cursor.execute("UPDATE wkf_workitem " \
                "SET state = 'complete' WHERE subflow_id = %d", (inst_id,))
        # TODO remove the subquery
        cursor.execute("SELECT i.id, w.osv, i.res_id " \
                "FROM wkf_instance i " \
                    "LEFT JOIN wkf w ON (i.wkf_id = w.id) " \
                "WHERE i.id IN (" \
                    "SELECT inst_id FROM wkf_workitem " \
                    "WHERE subflow_id = %d)", (inst_id,))
        for i in cursor.fetchall():
            for act_name in act_names:
                validate(cursor, i[0], (ident[0], i[1], i[2]),
                        'subflow.' + act_name[0])
    return res
