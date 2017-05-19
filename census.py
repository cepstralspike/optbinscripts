#!/system/xbin/env python3
# {{{
# Added changes necessary to make a full device manifest run to completion
# on a Samsung SM-P607T lt03ltetmo with python-3.4.2
# }}}
# {{{
# 20151125.224423.4390855 Added changes to compensate for failed
# surrogateescape conversion of filenames in the recycle bin.
# since it is possible to have bogus filenames that are outside
# the utf-8 codepoint set I changed the codepoint set to utf-16.
# that was not sufficient to fix the problem. So I changed from
# surrogateescape conversion to xmlcharrefreplace. That did the
# trick. On the way I added some exception handlers (try/except)
# blocks. I also added remote debug stuff
#
#    pycharmRemoteDebugPath =`'C:\\bin\\PyCharmPro\\debug-eggs\\pycharm-debug-py3k'
#    if os.path.exists(pycharmRemoteDebugPath):
#        if False:
#            sys.path.append(pycharmRemoteDebugPath)
#            import pydevd
#            pydevd.settrace('localhost', port=5656, stdoutToServer=True, stderrToServer=True)
# it seems to work splendidly.
#
# Also fixed skiplist handling and added :
#        for url2skip in skiplist:
#            if re.match(url2skip, urlPath, re.IGNORECASE):
#                osList = skiplist[url2skip]
#                if platformType in osList:
#                    raise SkipThisDirectory
#
# Also added writeObituary function and
#   class SkipThisDirectory
#   class testException
#
#
# 20151127.233840.9536542
# Clear out code inspection Items
#
#
# }}}
# {{{
# Recursively descend the current directory. Use minimum memory resources. 
# Do a merge sort on the resulting output using the full path name as the 
# sort key.
# {{{
# 20151201.181122.8576819
# 20151201.192009.2997008
# 20151208.185909.3024239
# 
# }}}
# {{{ imports
import sys
import time
import re
import os
import stat
import urllib.request
import errno
import datetime
import shutil
import socket
import json
import subprocess
import platform
import inspect
import importlib
import importlib.util
import bz2

# }}}
# {{{
# Reading a 128meg chunk into memory all at once might be ambitious
# but it is not outrageous. Very few systems have less than 2G these
# days so that is 5% of a the memory on a small system I hope android
# does not choke
# }}}
compressionBlockSize = 0X7ffffff
# {{{ `itemsPerCarton` is the number of lines in each merge file.
# The number of cartons will be the total number of directory
# elements divided by the number `itemsPerCarton`.
# The memory consumed by the script in each partial sort
# increases as `itemsPerCarton` is increased.
# The memory consumed by the script in the final merge
# increases as `itemsPerCarton` is decreased, but since
# the merge is generaly less memory intensive, memory
# is not generally the limiting factor for a merge. OTOH 
# if `itemsPerCarton` were set to 1, then the merge memory-usage 
# would essentially be the same as if `itemsPerCarton` were 
# greater than the total number of items to be sorted. 
# See `Art of Computer Programming, Volume 3: Sorting 
# and Searching` ISBN-13: 978-0201896855
itemsPerCarton = 8191
# }}}
# {{{ `topNode`
# start directory descend here
#
topNode = ''
# topNode = os.getcwd()
# }}}
# {{{ `encodeFix`
# default error handler for encoding exceptions
# surrogateescape not reliable enough
encodeFix = 'xmlcharrefreplace'  # PEP 383 [ http://j.mp/1OwrztW ]
# }}}
# {{{ `fsEncoding`
# default file system encoding for this system
#
fsEncoding = ''
# }}}
# {{{ `pantry` is a dictionary whose
# keys are the names of all the 
# merge files
#
pantry = { }
# }}}
# {{{ `carton` is an array which contains the actual
# directory listing data for each merge file
#
carton = [ ]
# }}}
# {{{ `cartonIdx` contains the fullpath names of all the
# carton files as `keys` and the number of entries 
# in each carton as `values`.
#
cartonIdx = { }
# }}}
# {{{ `dfsIndex` is a unique base-56 encoded integer
# associated with each unique directory element
# that makes possible, putting directory entries 
# back in (their original pre-sorted) order.
#
dfsIndex = -1
# }}}
# {{{ `nullstr` syntactic sugar for ``
#
nullstr = ''
# }}}
# {{{ `distinctHostName` not `localhost` ( I Hope )
#
distinctHostName = None
# }}}
# {{{ `fLog` global file handle for log output`
#
fLog = None
# }}}
# {{{ `fRaw` global file handle for raw toc output`
#
fRaw = None
# }}}
# {{{ `fSrt` global file handle for sorted toc output`
#
fSrt = None
# }}}
# {{{ `space` syntactic sugar for ` `
#
space = str( chr( 32 ) )
# }}}
# {{{ `Tab` syntactic sugar for tab
#
tabChr = str( chr( 9 ) )
# }}}
# {{{ `ctrlA` syntactic sugar for control-a
#
ctrlA = str( chr( 1 ) )
# }}}
# {{{ Number Base Alphabets
# I use base 56 for Inode Numbers on NTFS
# because the inodes can get pretty huge
# I only track INodes so I can track hard 
# links on my disk
#
B56 = "0123456789ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
#
# I use 3 hex digits to number my carton 
# files ( most people call them buckets 
# but in my mind the bucket does not belong
# in a pantry whereas a carton just might)
#
B16 = "0123456789ABCDEF"
#
# finally I use simple base 10 for nix inodes
# but since I select these encodings via 
# the iNodeBase dictionary, the inline logic is
# same for android and windows
#
B10 = "0123456789"
# }}}
# {{{ `platformType` in linux,android,win32 ( I Hope )
#
platformType = 'android'
# }}}
# {{{ `elementTagHash` 
# an element is either a...
# `F`ile
# `D`irectory
# `L`ink
# `U`nknown
#
elementTagHash = {
    0b000: 'U',
    0b001: 'F',
    0b010: 'D',
    0b011: 'D',
    0b100: 'LU',
    0b101: 'LF',
    0b110: 'LD',
    0b111: 'LD'
}  # }}}
# {{{ regular expressions 

