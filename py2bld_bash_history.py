#!/usr/bin/python
# 
# Search for files with a name singnature like:
#
#   bash_history/history.XI1471363091.903699545IX.3724
#
# and combine the commands from all of them
# into 1 history file such that none of the 
# commands will be repeated and the commands
# are ordered to be those most recently run
# from the bash command line
#
# This was originally written in perl and bash
# Then I made a version in python3. But since 
# I want to use the latest version of py3 (I 
# compile it), py3 might not be set up yet at 
# the time this command is invoked. 
#
# So, I thought it wise to convert the py3 to py2 
# since my fundamental bash startup depends on it. 
# That way I can set up bash completely on a new 
# install before I have py3 completely compiled 
# and configured. I used '3to2'
#
#    sudo pip3 install 3to2
#    3to2 -w build_bash_history.py
#
# that got me close to running. but I needed
# to add getfilelist(dir_name)
# to handle the directory scan
#
from __future__ import absolute_import
import sys
import time
import re
import os
import os.path
import scandir
import stat
import errno
import datetime
import shutil
import argparse
from io import open
# {{{ `nullstr` syntactic sugar for ``
#
nullstr = u''
# }}}
# {{{ `space` syntactic sugar for ` `
#
space = unicode(unichr(32))
# }}}
# {{{ `Tab` syntactic sugar for tab
#
tabChr = unicode(unichr(9))
# }}}
# {{{ `ctrlA` syntactic sugar for control-a
#
ctrlA = unicode(unichr(1))
# }}}
# {{{ `fsEncoding`
# default file system encoding for this system
#
# fsEncoding = 'utf-8'  # sys.getfilesystemencoding()
# fsEncoding = 'utf-16'  # sys.getfilesystemencoding()
fsEncoding = sys.getfilesystemencoding()
# }}}

heredoc_end = "MMM"
default_time_stamp = "1458089970"

# {{{ regular expressions 
#
WS = u'[\s]'

h_list_item_re = re.compile(re.sub(WS, nullstr, ur"""
    \A
    ((\d){10})
    (.*)
    """))

time_stamp_re = re.compile(re.sub(WS, nullstr, ur"""
    \A
    [#]
    ((\d){10})
    \Z
    """))

blankline_re = re.compile(re.sub(WS, nullstr, ur"""
    \A
    \s*
    \Z
    """))

heredoc_re = re.compile(re.sub(WS, nullstr, ur"""
    <<
    \s*
    (\w+)
    \s*
    \Z
    """))

heredoc_end_re = re.compile(re.sub(WS, nullstr, ur"""
    \A
    MMM
    \Z
    """))

file_name_re = re.compile(re.sub(WS, nullstr, ur"""
    \A
    history
    [.]
    XI
    (\d){10}
    [.]
    (\d){9}
    IX
    [.]
    \d+
    \Z
    """))
# }}}

def getfilelist(dir_name):
    rtn_list = []
    for base_name in os.listdir(dir_name):
        full_name = os.path.join(dir_name, base_name)
        mode_bits = os.stat(full_name).st_mode
        if not stat.S_ISREG(mode_bits):
            continue
        if stat.S_ISLNK(mode_bits):
            continue
        found = re.search(file_name_re, base_name)
        if not found:
            continue    # skip files that do not match pattern
        rtn_list.append(base_name)    
    return rtn_list

