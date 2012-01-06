#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
try:
    import simplejson as json
except ImportError:
    import json

from trytond.model import ModelSQL, fields


class SessionWizard(ModelSQL):
    "Session Wizard"
    _name = 'ir.session.wizard'
    _description = __doc__

    data = fields.Text('Data')

    def __init__(self):
        super(SessionWizard, self).__init__()
        self._rpc = {}

    def default_data(self):
        return json.dumps({})

SessionWizard()