#
# documentation claims this is 
# unnecessary. As of 20140325
# python installed on host fultonJSheen
# does not treat <tab> <newline> <cr>
# as whitespace 
#
WS = ' \t\n\r'

leadingDrive = re.compile( r"""
    \A
    ( [a-z] )
    :
    [/\\]+
    """.strip( WS ), re.VERBOSE | re.IGNORECASE )

leadingSlash = re.compile( r"""
    \A
    [/\\]+
    """.strip( WS ), re.VERBOSE | re.IGNORECASE )

trailingSlash = re.compile( r"""
    [/\\]+
    \Z
    """.strip( WS ), re.VERBOSE | re.IGNORECASE )

anySlashes = re.compile( r"""
    [/\\]+
    """.strip( WS ), re.VERBOSE | re.IGNORECASE )

anyPeriods = re.compile( r"""
    [.]+
    """.strip( WS ), re.VERBOSE | re.IGNORECASE )

allDigits = re.compile( r"""
    \A
    \d+
    \Z
    """.strip( WS ), re.VERBOSE | re.IGNORECASE )

platformID = {
    'Linux-3.16.0-4-amd64-x86_64-with-debian-8.7'                            : 'linux',
    'Linux-3.16.0-4-amd64-x86_64-with-debian-8.5'                            : 'linux',
    'Linux-3.16.0-4-686-pae-i686-with-debian-8.5'                            : 'linux',
    'Linux-3.4.0-14.10-cm-qs600-3.2-g68558b0-armv7l-with-Linaro-14.04-trusty': 'linux',
    'Linux-3.5.0-54-generic-x86_64-with-Ubuntu-12.04-precise'                : 'linux',
    'Linux-3.4.0-453951-armv7l-with'                                         : 'android',
    'Linux-3.4.0-1433887-armv7l-with'                                        : 'android',
    'Windows-7-6.1.7601-SP1'                                                 : 'win32',
    'Windows-10.0.10586'                                                     : 'win32',
}

EXTERNAL_STORAGE = os.getenv( 'EXTERNAL_STORAGE' )
if not EXTERNAL_STORAGE:
    EXTERNAL_STORAGE = nullstr

SECONDARY_STORAGE = os.getenv( 'SECONDARY_STORAGE' )
if not SECONDARY_STORAGE:
    SECONDARY_STORAGE = nullstr

skiplist = {
    '/proc'               : [ 'linux', 'android' ],
    '///C:/%24recycle.bin': [ 'win32' ],
    '/sys/devices'        : [ 'linux', 'android' ],
    '/dev'                : [ 'linux', 'android' ],
    '/sys/dev'            : [ 'linux', 'android' ],
}

failSafeDirDict = {
    'linux'  : os.path.expanduser( '~' ),
    'android': EXTERNAL_STORAGE.split( ':' )[ 0 ],
    'win32'  : os.getenv( 'TEMP' ),
}

scratchDirDict = {
    'linux'  : os.path.expanduser( '~' ) + '/00/log/tox',
    'android': EXTERNAL_STORAGE.split( ':' )[ 0 ] + '/00/log/tox',
    'win32'  : 'C:/etc/tox',
}