def main(sys_argv, kwargs=None):
    global dblQuote
    dblQuote = u'"'
    d = u'Combine all history files into a single file without repeated commands'
    p = argparse.ArgumentParser(description=d)
    p.add_argument(u'-s', u'--search_path', metavar=u'D0', required=True)
    p.add_argument(u'-o', u'--output_path', metavar=u'D1', required=True)
    p.add_argument(u'-f', u'--output_file', metavar=u'F', required=True)
    arguments = p.parse_args(sys_argv)

    for d in [ (arguments.search_path, u'search_path'),
               (arguments.output_path, u'output_path')  ] :

        if not os.path.isdir(d[0]):
            err_bad_argument = u"** os.path.isdir("
            err_bad_argument += dblQuote
            err_bad_argument += d[0]
            err_bad_argument += dblQuote
            err_bad_argument += u") is False. It is not a directory "
            err_bad_argument += dblQuote
            err_bad_argument += d[1]
            err_bad_argument += dblQuote
            err_bad_argument += u" is not valid **"
            sys.exit(err_bad_argument)

        try:
            os.chdir(d[0])
        except OSError, exc_chdir_fail00:
            err_bad_argument = u"** <Directory> == "
            err_bad_argument += d[0]
            err_bad_argument += u" cannot cd to "
            err_bad_argument += d[1]
            err_bad_argument += u" **\n\n"
            err_bad_argument += unicode(exc_chdir_fail00)
            sys.exit(err_bad_argument)

    # {{{ `search_path`
    # search_path is Directory where the history files live
    # 
    search_path = arguments.search_path
    output_path = arguments.output_path
    output_file = arguments.output_file
    # 
    # }}}

    h_dict = {}
    flist = getfilelist(search_path)
    for entry in flist:
        full_name = os.path.join(search_path, entry)

        if not os.access(full_name, os.R_OK):
            print u"*** Could not access [ ", full_name, u" ] ***"
            continue    # complain then skip what I cannot open

        fH = None
        try:
            fH = open(full_name, u'rt', encoding=fsEncoding)
        except FileNotFoundError:
            print u"*** Could not open [ ", full_name, u" ] ***"

        if not fH:
            continue    # couldn't open the file, get the next one

        scan_state = u"LOOK4TIMESTAMP"
        prior_time_stamp = default_time_stamp
        time_stamp = default_time_stamp
        for text_line in fH: # {{{
            text_line = text_line.rstrip()
            if ( re.search(blankline_re, text_line ) ):
                continue
            if scan_state == u"LOOK4TIMESTAMP": # {{{
                time_stamp_found = re.search(time_stamp_re, text_line)
                if time_stamp_found:
                    scan_state = u"LOOK4COMMAND"
                    prior_time_stamp = time_stamp
                    time_stamp = time_stamp_found.group(1)
                else:
                    #
                    # It is not a time_stamp so it should be a command
                    #
                    if not text_line:
                        text_line = 'ls'
                    h_dict[text_line] = prior_time_stamp # give it the last stamp you found.
                    print u"*** TimeStamp Missing. Found [ ", text_line, u" ] instead. ***"

            elif scan_state == u"LOOK4COMMAND":
                heardoc_found = re.search(heredoc_re, text_line)
                if heardoc_found:
                    scan_state = u"LOOK4HEARDOCEND"
                    heredoc_end = heardoc_found.group(1)
                    heredoc_end_re = re.compile('\A' + heardoc_found.group(1) + '\Z')
                else:
                    scan_state = u"LOOK4TIMESTAMP"
                if text_line in h_dict:
                    if h_dict[text_line] < time_stamp:
                        #
                        # It is not a time_stamp so it should be a command
                        #
                        h_dict[text_line] = time_stamp
                else:
                    h_dict[text_line] = time_stamp
            elif scan_state == u"LOOK4HEARDOCEND":
                if re.search(heredoc_end_re, text_line):
                    #
                    # found the end of the heredoc so 
                    # now ok to look for a timestamp
                    #
                    scan_state = u"LOOK4TIMESTAMP"
                time_stamp_found = re.search(time_stamp_re, text_line)
                if time_stamp_found:
                    #
                    # this catches prior dangling heardocs
                    #
                    time_stamp = time_stamp_found.group(1)
                elif text_line in h_dict:
                    if h_dict[text_line] < time_stamp:
                        h_dict[text_line] = time_stamp
                else:
                    h_dict[text_line] = time_stamp

            # }}}
        # }}}
        fH.close()
    full_name = os.path.join(output_path, output_file)

    fH = None
    try:
        fH = open(full_name, u'wt', encoding=u'utf-8')
    except FileNotFoundError:
        print u"*** Could not open [ ", full_name, u" ] ***"
        exit(1)

    h_list = []
    for i in h_dict:
        h_list.append(unicode(h_dict[i]) + i)

    for i in sorted(h_list):
        #print "i=" + i
        splitter = re.search(h_list_item_re, i)
        fH.write(u"#%s\n" % splitter.group(1))
        fH.write(u"%s\n" % splitter.group(3))

    fH.close()


if __name__ == u'__main__':
    if not (re.search(u'\A utf [-] 8 \Z', sys.stdout.encoding, re.IGNORECASE | re.VERBOSE)):
        print >>sys.stderr, u"please set python env PYTHONIOENCODING=UTF-8."
        exit(1)
    main(sys.argv[1:], {u'main_caller': os.path.basename(__file__)})

