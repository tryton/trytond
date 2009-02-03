#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.


class Field(object):
    _type = None

    def __init__(self, string='', help='', required=False, readonly=False,
            domain=None, states=None, priority=0, change_default=False,
            translate=False, select=0, on_change=None, on_change_with=None,
            depends=None, order_field=None, context=None):
        self.string = string
        self.help = help
        self.required = required
        self.readonly = readonly
        self.domain = domain or []
        self.states = states or {}
        self.priority = priority
        self.change_default = change_default
        self.translate = translate
        self.select = select
        self.on_change = on_change
        self.on_change_with = on_change_with
        self.depends = depends or []
        self.order_field = order_field
        self.context = context or ''
