# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from sql import Table

from trytond.model import Index


class ModelIndexTestCase(unittest.TestCase):
    "Test Model Index"

    def test_index_equality(self):
        "Test Index equality"
        table1 = Table('test')
        index1 = Index(
            table1,
            (table1.name, Index.Equality(order='DESC')),
            (table1.amount, Index.Range()),
            where=table1.name == 'foo')
        table2 = Table('test')
        index2 = Index(
            table2,
            (table2.name, Index.Equality(order='DESC')),
            (table2.amount, Index.Range()),
            where=table2.name == 'foo')

        self.assertEqual(index1, index2)

    def test_index_inequality_table(self):
        "Test Index inequality on table"
        table1 = Table('test')
        index1 = Index(
            table1,
            (table1.name, Index.Equality()))
        table2 = Table('foo')
        index2 = Index(
            table2,
            (table2.name, Index.Equality()))

        self.assertNotEqual(index1, index2)

    def test_index_inequality_expression(self):
        "Test Index inequality on usage"
        table1 = Table('test')
        index1 = Index(
            table1,
            (table1.name, Index.Equality()),
            (table1.amount, Index.Range()))
        table2 = Table('test')
        index2 = Index(
            table2,
            (table2.name, Index.Equality()),
            (table2.value, Index.Range()))

        self.assertNotEqual(index1, index2)

    def test_index_inequality_usage(self):
        "Test Index inequality on usage"
        table1 = Table('test')
        index1 = Index(
            table1,
            (table1.name, Index.Equality()),
            (table1.amount, Index.Range()))
        table2 = Table('test')
        index2 = Index(
            table2,
            (table2.name, Index.Equality()),
            (table2.amount, Index.Similarity()))

        self.assertNotEqual(index1, index2)

    def test_index_inequality_usage_option(self):
        "Test Index inequality on usage option"
        table1 = Table('test')
        index1 = Index(
            table1,
            (table1.name, Index.Equality(order='DESC')),
            (table1.amount, Index.Range()),
            where=table1.name == 'foo')
        table2 = Table('test')
        index2 = Index(
            table2,
            (table2.name, Index.Equality(order='ASC')),
            (table2.amount, Index.Range()),
            where=table2.name == 'foo')

        self.assertNotEqual(index1, index2)

    def test_index_inequality_option_expression(self):
        "Test Index inequality on option param"
        table1 = Table('test')
        index1 = Index(
            table1,
            (table1.name, Index.Equality(order='DESC')),
            (table1.amount, Index.Range()),
            where=table1.name == 'foo')
        table2 = Table('test')
        index2 = Index(
            table2,
            (table2.name, Index.Equality(order='DESC')),
            (table2.amount, Index.Range()),
            where=table2.amount == 'foo')

        self.assertEqual(index1, index2)

    def test_index_inequality_option_param(self):
        "Test Index inequality on option param"
        table1 = Table('test')
        index1 = Index(
            table1,
            (table1.name, Index.Equality(order='DESC')),
            (table1.amount, Index.Range()),
            where=table1.name == 'foo')
        table2 = Table('test')
        index2 = Index(
            table2,
            (table2.name, Index.Equality(order='DESC')),
            (table2.amount, Index.Range()),
            where=table2.name == 'bar')

        self.assertEqual(index1, index2)

    def test_index_hash(self):
        "Test Index hash"
        table1 = Table('test')
        index1 = Index(
            table1,
            (table1.name, Index.Equality(order='DESC')),
            (table1.amount, Index.Range()),
            where=table1.name == 'foo')
        table2 = Table('test')
        index2 = Index(
            table2,
            (table2.name, Index.Equality(order='DESC')),
            (table2.amount, Index.Range()),
            where=table2.name == 'foo')

        self.assertEqual(hash(index1), hash(index2))
