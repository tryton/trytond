#!/usr/bin/env python

from distutils.core import setup
import os

execfile(os.path.join('trytond', 'version.py'))

setup(name=PACKAGE,
    version=VERSION,
    description='Tryton server',
    author='B2CK',
    author_email='info@b2ck.com',
    url=WEBSITE,
    packages=[
        'trytond',
        'trytond.ir',
        'trytond.ir.module',
        'trytond.ir.ui',
        'trytond.osv',
        'trytond.report',
        'trytond.res',
        'trytond.tools',
        'trytond.webdav',
        'trytond.web_service',
        'trytond.wizard',
        'trytond.wkf_service',
        'trytond.workflow',
    ],
    package_data={
        'trytond': ['init.sql'],
        'trytond.ir': ['*.xml'],
        'trytond.ir.module': ['*.xml'],
        'trytond.ir.ui': ['*.xml'],
        'trytond.res': ['*.xml'],
        'trytond.webdav': ['*.xml'],
        'trytond.workflow': ['*.xml'],
    },
    scripts=['trytond.py'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License Version 2 (GPL-2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ],
    license=LICENSE,
    requires=[
        'psycopg (<2.0)',
        'xml',
        'egenix-mx-base',
    ],
)
