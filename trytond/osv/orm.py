#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
# -*- coding: utf-8 -*-
from trytond.model import ModelView, ModelSQL

class ORM(ModelSQL, ModelView):
    """
    Object relationnal mapping to postgresql module
       . Hierarchical structure
       . Constraints consistency, validations
       . Object meta Data depends on its status
       . Optimised processing by complex query (multiple actions at once)
       . Default fields value
       . Permissions optimisation
       . Persistant object: DB postgresql
       . Datas conversions
       . Multi-level caching system
       . 2 different inheritancies
       . Fields:
            - classicals (varchar, integer, boolean, ...)
            - relations (one2many, many2one, many2many)
            - functions
    """
