# -*- coding: utf-8 -*-
import sys
import os
from os import path
from sphinx.util.console import nocolor
from sphinx.application import Sphinx

srcdir = confdir = path.abspath('.')
outdir = os.path.join(srcdir, 'html')
static_dir = os.path.join(srcdir, 'static')
doctreedir = path.join(outdir, '.doctrees')
status = sys.stdout
confoverrides = {}
freshenv = True
buildername = 'html'
if not path.isdir(outdir):
    os.mkdir(outdir)
if not path.isdir(static_dir):
    os.mkdir(static_dir)
nocolor()

app = Sphinx(srcdir, confdir, outdir, doctreedir, buildername,
             confoverrides, status, sys.stderr, freshenv)
app.builder.build_all()

