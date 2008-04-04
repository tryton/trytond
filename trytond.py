#!/usr/bin/env python
import trytond
if 0:
    import profile
    import pstats
    import tempfile
    import os

    statfile = tempfile.mkstemp(".stat","trytond-")[1]
    profile.run('trytond.TrytonServer().run()', statfile)
    s = pstats.Stats(statfile)
    s.strip_dirs().sort_stats('cumulative').print_stats(50)
    s.strip_dirs().sort_stats('call').print_stats(50)
    s.strip_dirs().sort_stats('time').print_stats(50)
    s.strip_dirs().sort_stats('time')
    s.print_callers(20)
    s.print_callees(20)

    os.remove(statfile)

else:
    trytond.TrytonServer().run()
