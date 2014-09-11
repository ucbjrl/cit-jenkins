#!/usr/local/bin/python2.7
# encoding: utf-8
'''
citJenkins.citjenkins -- shortdesc

citJenkins.citjenkins is a description

It defines classes_and_methods

@author:     Jim Lawson

@copyright:  2014 UC Berkeley. All rights reserved.

@license:    license

@contact:    ucbjrl@berkeley.edu
@deffield    updated: Updated
'''

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from argparse import FileType
from datetime import timedelta
import errno
import os
import random
import signal
import string
import sys

from monitorRepos import MonitorRepos
from testRun import testRun

__all__ = []
__version__ = 0.1
__date__ = '2014-07-03'
__updated__ = '2014-07-03'

DEBUG = 1
TESTRUN = 0
PROFILE = 0

class CLIError(Exception):
    '''Generic exception to raise and log different fatal errors.'''
    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = "E: %s" % msg
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg

localRepoNames = [ '/Users/jrl/noArc/clients/ucb/git/ucb-bar/chisel',
                   '/Users/jrl/noArc/clients/ucb/git/ucb-bar/dreamer-tools']

defaultChiselJar = '/Users/jrl/.ivy2/local/edu.berkeley.cs/chisel_2.10/2.3-SNAPSHOT/jars/chisel_2.10.jar'
chiselJar = defaultChiselJar
testDir = "test"
doExit = False
seed = None
badSeedFile = None
continueOnError = False

homeDir = os.getcwd()

def seed_generator(size=8, chars=string.ascii_uppercase + string.digits):
    '''Return the "next" seed. None when done.'''
    def newSeedFromFile(f):
        global seed
        newSeed = f.readline()
        if newSeed == '':
            newSeed = None
            f.close()
            seed = 'No more seeds!'
        else:
            # Trim trailing white space (including newlines)
            newSeed = newSeed.rstrip()
        return newSeed

    # Do we have a global seed?
    global seed
    newSeed = None
    if seed is None:
        newSeed = ''.join(random.choice(chars) for _ in range(size))
    elif type(seed) is str:
        # Does seed look like a file path?
        if seed.find('/') >= 0:
            # It's a file spec. Try to open it for reading.
            # Is it an absolute or a relative path?
            path = ''
            if seed.startswith('/'):
                path = seed
            else:
                path = os.path.join(homeDir, seed)
            f = open(path, 'r')
            if f is None:
                print 'Couldn\'t open %s for reading.' % (seed)
            else:
                seed = f
                newSeed = newSeedFromFile(seed)
        elif seed != 'No more seeds!':
            newSeed = seed
            seed = 'No more seeds!'
    elif type(seed) is file:
        newSeed = newSeedFromFile(seed)
            
    return newSeed

def chisel_jar_path():
    return chiselJar

def testDir_path():
    return testDir

initVariableFUNC = {
    'chisel_jar' : chisel_jar_path,
    'testDir' : testDir_path,
}

testVariableFUNC = {
    'seed' : seed_generator,
}

setupCommands = [
    "touch DELETETHISDIRECTORYWHENDONE",
]

sbtTestCommands = [
    "chisel-torture --seed $(seed)",
    "mv Torture.vcd Torture-gold.vcd",
    "sbt -Dsbt.log.noformat=true \"run --compileInitializationUnoptimized --lineLimitFunctions 8 --vcd --isVCDinline --backend flo\"",
    "vcd2step Torture-gold.vcd Torture.flo test.in",
    "sbt -Dsbt.log.noformat=true \"run --compileInitializationUnoptimized --lineLimitFunctions 8 --vcd --isVCDinline --backend c --genHarness --compile\"",
    "cat test.in | ./Torture",
    "vcddiff Torture-gold.vcd Torture.vcd"
]

testCommands = [
    "chisel-torture --seed $(seed)",
    "mv Torture.vcd Torture-gold.vcd",
    "scalac -classpath $(chisel_jar):. Torture.scala",
    "scala -classpath $(chisel_jar):. Torture  --compileInitializationUnoptimized --lineLimitFunctions 8 --vcd --isVCDinline --backend flo",
    "vcd2step Torture-gold.vcd Torture.flo test.in",
    "scala -classpath $(chisel_jar):. Torture  --compileInitializationUnoptimized --lineLimitFunctions 8 --vcd --isVCDinline --backend c --genHarness --compile",
    "cat test.in | ./Torture",
    "vcddiff Torture-gold.vcd Torture.vcd"
]

def sigterm(signum, frame):
    global doExit
    print 'citjenkins: signal %d' % (signum)
    if signum == signal.SIGTERM:
        doExit = True

def initVariables():
    variables = {}
    # Evaluate all variables so they stay constant for this set of commands.
    for v, f in initVariableFUNC.iteritems():
        newValue = f()
        # If a function returns None, it's out of values.
        # Pass this uplevel. We'll probably want to stop.
        if newValue is None:
            return None
        variables[v] = newValue
    return variables