localDirDict = {
    'linux'  : os.path.expanduser( '~' ) + '/00/log/tox',
    'android': SECONDARY_STORAGE.split( ':' )[ 0 ] + '/00/log/tox',
    'win32'  : 'C:/etc/tox',
}

drpBxDirDict = {
    'linux'  : os.path.expanduser( '~' ) + '/Dropbox/tox',
    'android': '/mnt/sdcard/00/log/tox',
    'win32'  : 'C:/drpbx/Dropbox/tox',
}

topNodeDict = {
    'linux'  : '/',
    'android': '/',
    'win32'  : 'C:/',
}

iNodeFldWdth = {
    'linux'  : 10,
    'android': 10,
    'win32'  : 12,
}

iNodeBase = {
    'linux'  : B10,
    'android': B10,
    'win32'  : B56,
}

fsEncodeDict = {
    'linux'  : sys.getfilesystemencoding( ),
    'android': sys.getfilesystemencoding( ),
    'win32'  : 'utf-16',
}

# }}}

class CannotCreateDirectory( Exception ):  # {{{
    pass


# }}}
class SkipThisDirectory( Exception ):  # {{{
    pass


# }}}
class testException( Exception ):  # {{{
    pass


# }}}

class InputMergeObj( object ):  # {{{
    __slots__ = [
        '__currentLine',
        '__errMsg',
        '__exc00',
        '__fullPath',
        '__H',
        '__metaData',
        '__outData',
        '__N',
        '__lineKey',
    ]

    def __init__( self, file_name: str ):
        self.__N = file_name
        self.__lineKey = ctrlA
        try:
            self.__outData = None
            self.__fullPath = None
            self.__metaData = None
            #
            # at object instantiation read the first
            # line in the text file and extract the
            # sort key ( full path name )
            #
            self.__H = open( file_name, 'rt', encoding=fsEncoding )
            self.__currentLine = self.__H.readline( )
            if self.__currentLine:
                self.__lineKey = self.__currentLine.split( ctrlA )[ -1 ]
        except (FileNotFoundError, OSError) as __exc00:
            __errMsg = "** <openInFile> == "
            __errMsg += file_name
            __errMsg += " cannot read this file **\n\n"
            __errMsg += str( __exc00 )
            writeObituary( inspect.currentframe( ), __errMsg )
            sys.exit( "open the pod bay doors hal" )

    def nxtLine( self ):
        self.__lineKey = ctrlA  # default the key to assume EOF
        if self.__currentLine:
            #
            # the current line is not empty
            # so the end of file has not been
            # reached
            #
            self.__currentLine = self.__H.readline( )
            if self.__currentLine:
                self.__lineKey = self.__currentLine.split( ctrlA )[ -1 ]
            else:
                self.__H.close( )

        return self.__lineKey

    def cleanCurrentLine( self ):
        #
        # clean line contains no ctrlA characters
        # all fields are space separated except the
        # last field which is separated with a tab
        # character
        #
        self.__outData = self.__currentLine.split( ctrlA )
        self.__fullPath = self.__outData.pop( )
        self.__metaData = space.join( self.__outData )
        return tabChr.join( [ self.__metaData, self.__fullPath ] )

    @property
    def N( self ):
        return self.__N

    @property
    def lineKey( self ):
        return self.__lineKey


# }}}
class FsysElement:  # {{{
    def __init__( self ):
        self.Size = 0
        self.MTime = time.gmtime( 0 )
        self.TagKey = 0
        self.Inode = 0
        self.Tag = ' U'
        self.LinkPtr = nullstr
        self.dfsIndex = str( int_encode( dfsIndex, B56 ) ).zfill( 4 )


# }}}
def microSecTS( ):  # {{{
    return datetime.datetime.now( ).strftime( 'T%Y%m%d.%H%M%S.%f' + space )


# }}}
def createStamp( ):  # {{{
    return time.strftime( '.%Y%m%d.%H%M%S.', time.localtime( ) )


# }}}
def mkdir_p( path ):  # {{{
    #
    # I clipped this from somewhere.
    # it seems to work. But I dont
    # remember where I got it.
    #
    try:
        os.makedirs( path )
    except OSError as exc00:  # Python >2.5
        if exc00.errno == errno.EEXIST and os.path.isdir( path ):
            pass
        else:
            raise CannotCreateDirectory


# }}}
def int_encode( num, alphabet=B56 ):  # {{{
    #
    # Encode a number in Base X
    #
    #     `num`: The number to encode
    #     `alphabet`: The alphabet to use for encoding
    #
    if num == 0:
        return alphabet[ 0 ]
    arr = [ ]
    base = len( alphabet )
    while num:
        rem = num % base
        num //= base
        arr.append( alphabet[ rem ] )
    arr.reverse( )
    return nullstr.join( arr )


