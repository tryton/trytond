#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
import sys
import time
try:
    from itertools import combinations
except ImportError:
    def combinations(iterable, r):
        pool = tuple(iterable)
        n = len(pool)
        if r > n:
            return
        indices = range(r)
        yield tuple(pool[i] for i in indices)
        while True:
            for i in reversed(range(r)):
                if indices[i] != i + n - r:
                    break
            else:
                return
            indices[i] += 1
            for j in range(i+1, r):
                indices[j] = indices[j-1] + 1
            yield tuple(pool[i] for i in indices)
from trytond.tests.test_tryton import POOL, DB, USER, CONTEXT, install_module
from trytond.test.trigger import TRIGGER_LOGS


class TriggerTestCase(unittest.TestCase):
    '''
    Test Trigger
    '''

    def setUp(self):
        install_module('test')
        self.triggered = POOL.get('test.triggered')
        self.trigger = POOL.get('ir.trigger')
        self.trigger_log = POOL.get('ir.trigger.log')
        self.model = POOL.get('ir.model')

    def test0010constraints(self):
        '''
        Test constraints
        '''
        cursor = DB.cursor()

        model_id = self.model.search(cursor, USER, [
            ('model', '=', 'test.triggered'),
            ], context=CONTEXT)[0]

        values = {
            'name': 'Test',
            'model': model_id,
            'on_time': True,
            'condition': 'True',
            'action_model': model_id,
            'action_function': 'test',
        }
        self.assert_(self.trigger.create(cursor, USER, values, context=CONTEXT))

        # on_exclusive
        for i in range(1, 4):
            for combination in combinations(['create', 'write', 'delete'], i):
                combination_values = values.copy()
                for mode in combination:
                    combination_values['on_%s' % mode] = True
                self.failUnlessRaises(Exception, self.trigger.create, cursor, USER,
                        combination_values, context=CONTEXT)

        # check_condition
        condition_values = values.copy()
        condition_values['condition'] = '='
        self.failUnlessRaises(Exception, self.trigger.create, cursor, USER,
                condition_values, context=CONTEXT)

        # Restart the cache on the get_triggers method of ir.trigger
        self.trigger.get_triggers(cursor.dbname)
        cursor.rollback()
        cursor.close()

    def test0020on_create(self):
        '''
        Test on_create
        '''
        cursor = DB.cursor()

        model_id = self.model.search(cursor, USER, [
            ('model', '=', 'test.triggered'),
            ], context=CONTEXT)[0]

        trigger_id = self.trigger.create(cursor, USER, {
            'name': 'Test',
            'model': model_id,
            'on_create': True,
            'condition': 'True',
            'action_model': model_id,
            'action_function': 'trigger',
            }, context=CONTEXT)

        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Test',
            }, context=CONTEXT)

        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Trigger with condition
        self.trigger.write(cursor, USER, trigger_id, {
            'condition': 'self.name == "Bar"',
            }, context=CONTEXT)

        # Matching condition
        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Bar',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Non matching condition
        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Foo',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [])

        # With limit number
        self.trigger.write(cursor, USER, trigger_id, {
            'condition': 'True',
            'limit_number': 1,
            }, context=CONTEXT)
        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Test',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # With minimum delay
        self.trigger.write(cursor, USER, trigger_id, {
            'limit_number': 0,
            'minimum_delay': 1,
            }, context=CONTEXT)
        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Test',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Restart the cache on the get_triggers method of ir.trigger
        self.trigger.get_triggers(cursor.dbname)
        cursor.rollback()
        cursor.close()

    def test0030on_write(self):
        '''
        Test on_write
        '''
        cursor = DB.cursor()

        model_id = self.model.search(cursor, USER, [
            ('model', '=', 'test.triggered'),
            ], context=CONTEXT)[0]

        trigger_id = self.trigger.create(cursor, USER, {
            'name': 'Test',
            'model': model_id,
            'on_write': True,
            'condition': 'True',
            'action_model': model_id,
            'action_function': 'trigger',
            }, context=CONTEXT)

        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Test',
            }, context=CONTEXT)

        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Foo',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [])

        # Trigger with condition
        self.trigger.write(cursor, USER, trigger_id, {
            'condition': 'self.name == "Bar"',
            }, context=CONTEXT)

        # Matching condition
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Bar',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # No change in condition
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Bar',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [])

        # Different change in condition
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Foo',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [])

        # With limit number
        self.trigger.write(cursor, USER, trigger_id, {
            'condition': 'self.name == "Bar"',
            'limit_number': 1,
            }, context=CONTEXT)
        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Foo',
            }, context=CONTEXT)
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Bar',
            }, context=CONTEXT)
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Foo',
            }, context=CONTEXT)
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Bar',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # With minimum delay
        self.trigger.write(cursor, USER, trigger_id, {
            'limit_number': 0,
            'minimum_delay': sys.maxint,
            }, context=CONTEXT)
        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Foo',
            }, context=CONTEXT)
        for name in ('Bar', 'Foo', 'Bar'):
            self.triggered.write(cursor, USER, triggered_id, {
                'name': name,
                }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        self.trigger.write(cursor, USER, trigger_id, {
            'minimum_delay': 0.02,
            }, context=CONTEXT)
        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Foo',
            }, context=CONTEXT)
        for name in ('Bar', 'Foo'):
            self.triggered.write(cursor, USER, triggered_id, {
                'name': name,
                }, context=CONTEXT)
        time.sleep(1.2)
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Bar',
            }, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id),
            ([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()
        TRIGGER_LOGS.pop()

        # Restart the cache on the get_triggers method of ir.trigger
        self.trigger.get_triggers(cursor.dbname)
        cursor.rollback()
        cursor.close()

    def test0040on_delete(self):
        '''
        Test on_delete
        '''
        cursor = DB.cursor()

        model_id = self.model.search(cursor, USER, [
            ('model', '=', 'test.triggered'),
            ], context=CONTEXT)[0]

        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Test',
            }, context=CONTEXT)

        trigger_id = self.trigger.create(cursor, USER, {
            'name': 'Test',
            'model': model_id,
            'on_delete': True,
            'condition': 'True',
            'action_model': model_id,
            'action_function': 'trigger',
            }, context=CONTEXT)

        self.triggered.delete(cursor, USER, triggered_id, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Trigger with condition
        self.trigger.write(cursor, USER, trigger_id, {
            'condition': 'self.name == "Bar"',
            }, context=CONTEXT)

        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Bar',
            }, context=CONTEXT)

        # Matching condition
        self.triggered.delete(cursor, USER, triggered_id, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Foo',
            }, context=CONTEXT)

        # Non matching condition
        self.triggered.delete(cursor, USER, triggered_id, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [])

        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Test',
            }, context=CONTEXT)

        # With limit number
        self.trigger.write(cursor, USER, trigger_id, {
            'condition': 'True',
            'limit_number': 1,
            }, context=CONTEXT)
        self.triggered.delete(cursor, USER, triggered_id, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()
        # Delete trigger logs because SQLite reuse the same triggered_id
        self.trigger_log.delete(cursor, USER,
                self.trigger_log.search(cursor, USER, [
                    ('trigger', '=', trigger_id),
                    ], context=CONTEXT))

        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Test',
            }, context=CONTEXT)

        # With minimum delay
        self.trigger.write(cursor, USER, trigger_id, {
            'limit_number': 0,
            'minimum_delay': 1,
            }, context=CONTEXT)
        self.triggered.delete(cursor, USER, triggered_id, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Restart the cache on the get_triggers method of ir.trigger
        self.trigger.get_triggers(cursor.dbname)
        cursor.rollback()
        cursor.close()

    def test0050on_time(self):
        '''
        Test on_time
        '''
        cursor = DB.cursor()

        model_id = self.model.search(cursor, USER, [
            ('model', '=', 'test.triggered'),
            ], context=CONTEXT)[0]

        trigger_id = self.trigger.create(cursor, USER, {
            'name': 'Test',
            'model': model_id,
            'on_time': True,
            'condition': 'True',
            'action_model': model_id,
            'action_function': 'trigger',
            }, context=CONTEXT)

        triggered_id = self.triggered.create(cursor, USER, {
            'name': 'Test',
            }, context=CONTEXT)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Trigger with condition
        self.trigger.write(cursor, USER, trigger_id, {
            'condition': 'self.name == "Bar"',
            }, context=CONTEXT)

        # Matching condition
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Bar',
            }, context=CONTEXT)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Non matching condition
        self.triggered.write(cursor, USER, triggered_id, {
            'name': 'Foo',
            }, context=CONTEXT)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [])

        # With limit number
        self.trigger.write(cursor, USER, trigger_id, {
            'condition': 'True',
            'limit_number': 1,
            }, context=CONTEXT)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Delete trigger logs of limit number test
        self.trigger_log.delete(cursor, USER,
                self.trigger_log.search(cursor, USER, [
                    ('trigger', '=', trigger_id),
                    ], context=CONTEXT))

        # With minimum delay
        self.trigger.write(cursor, USER, trigger_id, {
            'limit_number': 0,
            'minimum_delay': sys.maxint,
            }, context=CONTEXT)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()

        # Delete trigger logs of previous minimum delay test
        self.trigger_log.delete(cursor, USER,
                self.trigger_log.search(cursor, USER, [
                    ('trigger', '=', trigger_id),
                    ], context=CONTEXT))

        self.trigger.write(cursor, USER, trigger_id, {
            'minimum_delay': 0.02,
            }, context=CONTEXT)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        time.sleep(1.2)
        self.trigger.trigger_time(cursor, USER, context=CONTEXT)
        self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id),
            ([triggered_id], trigger_id)])
        TRIGGER_LOGS.pop()
        TRIGGER_LOGS.pop()

        # Restart the cache on the get_triggers method of ir.trigger
        self.trigger.get_triggers(cursor.dbname)
        cursor.rollback()
        cursor.close()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TriggerTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
