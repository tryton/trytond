#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Workflow',
    'category': 'Generic',
    'description': '''Basic module providing concept and administration of workflows.
''',
    'active': True,
    'depends': ['ir', 'res'],
    'xml': [
        'workflow.xml',
        ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ],
}
