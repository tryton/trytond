#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.config import CONFIG

db_type = CONFIG['db_type']
if db_type == 'sqlite':
    from .sqlite import *
elif db_type == 'mysql':
    from .mysql import *
elif db_type == 'postgresql':
    from .postgresql import *
else:
    raise ValueError('db_type: "%s" is not supported' % db_type)

