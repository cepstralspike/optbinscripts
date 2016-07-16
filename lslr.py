#!/system/xbin/env python3
import census
import argparse
import os
import re
import sys
# {{{
# 20151201.154520.2284881
# 20151201.171437.3128958
# 20151201.181122.8576819
# 20151201.192009.2997008
# 20151208.185909.3024239
# }}}

dblQuote = None


def main(sysArgv: list, kwargs=None):
    global dblQuote
    dblQuote = '"'
    d = 'Produce recursive descent directory listing sorted by name'
    p = argparse.ArgumentParser(description=d)
    p.add_argument('-d', '--dir', metavar='top_directory', required=True)
    arg01 = p.parse_args(sysArgv)

    if not os.path.isdir(arg01.dir):
        err_bad_arg_00 = "** os.path.isdir("
        err_bad_arg_00 += dblQuote
        err_bad_arg_00 += arg01.dir
        err_bad_arg_00 += dblQuote
        err_bad_arg_00 += ") is False. cannot cd to directory "
        err_bad_arg_00 += dblQuote
        err_bad_arg_00 += arg01.dir
        err_bad_arg_00 += dblQuote
        err_bad_arg_00 += "**"
        sys.exit(err_bad_arg_00)

    try:
        os.chdir(arg01.dir)
    except OSError as exc_chdir_fail00:
        err_bad_arg_00 = "** <topDirectory> == "
        err_bad_arg_00 += arg01.dir
        err_bad_arg_00 += " cannot cd to this directory **\n\n"
        err_bad_arg_00 += str(exc_chdir_fail00)
        sys.exit(err_bad_arg_00)

    census.main([arg01.dir], kwargs)

if __name__ == '__main__':
    if not (re.search('\A utf [-] 8 \Z', sys.stdout.encoding, re.IGNORECASE | re.VERBOSE)):
        print("please set python env PYTHONIOENCODING=UTF-8.", file=sys.stderr)
        exit(1)
    main(sys.argv[1:], {'main_caller': os.path.basename(__file__)})