def updateVariables():
    variables = {}
    # Evaluate all variables so they stay constant for this set of commands.
    for v, f in testVariableFUNC.iteritems():
        newValue = f()
        # If a function returns None, it's out of values.
        # Pass this uplevel. We'll probably want to stop.
        if newValue is None:
            return None
        variables[v] = newValue
    return variables

def locate(test, variables):
    ''' Create the test directory and do any setup required for testing. '''
    try:
        os.mkdir(testDir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            print >>sys.stderr, "os.mkdir(%s) returns %d: %s" % (e.filename, e.errno, e.strerror)
            sys.exit(1)

    os.chdir(testDir)
    test.run(setupCommands, variables)

def runATest(test, variables):
    ''' Run a test sequence of commands. '''
    result = test.run(testCommands, variables)
    return result

def cleanup(test, variables):
    ''' Cleanup a test directory.
    This is dangerous, since we use "rm -rf", so we attempt to
    verify that the directory is to be deleted by verifying that
    our "canary" file exists.
    '''
    cleanCommands = [
        "ls $(testDir)/DELETETHISDIRECTORYWHENDONE",
        "rm -rf $(testDir)"
        ]
    test.run(cleanCommands, variables)

def doWork(paths, period, verbose):
    modName = __name__ + '.doWork'
    variables = initVariables()
    if variables is None:
        print 'no variables'
        exit(1)
    
    repos = MonitorRepos(paths, period)
    if repos is None:
        exit(1)
    
    test = testRun(verbose)
    locate(test, variables)
    
    result = 0
    keepTestDirectory = False
    while (result == 0 or continueOnError) and not doExit:
        if repos.reposChangedSince():
            break
        newVariables = updateVariables()
        if newVariables is None:
            break
        for k, v in newVariables.iteritems():
            variables[k] = v
        result = runATest(test, variables)
        if result != 0:
            keepTestDirectory = True
            # Print the variables for this failed test.
            for k, v in variables.iteritems():
                print >>sys.stderr, '%s: %s "%s"' % (modName, k, v)
            if badSeedFile is not None:
                badSeedFile.write(variables['seed'] + '\n')
    
    if badSeedFile is not None:
        badSeedFile.close()

    os.chdir(homeDir)
    if not keepTestDirectory:
        cleanup(test, variables)

def main(argv=None): # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = __import__('__main__').__doc__.split("\n")[1]
    program_license = '''%s

  Created by Jim Lawson on %s.
  Copyright 2014 UC Berkeley. All rights reserved.

  Licensed under the Apache License 2.0
  http://www.apache.org/licenses/LICENSE-2.0

  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied.

USAGE
''' % (program_shortdesc, str(__date__))

    global chiselJar, defaultChiselJar
    global continueOnError
    try:
        # Setup argument parser
        parser = ArgumentParser(description=program_license, formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument("-c", "--continue", dest="continueOnError", help="continue on error [default: %(default)s]", action='store_true', default=continueOnError)
        parser.add_argument("-p", "--period", dest="periodMinutes", help="interval to check for repo updates (in minutes) [default: %(default)s]", type=int, default=15)
        parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
        parser.add_argument('-V', '--version', action='version', version=program_version_message)
        parser.add_argument('-J', '--chiselJar', dest='chiselJar', help='path to chisel jar to use for testing [default: %(default)s]', type=str, default=defaultChiselJar)
        parser.add_argument('-s', '--seed', dest='seed', help='seed (or file containing seeds', type=str, default=None)
        parser.add_argument('-b', '--badseed', dest='badseed', help='file to contain list of bad seeds', type=FileType('w'), default=None)
        parser.add_argument(dest="paths", help="paths to folders containing clones of github repositories to be tested [default: %(default)s]",  default=localRepoNames, metavar="path", nargs='*')

        # Process arguments
        args = parser.parse_args()

        paths = args.paths
        verbose = args.verbose
        global badSeedFile
        badSeedFile = args.badseed
        continueOnError = args.continueOnError

        global seed
        seed = args.seed

        if verbose > 0:
            print("Verbose mode on")

        # Install the signal handler to catch SIGTERM
        signal.signal(signal.SIGTERM, sigterm)
        period = timedelta(minutes = args.periodMinutes)
        doWork(paths, period, verbose)
        return 0
 
    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
    except Exception, e:
        if DEBUG or TESTRUN:
            raise(e)
        indent = len(program_name) * " "
        sys.stderr.write(program_name + ": " + repr(e) + "\n")
        sys.stderr.write(indent + "  for help use --help")
        return 2

if __name__ == "__main__":
    if DEBUG:
        sys.argv.append("-v")
    if TESTRUN:
        import doctest
        doctest.testmod()
    if PROFILE:
        import cProfile
        import pstats
        profile_filename = 'citJenkins.citjenkins_profile.txt'
        cProfile.run('main()', profile_filename)
        statsfile = open("profile_stats.txt", "wb")
        p = pstats.Stats(profile_filename, stream=statsfile)
        stats = p.strip_dirs().sort_stats('cumulative')
        stats.print_stats()
        statsfile.close()
        sys.exit(0)
    main()
