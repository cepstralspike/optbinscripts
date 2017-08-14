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
# Then I made a version in python3. But sometimes 
# Sometimes I want to use the latest version of py3 
# (git clone; configure; make install) without 
# breaking the py3 version from apt, py3 might not 
# be set up yet.
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

default_heredoc_end = "QUIT_LOOKING_GNIKOOL_TIUQ"
default_time_stamp = "1200000000"
default_text_line = "echo default_text_line"
heredoc_list = []
heredoc_timestamp = default_time_stamp

# {{{ regular expressions 
#
WS = u'[\s]'

double_lessthan_re = re.compile('[<][<]')


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
    [#]{0,1}
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
    #
    # Get the names of all the files in a directory
    # return those names in a single list (rtn_list)
    #
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

    cmd_tstamp_keyvalue_pairs = {}
    flist = getfilelist(search_path)
    for base_name in flist:
        full_name = os.path.join(search_path, base_name)

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
        text_line = default_text_line
        time_stamp = default_time_stamp
        heredoc_end = default_heredoc_end 
        line_number = 0
        for text_line in fH: # {{{
            line_number = line_number + 1
            error_locator = '{0:07d}:{1}'.format(line_number, base_name)
            text_line = text_line.rstrip()
            if ( re.search(blankline_re, text_line ) ):
                continue #51FE142E 
            if scan_state == u"LOOK4TIMESTAMP": # {{{
                heredoc_found = re.search(heredoc_re, text_line)
                time_stamp_found = re.search(time_stamp_re, text_line)
                if heredoc_found:
                    scan_state = u"LOOK4HEREDOCEND"
                    heredoc_end = heredoc_found.group(1)
                    heredoc_end_re = re.compile('\A' + heredoc_found.group(1) + '\Z')
                    heredoc_list = []
                    heredoc_timestamp = time_stamp
                    heredoc_list.append(text_line)
                elif time_stamp_found:
                    scan_state = u"LOOK4COMMAND"
                    prior_time_stamp = time_stamp
                    time_stamp = time_stamp_found.group(1)
                else:
                    scan_state = u"LOOK4TIMESTAMP"
                    #
                    # Not a timestamp
                    # Not a Heredoc
                    # Not Blank
                    # Must be command
                    #
                    if text_line in cmd_tstamp_keyvalue_pairs:
                        if cmd_tstamp_keyvalue_pairs[text_line] < time_stamp:
                            #
                            # It is not a time_stamp and
                            # up top at (#51FE142E) I filter out all blank
                            # lines, so it should be safe to
                            # treat it like a command.
                            #
                            cmd_tstamp_keyvalue_pairs[text_line] = time_stamp
                    else:
                        #
                        # This is the first time we've seen this command line
                        # put a new entry in the keyvalue_pairs dictionary
                        #
                        cmd_tstamp_keyvalue_pairs[text_line] = time_stamp


            elif scan_state == u"LOOK4COMMAND":
                heredoc_found = re.search(heredoc_re, text_line)
                time_stamp_found = re.search(time_stamp_re, text_line)
                if heredoc_found:
                    scan_state = u"LOOK4HEREDOCEND"
                    heredoc_end = heredoc_found.group(1)
                    heredoc_end_re = re.compile('\A' + heredoc_found.group(1) + '\Z')
                    heredoc_list = []
                    heredoc_timestamp = time_stamp
                    heredoc_list.append(text_line)
                elif time_stamp_found:
                    scan_state = u"LOOK4COMMAND"
                    #
                    # update to the newer time_stamp
                    #
                    prior_time_stamp = time_stamp
                    time_stamp = time_stamp_found.group(1)
                    errmsg = u"{0}\n*** Out Of Place TimeStamp Found [ {1} ]  ***\n"
                    print errmsg.format(error_locator, text_line)
                else:
                    scan_state = u"LOOK4TIMESTAMP"
                    #
                    # Not a timestamp
                    # Not a Heredoc
                    # Not Blank
                    # Must be command
                    #
                    #
                    # THIS SHOULD BE THE ROAD MOST TRAVELED
                    # usually looking for a command finds a command (I hope)
                    #
                    if text_line in cmd_tstamp_keyvalue_pairs:
                        if cmd_tstamp_keyvalue_pairs[text_line] < time_stamp:
                            #
                            # It is not a time_stamp and
                            # up top (#51FE142E) I filter out all blank
                            # lines, so it should be safe to
                            # treat it like a command.
                            #
                            cmd_tstamp_keyvalue_pairs[text_line] = time_stamp
                    else:
                        #
                        # This is the first time we've seen this command line
                        # put a new entry in the keyvalue_pairs dictionary
                        #
                        cmd_tstamp_keyvalue_pairs[text_line] = time_stamp

            elif scan_state == u"LOOK4HEREDOCEND":
                heredoc_end_found = re.search(heredoc_end_re, text_line)
                time_stamp_found = re.search(time_stamp_re, text_line)
                if heredoc_end_found:
                    scan_state = u"LOOK4TIMESTAMP"
                    #
                    # found the end of the heredoc so 
                    # now ok to look for a timestamp
                    #
                    heredoc_list.append(text_line)
                    heredoc_list.append(nullstr)
                    heredoc_end = default_heredoc_end
                    #
                    # Join all heredoc commands together in a 
                    # single string with commands separated by
                    # ascii(1) characters
                    #
                    text_line2save = ctrlA.join(heredoc_list)
                    #
                    # Associate the entire heredoc with a single timestamp
                    #
                    cmd_tstamp_keyvalue_pairs[text_line2save] = heredoc_timestamp
                    #
                    # Clear the heredoc_list for good house keeping
                    #
                    heredoc_list = []
                elif time_stamp_found:
                    scan_state = u"LOOK4COMMAND"
                    #
                    # this catches unterminated heredocs
                    # each item in heredoc_list must become
                    # a separate entry in cmd_tstamp_keyvalue_pairs
                    #
                    heredoc_list[0] = '# '+ heredoc_list[0] + " # UNTERMINATED ***"
                    for text_line in heredoc_list:
                        if text_line in cmd_tstamp_keyvalue_pairs:
                            #
                            # command line is already in dictionary
                            # I want the newest one so it
                            # sorts closer to the end
                            #
                            if cmd_tstamp_keyvalue_pairs[text_line] < heredoc_timestamp:
                                cmd_tstamp_keyvalue_pairs[text_line] = heredoc_timestamp
                        else:
                            #
                            # This is the first time we've seen this command line
                            # put a new entry in the keyvalue_pairs dictionary
                            #
                            cmd_tstamp_keyvalue_pairs[text_line] = heredoc_timestamp
                    heredoc_list = []
                    time_stamp = time_stamp_found.group(1)
                    errmsg = u"{0}\n*** UNTERMINATED HEREDOC DETECTED  ***\n"
                    print errmsg.format(error_locator)
                else:
                    scan_state = u"LOOK4HEREDOCEND"
                    heredoc_list.append(text_line)

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

    unique_command_list = []
    cmdcount = len(list(cmd_tstamp_keyvalue_pairs.keys()))
    print "command count is " + str(cmdcount)
    for command_line in cmd_tstamp_keyvalue_pairs:
        time_stamp = unicode(cmd_tstamp_keyvalue_pairs[command_line])
        unique_command_list.append( u"#"        +
                                    time_stamp  + 
                                    ctrlA       +
                                    command_line)

    for info2write in sorted(unique_command_list):
        list2write = info2write.split(ctrlA)
        for text_line in list2write:
            fH.write(u"%s\n" % text_line)

    fH.close()


if __name__ == u'__main__':
    if not (re.search(u'\A utf [-] 8 \Z', sys.stdout.encoding, re.IGNORECASE | re.VERBOSE)):
        print >>sys.stderr, u"please set python env PYTHONIOENCODING=UTF-8."
        exit(1)
    main(sys.argv[1:], {u'main_caller': os.path.basename(__file__)})

