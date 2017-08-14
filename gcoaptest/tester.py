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
import time
from   soscoap  import MessageType
from   soscoap  import RequestCode
import soscoap
from   soscoap.resource import SosResourceTransfer
from   soscoap.msgsock  import MessageSocket
from   soscoap.server   import CoapServer, IgnoreRequestException

logging.basicConfig(filename='tester.log', level=logging.DEBUG, 
                    format='%(asctime)s %(module)s %(message)s')
log = logging.getLogger(__name__)

VERSION = '0.1'

class GcoapTester(object):
    '''Provides a server for testing gcoap client commands.
    
    Attributes:
        :_server:   CoapServer Provides CoAP message protocol
        :_delay:    Time in seconds to delay a response; useful for testing
    
    Usage:
        #. cr = GcoapTester()  -- Create instance
        #. cr.start()  -- Starts to listen
        #. cr.close()  -- Releases sytem resources
        
    URIs:
        | /ver -- GET program version
        | /toobig -- GET large text payload. CoAP PDU exceeds 128-byte buffer
                     used by gcoap.
        | /ignore -- GET that does not respond.
        | Configuration
        | /cf/delay -- POST integer seconds to delay future responses
        | /ver/ignores -- PUT count of /ver requests to ignore before responding;
                          tests client retry mechanism
    '''
    def __init__(self, port=soscoap.COAP_PORT):
        '''Pass in port for non-standard CoAP port.
        '''
        self._server = CoapServer(port=port)
        self._server.registerForResourceGet(self._getResource)
        self._server.registerForResourcePut(self._putResource)
        self._server.registerForResourcePost(self._postResource)
        self._delay = 0
        self._verIgnores = 0
        
    def close(self):
        '''Releases system resources.
        '''
        pass
                
    def _getResource(self, resource):
        '''Sets the value for the provided resource, for a GET request.
        '''
        log.debug('Resource path is {0}'.format(resource.path))
        if resource.path == '/ver':
            if self._verIgnores > 0:
                self._verIgnores = self._verIgnores - 1
                raise IgnoreRequestException
                return
            else:
                resource.type  = 'string'
                resource.value = VERSION
        elif resource.path == '/toobig':
            resource.type  = 'string'
            resource.value = '1234567890' * 13
        elif resource.path == '/ignore':
            time.sleep(self._delay)
            raise IgnoreRequestException
            return
        else:
            time.sleep(self._delay)
            raise NotImplementedError('Unknown path')
            return

        time.sleep(self._delay)
    
    def _postResource(self, resource):
        '''Accepts the value for the provided resource, for a POST request.
        '''
        log.debug('Resource path is {0}'.format(resource.path))
        if resource.path == '/cf/delay':
            self._delay = int(resource.value)
            log.debug('Post delay value: {0}'.format(self._delay))
        else:
            time.sleep(self._delay)
            raise NotImplementedError('Unknown path: {0}'.format(resource.path))
    
    def _putResource(self, resource):
        '''Accepts the value for the provided resource, for a PUT request.
        '''
        if resource.path == '/ver/ignores':
            self._verIgnores = int(resource.value)
            log.debug('Ignores for /ver: {0}'.format(self._verIgnores))
        else:
            raise NotImplementedError('Unknown path: {0}'.format(resource.path))

    def start(self):
        '''Creates the server, and opens the file for this recorder.
        
        :raises IOError: If cannot open file
        '''
        self._server.start()

# Start the tester
if __name__ == '__main__':
    from optparse import OptionParser

    formattedPath = '\n\t'.join(str(p) for p in sys.path)
    log.info('Running gcoap tester with sys.path:\n\t{0}'.format(formattedPath))

    # read command line
    parser = OptionParser()
    parser.add_option('-p', type='int', dest='port', default=soscoap.COAP_PORT)

    (options, args) = parser.parse_args()
    log.info('Using port {0}'.format(options.port))

    tester = None
    try:
        tester = GcoapTester(options.port)
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