# }}}
def getNetHostName4Android( ):  # {{{
    #
    # Getprop returns a name like:
    #
    # `android-1f6e8ad67260efb1`
    #	or
    # `kindle-91cf73cdf`
    #   or
    # `` ( for python on gs4 android 4.2.2 )
    #
    # I call this a hostile host name
    #
    byteRslt = None
    errMesg = None
    errCode = None
    droidNetHostName = 'localhost'
    try:
        byteRslt = subprocess.check_output( [ 'getprop', 'net.hostname' ] )
    except subprocess.CalledProcessError as exc01:
        errMesg = exc01.output  # Output generated before error
        errCode = exc01.returncode  # Return error code

    if errCode:
        print( '(**' + errMesg + '**)' )
    else:
        if not byteRslt:
            pass
        elif byteRslt.rstrip( ).lstrip( ):
            droidNetHostName = byteRslt.decode( fsEncoding ).rstrip( ).lstrip( )
        else:
            pass

    return droidNetHostName


# }}}
def getFriendlyHostName4Android( ):  # {{{
    #
    # getFriendlyHostName4Android
    # returns a name like:
    #
    # `myDogFido`
    #	or
    # `myCatFluffy`
    #
    # I call this a friendly host name
    #
    hostileDroidHostName = getNetHostName4Android( )
    retVal = hostileDroidHostName
    hostNameJsonFile = '/sdcard/etc/androidHosts.json'
    # pdb.set_trace()
    hostNameMap = { }
    if os.path.isfile( hostNameJsonFile ):
        if os.access( hostNameJsonFile, os.R_OK ):
            try:
                fH = open( hostNameJsonFile, 'rt', encoding=fsEncoding )
                hostNameMap = json.load( fH )
            except FileNotFoundError:
                pass

    if hostileDroidHostName in hostNameMap:
        retVal = hostNameMap[ hostileDroidHostName ]

    return retVal


# }}}
def establishDestinationDir( dirHash ):  # {{{
    # {{{ dst Directory Logic
    directoryPath = dirHash[ platformType ]

    if os.path.exists( directoryPath ):
        alternatePath = directoryPath
        altCount = 0
        while os.path.isfile( alternatePath ):
            #
            # prefered directoryPath exists as a file
            #
            alternatePath = directoryPath + "." + str( altCount )
            altCount += 1
        if altCount:
            #
            # Create alternate dst directory
            #
            directoryPath = alternatePath
            try:
                mkdir_p( directoryPath )
            except CannotCreateDirectory:
                directoryPath = failSafeDirDict[ platformType ]
    else:
        try:
            mkdir_p( directoryPath )
        except CannotCreateDirectory:
            directoryPath = failSafeDirDict[ platformType ]

    if not os.path.isdir( directoryPath ):
        errMsg000 = "<directoryPath> == "
        errMsg000 += directoryPath
        errMsg000 += " must be a directory"
        sys.exit( errMsg000 )
    else:
        if not os.access( directoryPath, os.W_OK ):
            errMsg000 = "<directoryPath> == "
            errMsg000 += directoryPath
            errMsg000 += " must be a writable directory"
            sys.exit( errMsg000 )

    # }}}
    return directoryPath


# }}}
def openOutFileBinMode( fN ):  # {{{
    try:
        handle = open( fN, 'wb' )
    except OSError as exc_openwt_fail00:
        errMsg010 = "** <openOutFileBinMode> == "
        errMsg010 += fN
        errMsg010 += " cannot write to this file **\n\n"
        errMsg010 += str( exc_openwt_fail00 )
        writeObituary( inspect.currentframe( ), errMsg010 )
        sys.exit( "open the pod bay doors hal" )

    return handle


# }}}
def openInFileBinMode( fN ):  # {{{
    try:
        handle = open( fN, 'rb' )
    except FileNotFoundError as exc_openrd_fail:
        errMsg020 = "** <openInFileBinMode> == "
        errMsg020 += fN
        errMsg020 += " cannot read this file **\n\n"
        errMsg020 += str( exc_openrd_fail )
        writeObituary( inspect.currentframe( ), errMsg020 )
        sys.exit( "open the pod bay doors hal" )

    return handle


# }}}
def openOutFile( fN ):  # {{{
    try:
        handle = open( fN, 'wt', encoding=fsEncoding )
    except OSError as exc_openwt_fail00:
        errMsg010 = "** <openOutFile> == "
        errMsg010 += fN
        errMsg010 += " cannot write to this file **\n\n"
        errMsg010 += str( exc_openwt_fail00 )
        writeObituary( inspect.currentframe( ), errMsg010 )
        sys.exit( "open the pod bay doors hal" )

    return handle


