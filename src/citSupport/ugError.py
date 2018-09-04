'''
Created on Jul 3, 2014

@author: jrl
'''


class Error(Exception):
    def __init__(self, msg):
        self.msg = msg
