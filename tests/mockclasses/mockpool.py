# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>

class mockpool():

    responses = {}

    def __init__(self, processes=None):
       
        pass

    def apply_async(self, func, args):

        return mockresult( self.responses[args[0]].pop(0) )
    
    def close(*arg):

        pass
    
    def join(*arg):
       
        pass

class mockresult():
    
    def __init__(self, res):

        self.result = res
    
    def get(self,timeout=None):
    
        return self.result  