# }}}
def openInFile( fN ):  # {{{
    try:
        handle = open( fN, 'rt', encoding=fsEncoding )
    except FileNotFoundError as exc_openrd_fail:
        errMsg020 = "** <openInFile> == "
        errMsg020 += fN
        errMsg020 += " cannot read this file **\n\n"
        errMsg020 += str( exc_openrd_fail )
        writeObituary( inspect.currentframe( ), errMsg020 )
        sys.exit( "open the pod bay doors hal" )

    return handle


# }}}
def nextOutFile( nameType, stamp ):  # {{{
    suffix = ".txt"
    stringMatches = allDigits.match( nameType )
    if stringMatches:
        #
        # A name type of all digits
        # is a temporary carton file.
        #
        # Cartons fill a pantry.
        #
        # All the cartons in the pantry
        # eventually get placed into a
        # single crate (a srt.txt file).
        #
        nameType = int_encode( int( nameType ), B16 )
        nameType = str( nameType ).zfill( 3 )
        outFName = establishDestinationDir( scratchDirDict )
        suffix = ".tmp"
    else:
        outFName = establishDestinationDir( localDirDict )

    outFName += "/"

    baseName = topNode
    baseName = leadingDrive.sub( "\\1.slash.", baseName )
    baseName = leadingSlash.sub( "slash.", baseName )
    baseName = trailingSlash.sub( nullstr, baseName )
    baseName = anySlashes.sub( ".", baseName )
    baseName = distinctHostName + '.' + baseName

    if "ezn" == nameType:
        baseName += ".toc."
    else:
        baseName += stamp

    baseName += nameType
    baseName += suffix
    baseName = anySlashes.sub( ".", baseName )
    baseName = anyPeriods.sub( ".", baseName )

    outFName += baseName
    outFName = anyPeriods.sub( ".", outFName )
    outFName = anySlashes.sub( "/", outFName )

    if ".tmp" == suffix:
        pantry[ outFName ] = 0  # initialize pantry size

    outFHandle = openOutFile( outFName )

    return { "outFHandle": outFHandle, "outFName": outFName, "baseName": baseName }


# }}}

def writeObituary( stackFrame, msg=None ):  # {{{
    global fLog
    global dfsIndex
    if msg:
        errMsg030 = msg
    else:
        errMsg030 = ""

    errMsg030 = microSecTS( ) + \
                str( int_encode( dfsIndex, B56 ) ).zfill( 4 ) + \
                " <<< [[[Fatal Exception at line " + \
                str( stackFrame.f_lineno ) + \
                " Triggered]]]::" + \
                errMsg030 + \
                ">>>\n"

    fLog.write( errMsg030 )
    fLog.close( )
    sys.exit( errMsg030 )


# }}}

def coerse2str( dataIn ):  # {{{
    #
    # As of python version 3.1: On some systems, conversion using the file system encoding may fail.
    # To compensate, Python uses the surrogateescape encoding error handler, which means that undecodable
    # bytes are replaced by a Unicode character U+DCxx on decoding.
    #
    # This program only generates a manifest of files. So the filname encoding in the
    # manifest need not be the same as the file name encoding on the physical medium
    #
    if isinstance( dataIn, bytes ):
        try:
            retVal = dataIn.decode( fsEncoding, errors=encodeFix )
        except UnicodeError as exc_unicode_00:
            writeObituary( inspect.currentframe( ), str( exc_unicode_00 ) )
            sys.exit( "open the pod bay doors hal" )

    elif isinstance( dataIn, str ):
        try:
            dataInBytes = dataIn.encode( fsEncoding, errors=encodeFix )
            retVal = dataInBytes.decode( fsEncoding, errors=encodeFix )
            if False:
                if not (2 + dfsIndex) % 1111:
                    raise testException
        except UnicodeError as exc_unicode_01:
            writeObituary( inspect.currentframe( ), str( exc_unicode_01 ) )
            sys.exit( "open the pod bay doors hal" )
    else:
        errMsg040 = "** <coerse2str> dataIn == "
        errMsg040 += dataIn
        errMsg040 += " 'dataIn' must be bytes or str **"
        writeObituary( inspect.currentframe( ), errMsg040 )
        sys.exit( "open the pod bay doors hal" )

    return retVal  # Instance of str


# }}}
def int_decode( string, alphabet=B56 ):  # {{{
    #
    # Decode a Base X encoded string into the number
    #
    #    Arguments:
    #    - `string`: The encoded string
    #    - `alphabet`: The alphabet to use for encoding
    #
    base = len( alphabet )
    strlen = len( string )
    num = 0

    idx00 = 0
    for char in string:
        power = (strlen - (idx00 + 1))
        num += alphabet.index( char ) * (base ** power)
        idx00 += 1

    return num


