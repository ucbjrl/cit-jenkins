'''
Created on Jul 3, 2014

@author: jrl
'''
import errno
import os
import random
import re
import string
import subprocess
import sys

class testRun():
    ''' Run a sequence of commands:
        - with possible variable substitution,
        - logging output,
        - and calling an external decision function to determine if execution should continue
    '''

    def __init__(self, verbose = 0):
        self.testVariableRE = re.compile(r'\$\((\w+)\)')
        self.verbose = verbose

    def run(self, commands, variables):
        ''' Run a sequence of commands, stopping on the first non-zero exit code. '''
        retcode = 1
        modName = 'testRun.run'

        def replaceVariable(matchobj):
            ''' Replace a $(variable) with its value. '''
            variable = matchobj.group(1)
            if variable in variables.keys():
                replacement = variables[variable]
                if self.verbose > 1:
                    print >>sys.stderr, '%s: replacing "$s" with "%s"' % (modName, variable, replacement)
                return replacement
            else:
                return matchobj.group(0)

        def basicTestResult(command, retcode):
            ''' Evaluate the retcode returned by command and return False if execution should stop. '''
            result = False
            if retcode < 0:
                print >>sys.stderr, "%s: \"%s\" terminated by signal %d" % (modName, command, -retcode)
            elif retcode > 0:
                print >>sys.stderr, "%s: \"%s\" returned %d" % (modName, command, retcode)
            else:
                result = True
            return result

        for command in commands:
            baseCommand = None
            testResult = basicTestResult
            # This may be:
            # - string: simple command, break on failure,
            # - tuple: (command, eval function),
            # - map: (command and testResult entries)
            if type(command) is tuple:
                (baseCommand, testResult) = command
            elif type(command) is dict:
                baseCommand = command['command']
                testResult = command['test']
            else:
                baseCommand = command

            # Does this command need a variable expanded?
            if variables is None:
                expandedCommand = baseCommand
            else:
                expandedCommand = self.testVariableRE.sub(replaceVariable, baseCommand)

            if self.verbose > 0:
                print >>sys.stderr, '%s: "%s" ...' % (modName, expandedCommand)
            retcode = subprocess.call(expandedCommand, shell=True)
            if self.verbose > 0:
                print >>sys.stderr, '%s: ... returned %d' % (modName, retcode)
            if not testResult(expandedCommand, retcode):
                break
        return retcode

