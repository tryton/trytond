#!/usr/bin/env python3
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import glob
import io
import os
import re
import subprocess

from setuptools import Command, find_packages, setup


def read(fname):
    return io.open(
        os.path.join(os.path.dirname(__file__), fname),
        'r', encoding='utf-8').read()


def get_version():
    init = read(os.path.join('trytond', '__init__.py'))
    return re.search('__version__ = "([0-9.]*)"', init).group(1)


class rnc2rng(Command):
    description = "Generate rng files from rnc"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        os.chdir(os.path.dirname(__file__) or '.')
        for path in glob.glob('**/*.rnc', recursive=True):
            root, ext = os.path.splitext(path)
            cmd = ['rnc2rng', path, root + '.rng']
            self.announce(' '.join(cmd))
            subprocess.run(cmd)


version = get_version()
major_version, minor_version, _ = version.split('.', 2)
major_version = int(major_version)
minor_version = int(minor_version)
name = 'trytond'

download_url = 'http://downloads.tryton.org/%s.%s/' % (
    major_version, minor_version)
if minor_version % 2:
    version = '%s.%s.dev0' % (major_version, minor_version)
    download_url = 'hg+http://hg.tryton.org/%s#egg=%s-%s' % (
        name, name, version)
local_version = []
if os.environ.get('CI_JOB_ID'):
    local_version.append(os.environ['CI_JOB_ID'])
else:
    for build in ['CI_BUILD_NUMBER', 'CI_JOB_NUMBER']:
        if os.environ.get(build):
            local_version.append(os.environ[build])
        else:
            local_version = []
            break
if local_version:
    version += '+' + '.'.join(local_version)

dependency_links = []
if minor_version % 2:
    dependency_links.append(
        'https://trydevpi.tryton.org/?local_version='
        + '.'.join(local_version))

tests_require = ['pillow']

setup(name=name,
    version=version,
    description='Tryton server',
    long_description=read('README.rst'),
    author='Tryton',
    author_email='bugs@tryton.org',
    url='http://www.tryton.org/',
    download_url=download_url,
    project_urls={
        "Bug Tracker": 'https://bugs.tryton.org/',
        "Documentation": 'https://docs.tryton.org/',
        "Forum": 'https://www.tryton.org/forum',
        "Source Code": 'https://hg.tryton.org/trytond',
        },
    keywords='business application platform ERP',
    packages=find_packages(exclude=['*.modules.*', 'modules.*', 'modules',
            '*.proteus.*', 'proteus.*', 'proteus']),
    package_data={
        'trytond': ['ir/ui/icons/*.svg', '*.rnc', '*.rng', 'ir/fonts/*.ttf'],
        'trytond.backend.postgresql': ['init.sql'],
        'trytond.backend.sqlite': ['init.sql'],
        'trytond.ir': ['tryton.cfg', '*.xml', 'view/*.xml', 'locale/*.po'],
        'trytond.ir.module': ['*.xml'],
        'trytond.ir.ui': ['*.xml', '*.rng', '*.rnc'],
        'trytond.res': [
            'tryton.cfg', '*.xml', '*.html', 'view/*.xml', 'locale/*.po'],
        'trytond.tests': ['tryton.cfg', '*.xml', 'forbidden.txt'],
        },
    scripts=[
        'bin/trytond',
        'bin/trytond-admin',
        'bin/trytond-console',
        'bin/trytond-cron',
        'bin/trytond-worker',
        'bin/trytond-stat',
        ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: No Input/Output (Daemon)',
        'Framework :: Tryton',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: '
        'GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: Bulgarian',
        'Natural Language :: Catalan',
        'Natural Language :: Chinese (Simplified)',
        'Natural Language :: Czech',
        'Natural Language :: Dutch',
        'Natural Language :: English',
        'Natural Language :: Finnish',
        'Natural Language :: French',
        'Natural Language :: German',
        'Natural Language :: Hungarian',
        'Natural Language :: Indonesian',
        'Natural Language :: Italian',
        'Natural Language :: Persian',
        'Natural Language :: Polish',
        'Natural Language :: Portuguese (Brazilian)',
        'Natural Language :: Romanian',
        'Natural Language :: Russian',
        'Natural Language :: Slovenian',
        'Natural Language :: Spanish',
        'Natural Language :: Turkish',
        'Natural Language :: Ukrainian',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        ],
    platforms='any',
    license='GPL-3',
    python_requires='>=3.7',
    install_requires=[
        'defusedxml',
        'lxml >= 2.0',
        'relatorio[fodt] >= 0.7.0',
        'Genshi',
        'python-dateutil',
        'polib',
        'python-sql >= 1.3',
        'werkzeug',
        'wrapt',
        'passlib >= 1.7.0',
        'pytz;python_version<"3.9"',
        ],
    extras_require={
        'test': tests_require,
        'PostgreSQL': ['psycopg2 >= 2.7.0'],
        'graphviz': ['pydot'],
        'Levenshtein': ['python-Levenshtein'],
        'BCrypt': ['passlib[bcrypt]'],
        'Argon2': ['passlib[argon2]'],
        'html2text': ['html2text'],
        'weasyprint': ['weasyprint'],
        'coroutine': ['gevent>=1.1'],
        'image': ['pillow'],
        'completion': ['argcomplete'],
        },
    dependency_links=dependency_links,
    zip_safe=False,
    cmdclass={
        'update_rng': rnc2rng,
        },
    )