# }}}
def WriteFsysElementInfo( path, fH, fN ):  # {{{
    #
    # send a line to a text file
    #
    element = carton[ cartonIdx[ path ] ]
    iNodeEnc = iNodeBase[ platformType ]
    iNodeStr = int_encode( element.Inode, iNodeEnc )
    msg = str( element.Tag ).rjust( 2 )
    msg += ctrlA
    msg += element.dfsIndex
    msg += ctrlA
    msg += time.strftime( '%Y%m%d.%H%M%S', element.MTime )
    msg += ctrlA
    msg += str( iNodeStr ).zfill( iNodeFldWdth[ platformType ] )
    msg += ctrlA
    msg += str( element.Size ).zfill( 12 )
    msg += ctrlA
    msg += path
    msg += element.LinkPtr
    msg += "\n"
    try:
        msg2write = coerse2str( msg )
    except UnicodeError as exc_unicode_02:
        errMsg050 = ": msg2write = coerse2str(msg)"
        errMsg050 += " failed for file "
        errMsg050 += fN
        errMsg050 += "\n\n"
        errMsg050 += str( exc_unicode_02 )
        writeObituary( inspect.currentframe( ), errMsg050 )
        sys.exit( "open the pod bay doors hal" )

    fH.write( msg2write )


# }}}
def squeeze( ifN, ofN ):  # {{{
    '''Compress *ifN* into *ofN* using bz2 compression'''

    bz2vise = bz2.BZ2Compressor( 9 )
    ifH = openInFileBinMode( ifN )
    ofH = openOutFileBinMode( ofN )
    while True:
        chunk = ifH.read( compressionBlockSize )
        if not chunk:
            break
        chunk = bz2vise.compress( chunk )
        if chunk:
            ofH.write( chunk )
    chunk = bz2vise.flush( )
    if chunk:
        ofH.write( chunk )
    ifH.close( )
    ofH.close( )


