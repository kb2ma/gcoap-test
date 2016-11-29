#!/usr/bin/python
# Copyright (c) 2016, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
Defines and runs a GcoapTester for values received by a CoAP server. Provides
an example use of an SOS CoAP server. See class documentation for URIs.

Start the recorder on POSIX with:
   ``$PYTHONPATH=.. ./recorder.py``
'''
from   __future__ import print_function
import logging
import asyncore
import sys
from   soscoap  import MessageType
from   soscoap  import RequestCode
from   soscoap.resource import SosResourceTransfer
from   soscoap.msgsock  import MessageSocket
from   soscoap.server   import CoapServer

logging.basicConfig(filename='tester.log', level=logging.DEBUG, 
                    format='%(asctime)s %(module)s %(message)s')
log = logging.getLogger(__name__)

VERSION = '0.1'

class GcoapTester(object):
    '''Provides a server for testing gcoap client commands.
    
    Attributes:
        :_server:   CoapServer Provides CoAP message protocol
    
    Usage:
        #. cr = GcoapTester()  -- Create instance
        #. cr.start()  -- Starts to listen
        #. cr.close()  -- Releases sytem resources
        
    URIs:
        | /ver -- GET program version
        | /toobig -- CoAP PDU exceeds 128-byte buffer used by gcoap
    '''
    def __init__(self):
        self._server = CoapServer()
        self._server.registerForResourceGet(self._getResource)
        self._server.registerForResourcePut(self._putResource)
        self._server.registerForResourcePost(self._postResource)
        
    def close(self):
        '''Releases system resources.
        '''
        pass
                
    def _getResource(self, resource):
        '''Sets the value for the provided resource, for a GET request.
        '''
        log.debug('Resource path is {0}'.format(resource.path))
        if resource.path == '/ver':
            resource.type  = 'string'
            resource.value = VERSION
            log.debug('Got resource value')
        elif resource.path == '/toobig':
            resource.type  = 'string'
            resource.value = '1234567890' * 13
            log.debug('Got resource value')
        else:
            log.debug('Unknown path')
    
    def _postResource(self, resource):
        '''Records the value for the provided resource, for a POST request.
        
        :param resource.value: str ASCII in CSV format, with two fields:
                               1. int Time
                               2. int Value
        '''
        log.debug('Resource path is {0}'.format(resource.path))
        raise NotImplementedError('Unknown path')
    
    def _putResource(self, resource):
        '''Records the value for the provided resource, for a PUT request.
        
        :param resource.value: str ASCII in CSV format, with two fields:
                               1. int Time
                               2. int Value
        '''
        log.debug('Resource path is {0}'.format(resource.path))
        raise NotImplementedError('Unknown path')
    
    def start(self):
        '''Creates the server, and opens the file for this recorder.
        
        :raises IOError: If cannot open file
        '''
        self._server.start()

# Start the tester
if __name__ == '__main__':
    formattedPath = '\n\t'.join(str(p) for p in sys.path)
    log.info('Running gcoap tester with sys.path:\n\t{0}'.format(formattedPath))
    tester = None
    try:
        tester = GcoapTester()
        print('Sock it to me!')
        if tester:
            tester.start()
    except KeyboardInterrupt:
        pass
    except:
        log.exception('Catch-all handler for tester')
        print('\nAborting; see log for exception.')
    finally:
        if tester:
            tester.close()
            log.info('gcoap tester closed')


