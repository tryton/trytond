#!/usr/bin/env python
import trytond
import time
if 0:
    import profile
    profile.run('trytond.TrytonServer().run()')
else:
    trytond.TrytonServer().run()
while True:
    time.sleep(1)
