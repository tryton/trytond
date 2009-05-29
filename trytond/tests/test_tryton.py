#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import time
from trytond import pysocket

ADMIN_PASSWORD = 'admin'
HOST = '127.0.0.1'
PORT = '8070'
DB_NAME = 'test_' + str(int(time.time()))
USERNAME = 'admin'
PASSWORD = 'admin'
CONTEXT = {}
USER = None
SESSION = None

SOCK = pysocket.PySocket()
SOCK.connect(HOST, PORT)

class DBTestCase(unittest.TestCase):
    '''
    Test DB service.
    '''

    def test0010create(self):
        '''
        Create database.
        '''
        SOCK.send((None, None, None, 'common', 'db', 'create', DB_NAME,
            ADMIN_PASSWORD, 'en_US', PASSWORD))
        res = SOCK.receive()
        self.assert_(res)

    def test0020list(self):
        '''
        List databases.
        '''
        SOCK.send((None, None, None, 'common', 'db', 'list'))
        res = SOCK.receive()
        self.assert_(DB_NAME in res)

    def test0030login(self):
        '''
        Login.
        '''
        login()


class FieldsTestCase(unittest.TestCase):
    '''
    Test Fields.
    '''

    def setUp(self):
        install_module('tests')
        self.boolean = RPCProxy('tests.boolean')
        self.boolean_default = RPCProxy('tests.boolean_default')
        self.boolean_required = RPCProxy('tests.boolean_required')

        self.integer = RPCProxy('tests.integer')
        self.integer_default = RPCProxy('tests.integer_default')

        self.float = RPCProxy('tests.float')
        self.float_default = RPCProxy('tests.float_default')

    def test0010boolean(self):
        '''
        Test Boolean.
        '''
        boolean1_id = self.boolean.create({
            'boolean': True,
            }, CONTEXT)
        self.assert_(boolean1_id)

        boolean1 = self.boolean.read(boolean1_id, ['boolean'], CONTEXT)
        self.assert_(boolean1['boolean'] == True)

        boolean_ids = self.boolean.search([
            ('boolean', '=', True),
            ], CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean_ids = self.boolean.search([
            ('boolean', '!=', True),
            ], CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search([
            ('boolean', 'in', [True]),
            ], CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean_ids = self.boolean.search([
            ('boolean', 'in', [False]),
            ], CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search([
            ('boolean', 'not in', [True]),
            ], CONTEXT)
        self.assert_(boolean_ids == [])

        boolean_ids = self.boolean.search([
            ('boolean', 'not in', [False]),
            ], CONTEXT)
        self.assert_(boolean_ids == [boolean1_id])

        boolean2_id = self.boolean.create({
            'boolean': False,
            }, CONTEXT)
        self.assert_(boolean2_id)

        boolean2 = self.boolean.read(boolean2_id, ['boolean'], CONTEXT)
        self.assert_(boolean2['boolean'] == False)

        boolean_ids = self.boolean.search([
            ('boolean', '=', False),
            ], CONTEXT)
        self.assert_(boolean_ids == [boolean2_id])

        boolean_ids = self.boolean.search([
            ('boolean', 'in', [True, False]),
            ], CONTEXT)
        self.assert_(boolean_ids == [boolean1_id, boolean2_id])

        boolean_ids = self.boolean.search([
            ('boolean', 'not in', [True, False]),
            ], CONTEXT)
        self.assert_(boolean_ids == [])

        boolean3_id = self.boolean.create({}, CONTEXT)
        self.assert_(boolean3_id)

        boolean3 = self.boolean.read(boolean3_id, ['boolean'], CONTEXT)
        self.assert_(boolean3['boolean'] == False)

        boolean4_id = self.boolean_default.create({}, CONTEXT)
        self.assert_(boolean4_id)

        boolean4 = self.boolean_default.read(boolean4_id, ['boolean'], CONTEXT)
        self.assert_(boolean4['boolean'] == True)

        boolean5_id = self.boolean_required.create({}, CONTEXT)
        self.assert_(boolean5_id)

        self.boolean.write(boolean1_id, {
            'boolean': False,
            }, CONTEXT)
        boolean1 = self.boolean.read(boolean1_id, ['boolean'], CONTEXT)
        self.assert_(boolean1['boolean'] == False)

        self.boolean.write(boolean2_id, {
            'boolean': True,
            }, CONTEXT)
        boolean2 = self.boolean.read(boolean2_id, ['boolean'], CONTEXT)
        self.assert_(boolean2['boolean'] == True)

    def test0020integer(self):
        '''
        Test Integer.
        '''
        integer1_id = self.integer.create({
            'integer': 1,
            }, CONTEXT)
        self.assert_(integer1_id)

        integer1 = self.integer.read(integer1_id, ['integer'], CONTEXT)
        self.assert_(integer1['integer'] == 1)

        integer_ids = self.integer.search([
            ('integer', '=', 1),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '=', 0),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '!=', 1),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '!=', 0),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', 'in', [1]),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', 'in', [0]),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', 'in', []),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', 'not in', [1]),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', 'not in', [0]),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', 'not in', []),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '<', 5),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '<', -5),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '<', 1),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '<=', 5),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '<=', -5),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '<=', 1),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '>', 5),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '>', -5),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '>', 1),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '>=', 5),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer_ids = self.integer.search([
            ('integer', '>=', -5),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer_ids = self.integer.search([
            ('integer', '>=', 1),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id])

        integer2_id = self.integer.create({
            'integer': 0,
            }, CONTEXT)
        self.assert_(integer2_id)

        integer2 = self.integer.read(integer2_id, ['integer'], CONTEXT)
        self.assert_(integer2['integer'] == 0)

        integer_ids = self.integer.search([
            ('integer', '=', 0),
            ], CONTEXT)
        self.assert_(integer_ids == [integer2_id])

        integer_ids = self.integer.search([
            ('integer', 'in', [0, 1]),
            ], CONTEXT)
        self.assert_(integer_ids == [integer1_id, integer2_id])

        integer_ids = self.integer.search([
            ('integer', 'not in', [0, 1]),
            ], CONTEXT)
        self.assert_(integer_ids == [])

        integer3_id = self.integer.create({}, CONTEXT)
        self.assert_(integer3_id)

        integer3 = self.integer.read(integer3_id, ['integer'], CONTEXT)
        self.assert_(integer3['integer'] == 0)

        integer4_id = self.integer_default.create({}, CONTEXT)
        self.assert_(integer4_id)

        integer4 = self.integer_default.read(integer4_id, ['integer'], CONTEXT)
        self.assert_(integer4['integer'] == 5)

        self.integer.write(integer1_id, {
            'integer': 0,
            }, CONTEXT)
        integer1 = self.integer.read(integer1_id, ['integer'], CONTEXT)
        self.assert_(integer1['integer'] == 0)

        self.integer.write(integer2_id, {
            'integer': 1,
            }, CONTEXT)
        integer2 = self.integer.read(integer2_id, ['integer'], CONTEXT)
        self.assert_(integer2['integer'] == 1)

        self.failUnlessRaises(Exception, self.integer.create, {
            'integer': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.integer.write, integer1_id, {
            'integer': 'test',
            }, CONTEXT)

    def test0030float(self):
        '''
        Test Float.
        '''
        float1_id = self.float.create({
            'float': 1.1,
            }, CONTEXT)
        self.assert_(float1_id)

        float1 = self.float.read(float1_id, ['float'], CONTEXT)
        self.assert_(float1['float'] == 1.1)

        float_ids = self.float.search([
            ('float', '=', 1.1),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '=', 0),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '!=', 1.1),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '!=', 0),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', 'in', [1.1]),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', 'in', [0]),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', 'in', []),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', 'not in', [1.1]),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', 'not in', [0]),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', 'not in', []),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '<', 5),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '<', -5),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '<', 1.1),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '<=', 5),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '<=', -5),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '<=', 1.1),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '>', 5),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '>', -5),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '>', 1.1),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '>=', 5),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float_ids = self.float.search([
            ('float', '>=', -5),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float_ids = self.float.search([
            ('float', '>=', 1.1),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id])

        float2_id = self.float.create({
            'float': 0,
            }, CONTEXT)
        self.assert_(float2_id)

        float2 = self.float.read(float2_id, ['float'], CONTEXT)
        self.assert_(float2['float'] == 0)

        float_ids = self.float.search([
            ('float', '=', 0),
            ], CONTEXT)
        self.assert_(float_ids == [float2_id])

        float_ids = self.float.search([
            ('float', 'in', [0, 1.1]),
            ], CONTEXT)
        self.assert_(float_ids == [float1_id, float2_id])

        float_ids = self.float.search([
            ('float', 'not in', [0, 1.1]),
            ], CONTEXT)
        self.assert_(float_ids == [])

        float3_id = self.float.create({}, CONTEXT)
        self.assert_(float3_id)

        float3 = self.float.read(float3_id, ['float'], CONTEXT)
        self.assert_(float3['float'] == 0)

        float4_id = self.float_default.create({}, CONTEXT)
        self.assert_(float4_id)

        float4 = self.float_default.read(float4_id, ['float'], CONTEXT)
        self.assert_(float4['float'] == 5.5)

        self.float.write(float1_id, {
            'float': 0,
            }, CONTEXT)
        float1 = self.float.read(float1_id, ['float'] , CONTEXT)
        self.assert_(float1['float'] == 0)

        self.float.write(float2_id, {
            'float': 1.1,
            }, CONTEXT)
        float2 = self.float.read(float2_id, ['float'], CONTEXT)
        self.assert_(float2['float'] == 1.1)

        self.failUnlessRaises(Exception, self.float.create, {
            'float': 'test',
            }, CONTEXT)

        self.failUnlessRaises(Exception, self.float.write, float1_id, {
            'float': 'test',
            }, CONTEXT)


class MPTTTestCase(unittest.TestCase):
    '''
    Test Modified Preorder Tree Traversal.
    '''

    def setUp(self):
        install_module('tests')
        self.mptt = RPCProxy('tests.mptt')

    def CheckTree(self, parent_id=False, left=0, right=0):
        child_ids = self.mptt.search([
            ('parent', '=', parent_id),
            ], 0, None, None, CONTEXT)
        childs = self.mptt.read(child_ids, ['left', 'right'], CONTEXT)
        childs.sort(lambda x, y: cmp(child_ids.index(x['id']),
            child_ids.index(y['id'])))
        for child in childs:
            if child['left'] <= left:
                raise Exception('Record (%d): left %d <= parent left %d' % \
                        (child['id'], child['left'], left))
            if child['left'] >= child['right']:
                raise Exception('Record (%d): left %d >= right %d' % \
                        (child['id'], child['left'], child['right']))
            if right != 0 and child['right'] >= right:
                raise Exception('Record (%d): right %d >= parent right %d' % \
                        (child['id'], child['right'], right))
            self.CheckTree(child['id'], left=child['left'],
                    right=child['right'])
        next_left = 0
        for child in childs:
            if child['left'] <= next_left:
                raise Exception('Record (%d): left %d <= next left %d' % \
                        (child['id'], child['left'], next_left))
            next_left = child['right']
        childs.reverse()
        previous_right = 0
        for child in childs:
            if previous_right != 0 and child['right'] >= previous_right:
                raise Exception('Record (%d): right %d >= previous right %d' % \
                        (child['id'] , child['right'], previous_right))
            previous_right = child['left']

    def test0010create(self):
        '''
        Create tree.
        '''
        new_records = [False]
        for j in range(3):
            parent_records = new_records
            new_records = []
            k = 0
            for parent_record in parent_records:
                for i in range(3):
                    record_id = self.mptt.create({
                        'name': 'Test %d %d %d' % (j, k, i),
                        'parent': parent_record,
                        }, CONTEXT)
                    new_records.append(record_id)
                k += 1
        self.assertRaises(Exception, self.CheckTree())

    def test0020reorder(self):
        '''
        Re-order.
        '''
        def reorder(parent_id=False):
            record_ids = self.mptt.search([
                ('parent', '=', parent_id),
                ], CONTEXT)
            if not record_ids:
                return
            i = len(record_ids)
            for record_id in record_ids:
                self.mptt.write(record_id, {
                    'sequence': i,
                    }, CONTEXT)
                i -= 1
                self.assertRaises(Exception, self.CheckTree())
            i = 0
            for record_id in record_ids:
                self.mptt.write(record_id, {
                    'sequence': i,
                    }, CONTEXT)
                i += 1
                self.assertRaises(Exception, self.CheckTree())
            for record_id in record_ids:
                reorder(record_id)
        reorder()
        record_ids = self.mptt.search([], CONTEXT)
        self.mptt.write(record_ids, {
            'sequence': 0,
            }, CONTEXT)
        self.assertRaises(Exception, self.CheckTree())

    def test0030reparent(self):
        '''
        Re-parent.
        '''
        def reparent(parent_id=False):
            record_ids = self.mptt.search([
                ('parent', '=', parent_id),
                ], CONTEXT)
            if not record_ids:
                return
            for record_id in record_ids:
                for record2_id in record_ids:
                    if record_id != record2_id:
                        self.mptt.write(record_id, {
                            'parent': record2_id,
                            }, CONTEXT)
                        self.assertRaises(Exception, self.CheckTree())
                        self.mptt.write(record_id, {
                            'parent': parent_id,
                            }, CONTEXT)
                        self.assertRaises(Exception, self.CheckTree())
            for record_id in record_ids:
                reparent(record_id)
        reparent()

    def test0040delete(self):
        '''
        Delete.
        '''
        record_ids = self.mptt.search([], CONTEXT)
        for record_id in record_ids:
            if record_id % 2:
                self.mptt.delete(record_id, CONTEXT)
                self.assertRaises(Exception, self.CheckTree())
        record_ids = self.mptt.search([], CONTEXT)
        self.mptt.delete(record_ids[:len(record_ids)/2], CONTEXT)
        self.assertRaises(Exception, self.CheckTree())
        record_ids = self.mptt.search([], CONTEXT)
        self.mptt.delete(record_ids, CONTEXT)
        self.assertRaises(Exception, self.CheckTree())


class RPCProxy(object):

    def __init__(self, name):
        self.name = name
        self.__attrs = {}

    def __getattr__(self, attr):
        if attr not in self.__attrs:
            self.__attrs[attr] = RPCFunction(self.name, attr)
        return self.__attrs[attr]


class RPCFunction(object):

    def __init__(self, name, func_name):
        self.name = name
        self.func_name = func_name

    def __call__(self, *args):
        SOCK.send((DB_NAME, USER, SESSION, 'model', self.name, self.func_name) \
                + args)
        res = SOCK.receive()
        return res

def login():
    global USER, SESSION, CONTEXT
    SOCK.send((DB_NAME, USERNAME, PASSWORD, 'common', 'db', 'login'))
    USER, SESSION = SOCK.receive()
    user = RPCProxy('res.user')
    context = user.get_preferences(True, {})
    for i in context:
        value = context[i]
        CONTEXT[i] = value

def install_module(name):
    module = RPCProxy('ir.module.module')
    module_ids = module.search([
        ('name', '=', name),
        ('state', '!=', 'installed'),
        ])

    if not module_ids:
        return

    module.button_install(module_ids, CONTEXT)

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'create'))
    wiz_id = SOCK.receive()

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'execute', wiz_id, {}, 'start',
        CONTEXT))
    SOCK.receive()

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'delete', wiz_id))
    SOCK.receive()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(DBTestCase)

if __name__ == '__main__':
    suite = suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FieldsTestCase))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(MPTTTestCase))
    unittest.TextTestRunner(verbosity=2).run(suite)
    SOCK.disconnect()