# }}}
# {{{ Main descent Loop Initialization
def main( sysArgv: list, kwargs=None ):
    global dfsIndex
    global platformType
    global distinctHostName
    global topNode
    global fLog
    global fRaw
    global fSrt
    global fsEncoding
    platformKey = platform.platform( )
    if platformKey not in platformID:
        err_msg = "[BAILINGOUT]::** platformKey == " + platformKey + " is not supported **"
        sys.exit( err_msg )

    platformType = platformID[ platformKey ]
    fsEncoding = fsEncodeDict[ platformType ] 
    if 'win32' == platformType:
        #
        # Belts & Suspenders here. 'pycharmRemoteDebugPath' is only
        # needed if 'pydevd' is not somewhere on the 'PYTHONPATH'
        #
        pydevd_spec = importlib.util.find_spec( 'pydevd' )
        pydevd_is_available = pydevd_spec is not None
        pycharmRemoteDebugPath = 'C:\\bin\\PyCharmPro\\debug-eggs\\pycharm-debug-py3k'
        if os.path.exists( pycharmRemoteDebugPath ):
            if not pydevd_is_available:
                sys.path.append( pycharmRemoteDebugPath )
                pydevd_spec = importlib.util.find_spec( 'pydevd' )
                pydevd_is_available = pydevd_spec is not None

        if pydevd_is_available:
            import pydevd
            ok2request_trace = os.path.exists( __file__ + ".debug_this" )
            if ok2request_trace:
                pydevd.settrace( 'localhost', port=5656, stdoutToServer=True, stderrToServer=True )

                # SSyncDiffHere SyncDiffHere SyncDiffHere SyncDiffHere SyncDiffHere SyncDiffHere yncDiffHere
    cartonNumber = 0
    uniqIdStamp = createStamp( )
    drpBxPath = establishDestinationDir( drpBxDirDict )

    distinctHostName = socket.gethostname( )
    if 'localhost' == distinctHostName:
        if 'android' == platformType:
            distinctHostName = getFriendlyHostName4Android( )

    if 'main_caller' in kwargs:
        try:
            if os.path.basename( __file__ ) == kwargs[ 'main_caller' ]:
                os.chdir( topNodeDict[ platformType ] )
                topNode = os.getcwd( )
            elif 'ezdfstree.py' == kwargs[ 'main_caller' ]:
                topNode = os.getcwd( )
            elif 'dbxdfstree.py' == kwargs[ 'main_caller' ]:
                os.chdir( drpBxDirDict[ platformType ] )
                os.chdir( ".." )
                topNode = os.getcwd( )
        except OSError as exc_chdir_fail_00:
            errMsg055 = str( exc_chdir_fail_00 )
            sys.exit( errMsg055 )

    if '' == topNode:
        errMsg060 = "** <topDirectory> == [ "
        errMsg060 += sysArgv[ 0 ]
        errMsg060 += " ] cannot cd to this directory **"
        if os.path.isdir( sysArgv[ 0 ] ):
            try:
                os.chdir( sysArgv[ 0 ] )
                topNode = os.getcwd( )
            except OSError as exc_chdir_fail_01:
                errMsg060 += "\n\n"
                errMsg060 += str( exc_chdir_fail_01 )
                sys.exit( errMsg060 )
        else:
            errMsg060 = "** os.path.isdir("
            errMsg060 += sysArgv[ 0 ]
            errMsg060 += ") is False. cannot cd to this directory **"
            sys.exit( errMsg060 )

    #
    # error log file is a special carton
    #
    rslt = nextOutFile( "log", uniqIdStamp )
    dstLogFName = rslt[ "outFName" ]
    fLog = rslt[ "outFHandle" ]
    #
    # error log file is a special carton
    #
    rslt = nextOutFile( "raw", uniqIdStamp )
    dstRawFName = rslt[ "outFName" ]
    fRaw = rslt[ "outFHandle" ]

    dirStack = [ ]
    dirStack.insert( 0, topNode )
    # }}}
    while len( dirStack ):  # {{{ Main Outer Loop
        thisDir = dirStack.pop( )
        thisDirCanonical = coerse2str( thisDir )
        urlPath = urllib.request.pathname2url( thisDirCanonical )
        try:  # {{{
            for url2skip in skiplist:
                if re.match( url2skip, urlPath, re.IGNORECASE ):
                    osList = skiplist[ url2skip ]
                    if platformType in osList:
                        raise SkipThisDirectory

            try:  # {{{
                dirListing = os.listdir( thisDir )
            # }}}
            except OSError as exc02:  # {{{
                fLog.write( microSecTS( ) +
                            str( int_encode( dfsIndex, B56 ) ).zfill( 4 ) +
                            " <<< [[[Exception 0 Triggered]]]::" +
                            thisDir + str( exc02 ) +
                            ">>>\n" )

                dirListing = [ ]
            # }}}

            while len( dirListing ):  # {{{ Main inner Loop
                eName = dirListing.pop( )
                dfsIndex += 1
                if False:
                    if not (2 + dfsIndex) % 1111:
                        print( dfsIndex )
                fullPath = os.path.join( thisDir, eName )
                e = FsysElement( )

                try:  # {{{
                    e.TagKey = 0
                    e.TagKey |= os.path.isfile( fullPath )
                    e.TagKey |= os.path.isdir( fullPath ) << 1
                    e.TagKey |= os.path.islink( fullPath ) << 2

                    e.Tag = elementTagHash[ e.TagKey ]
                    e.Inode = abs( os.stat( fullPath ).st_ino )
                    if 'L' == e.Tag[ 0 ]:
                        e.LinkPtr = ' -> ' + os.readlink( fullPath )

                    e.MTime = time.localtime( os.path.getmtime( fullPath ) )
                    e.Size = os.lstat( fullPath )[ stat.ST_SIZE ]
                # }}}
                except OSError as exc03:  # {{{ Exception Triggered
                    fLog.write( microSecTS( ) +
                                str( int_encode( dfsIndex, B56 ) ).zfill( 4 ) +
                                " <<< [[[Exception 1 Triggered]]]::" +
                                fullPath + str( exc03 ) +
                                ">>>\n" )
                # }}}

                cartonIdx[ fullPath ] = len( carton )
                carton.append( e )
                try:  # {{{
                    WriteFsysElementInfo( fullPath, fRaw, dstRawFName )
                # }}}
                except Exception as exc04:  # {{{
                    writeObituary( inspect.currentframe( ), msg=str( exc04 ) )
                    sys.exit( "open the pod bay doors hal" )
                # }}}
                if 'D' == e.Tag:
                    dirStack.insert( 0, fullPath )

                if itemsPerCarton == len( carton ):  # {{{
                    #
                    # The carton is full. Dump it to a file
                    #
                    rslt = nextOutFile( str( cartonNumber ), uniqIdStamp )
                    dstFName = rslt[ "outFName" ]
                    fOut = rslt[ "outFHandle" ]
                    fLog.write( microSecTS( ) + '> ' + dstFName + "\n" )
                    #
                    # pantry dictionary contains the full path names
                    # of all the carton files as indexes.
                    # associated with each carton file is a linecount
                    #
                    pantry[ dstFName ] = len( carton )
                    for fullPath in sorted( cartonIdx.keys( ) ):  # {{{
                        WriteFsysElementInfo( fullPath, fOut, dstFName )
                    # }}}
                    fOut.close( )
                    #
                    # I only keep the `active` carton in memory.
                    # So, clear out the old. Make room for the new.
                    # This python slice semantics will take me
                    # some getting-used-to.
                    #
                    carton[ : ] = [ ]
                    #
                    # Carton has been cleared so must also
                    # be the carton index.
                    #
                    cartonIdx.clear( )
                    cartonNumber += 1
                    # }}}
                    # }}}
        # }}}
        except SkipThisDirectory:  # {{{
            pass
            # }}}
    # }}}

    # {{{ Main descent Loop Cleanup
    if len( carton ):  # {{{
        #
        # usually a partially filled carton
        # will be left over. So, manage that condition.
        #
        rslt = nextOutFile( str( cartonNumber ), uniqIdStamp )
        dstFName = rslt[ "outFName" ]
        fOut = rslt[ "outFHandle" ]
        fLog.write( microSecTS( ) + '> ' + dstFName + "\n" )
        pantry[ dstFName ] = len( carton )
        for fullPath in sorted( cartonIdx.keys( ) ):  # {{{
            WriteFsysElementInfo( fullPath, fOut, dstFName )
        # }}}
        fOut.close( )  # }}}
    # recursive descent is complete
    # now I need to merge all of my
    # cartons into a single crate
    # which will be sorted by fullpathname
    #
    fRaw.close( )
    # }}}
    # {{{ Initialize the merge operation
    #
    # put the names of all
    # merge files in the mergeQ
    #
    mergeQ = [ ]
    tmpFileList = list( pantry.keys( ) )
    for fName in tmpFileList:
        #
        # open temp file for reading
        #
        bucket = InputMergeObj( fName )
        #
        # put the handle, FileName pair in the queue
        #
        mergeQ.append( bucket )

    rslt = nextOutFile( "srt", uniqIdStamp )
    dstSrtFName = rslt[ "outFName" ]
    fSrt = rslt[ "outFHandle" ]

    therezWork2do = True
    # }}}
    while therezWork2do:  # {{{ Main Merge Loop
        minIdx = 0
        if 1 < len( mergeQ ):
            for idx in list( range( 1, len( mergeQ ) ) ):
                if mergeQ[ idx ].lineKey < mergeQ[ minIdx ].lineKey:
                    minIdx = idx
            bucket = mergeQ[ minIdx ]
            fSrt.write( bucket.cleanCurrentLine( ) )
            if ctrlA == bucket.nxtLine( ):
                fLog.write( microSecTS( ) + '< ' + mergeQ[ minIdx ].N + "\n" )
                mergeQ.pop( minIdx )
        else:
            therezWork2do = False
    # }}}
    # {{{ Merge Cleanup
    bucket = mergeQ[ 0 ]
    fSrt.write( bucket.cleanCurrentLine( ) )
    while ctrlA != bucket.nxtLine( ):  # {{{
        #
        # write out all the lines that remain
        # in the last bucket
        #
        fSrt.write( bucket.cleanCurrentLine( ) )
        # }}}
    fLog.write( microSecTS( ) + '< ' + mergeQ[ 0 ].N + "\n" )
    mergeQ.pop( 0 )
    fSrt.close( )
    fLog.close( )
    #
    # cleanup the temp files
    #
    tmpFileList = list( pantry.keys( ) )
    for fName in tmpFileList:
        os.remove( fName )

    rslt = nextOutFile( "ezn", uniqIdStamp )
    fEzn = rslt[ "outFHandle" ]
    #
    # the ezn file exists only as a destination name 
    # to which the timestamped output file is copied
    # so close the filehandle that nextOutFile generated 
    #
    fEzn.close( )
    dstEzFName = rslt[ "outFName" ]
    dbxEzFName = drpBxPath + "/" + rslt[ "baseName" ]
    shutil.copy2( dstSrtFName, dstEzFName )
    if not os.path.samefile( establishDestinationDir( localDirDict ), drpBxPath ):
        shutil.copy2( dstEzFName, dbxEzFName )

    resultFiles = (dstRawFName, dstSrtFName, dstLogFName)
    for f in resultFiles:
        squeeze( f, f + ".bz2" )
        print( f + ".bz2" )
        os.remove( f )

    print( dstEzFName )
    if dstEzFName != dbxEzFName:
        print( dbxEzFName )


if __name__ == '__main__':
    if not (re.search( '\A utf [-] 8 \Z', sys.stdout.encoding, re.IGNORECASE | re.VERBOSE )):
        print( "please set python env PYTHONIOENCODING=UTF-8.", file=sys.stderr )
        exit( 1 )
    main( sys.argv[ 1: ], { 'main_caller': os.path.basename( __file__ ) } )
