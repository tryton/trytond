#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.

from distutils.core import setup
from distutils.command import sdist
import os


class mysdist(sdist.sdist):

    def add_defaults(self):
        sdist.sdist.add_defaults(self)
        if self.distribution.has_pure_modules():
            build_py = self.get_finalized_command('build_py')
            data = []
            for package in build_py.packages:
                src_dir = build_py.get_package_dir(package)
                data.extend(build_py.find_data_files(package, src_dir))
            self.filelist.extend(data)

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
        'trytond.modules',
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
        'trytond.ir': ['*.xml', '*.csv'],
        'trytond.ir.module': ['*.xml'],
        'trytond.ir.ui': ['*.xml', '*.rng', '*.rnc'],
        'trytond.res': ['*.xml', '*.csv'],
        'trytond.webdav': ['*.xml', '*.csv'],
        'trytond.workflow': ['*.xml', '*.csv'],
    },
    data_files=[
        ('/etc', ['etc/trytond.conf']),
    ],
    scripts=['bin/trytond'],
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
    #requires=[
    #    'psycopg (>=2.0)',
    #    'lxml',
    #    'egenix-mx-base',
    #    'relatorio (>=0.2.0),
    #],
    cmdclass={
        'sdist': mysdist,
    },
)
