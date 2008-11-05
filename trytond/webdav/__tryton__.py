#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'WebDAV',
    'category': 'Generic',
    'description': '''Basic module providing concept and administration of integrated webDAV features.
''',
    'active': True,
    'depends': ['ir'],
    'xml': [
        'webdav.xml',
    ],
    'translation': [
        'fr_FR.csv',
        'de_DE.csv',
        'es_ES.csv',
    ],
}
