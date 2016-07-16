#!/system/xbin/env python3
import census
import os
import re
import sys
# {{{
# 20151201.192009.2997008
# 20151208.185909.3024239
# }}}


def main(sysArgv: list, kwargs=None):
    census.main(sysArgv, kwargs)

if __name__ == '__main__':
    if not (re.search('\A utf [-] 8 \Z', sys.stdout.encoding, re.IGNORECASE | re.VERBOSE)):
        print("please set python env PYTHONIOENCODING=UTF-8.", file=sys.stderr)
        exit(1)
    main([], {'main_caller': os.path.basename(__file__)})
