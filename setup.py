#!/usr/bin/env python

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
    #    'psycopg (<2.0)',
    #    'xml',
    #    'egenix-mx-base',
    #],
    cmdclass={
        'sdist': mysdist,
    },
)
