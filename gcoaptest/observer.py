#!/usr/bin/python
# Copyright (c) 2017, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
A CoAP client to query and subscribe to Observe notifications from the RIOT
 gcoap example.

Options:
   | -a <hostAddr> -- Host address to query
   | -s <port> -- Source port from which to send query and listen for
   |              response. Valuable for the Observe mechanism, where the
   |              server periodically sends responses. Also uses <port>+1 to
   |              listen for commands. For example, use of '-s 5682' means
   |              that ports 5682 and 5683 will be used.

Run the observer on POSIX with:
   ``$ PYTHONPATH=../../soscoap/repo ./gcoap_observer.py -s 5682 -a fe80::bbbb:2%tap0``
'''
from   __future__ import print_function
import logging
import asyncore
import random
import sys
from   soscoap  import CodeClass
from   soscoap  import MessageType
from   soscoap  import OptionType
from   soscoap  import RequestCode
from   soscoap  import ClientResponseCode
from   soscoap  import COAP_PORT
from   soscoap.resource import SosResourceTransfer
from   soscoap.message  import CoapMessage
from   soscoap.message  import CoapOption
from   soscoap.msgsock  import MessageSocket
from   soscoap.client   import CoapClient
from   soscoap.server   import CoapServer

logging.basicConfig(filename='observer.log', level=logging.DEBUG, 
                    format='%(asctime)s %(module)s %(message)s')
log = logging.getLogger(__name__)

VERSION = '0.1'

class GcoapObserver(object):
    '''Reads statistics from a RIOT gcoap URL.

    NB: As shown in the Usage section below, StatsReader starts the asyncore
    loop before sending the query, like a server. This approach means the
    query must be called via another thread. Another approach would be to use
    asyncore's capabilities to create a single-use CoapClient and send the
    query at startup, in the same thread.
    
    Attributes:
        :_addrTuple: tuple IPv6 address tuple for message destination
        :_client:    CoapClient Provides CoAP client for server queries
        :_registeredPaths: string:bytearray, where the key is the short name
                           for the path, and the value is the token used to
                           register for Observe notifications for the path
        :_server:    CoapServer Provides CoAP server for remote client commands
    
    Usage:
        #. sr = StatsReader(hostAddr, hostPort, sourcePort, query)  -- Create instance
        #. sr.start() -- Starts asyncore networking loop
        #. sr.close() -- Cleanup
    '''
    def __init__(self, hostAddr, hostPort, sourcePort):
        '''Initializes on destination host and source port.

        Also uses sourcePort + 1 for the server to receive commands.
        '''
        self._hostTuple  = (hostAddr, hostPort)
        self._client     = CoapClient(sourcePort=sourcePort, dest=self._hostTuple)
        self._client.registerForResponse(self._responseClient)

        self._server     = CoapServer(port=sourcePort+1)
        self._server.registerForResourcePost(self._postServerResource)

        self._registeredPaths = {}

    def _responseClient(self, message):
        '''Reads a response to a request
        '''
        prefix   = '0' if message.codeDetail < 10 else ''
        obsList  = message.findOption(OptionType.Observe)
        obsValue = '<none>' if len(obsList) == 0 else obsList[0].value
        obsText  = 'len: {0}; val: {1}'.format(len(obsList), obsValue)
        
        print('Response code: {0}.{1}{2}; Observe {3}'.format(message.codeClass, prefix,
                                                              message.codeDetail, obsText))

        if message.messageType == MessageType.CON:
            self._ackConfirmNotification(message)

    def _postServerResource(self, resource):
        '''Reads a command
        '''
        log.debug('Resource path is {0}'.format(resource.path))
        
        observeAction = None
        observePath   = None
        if resource.path == '/reg/stats':
            observeAction = 'reg'
            observePath   = 'stats'
        elif resource.path == '/reg/core':
            observeAction = 'reg'
            observePath   = 'core'
        elif resource.path == '/reg/stats2':
            observeAction = 'reg'
            observePath   = 'stats2'
        elif resource.path == '/dereg/stats':
            observeAction = 'dereg'
            observePath   = 'stats'
        elif resource.path == '/dereg/core':
            observeAction = 'dereg'
            observePath   = 'core'
        elif resource.path == '/dereg/stats2':
            observeAction = 'dereg'
            observePath   = 'stats2'

        self._query(observeAction, observePath)

    def _query(self, observeAction, observePath):
        '''Runs the reader's query

        :param observeAction: string -- reg (register), dereg (deregister);
                              triggers inclusion of Observe option
        :param observePath: string Path for register/deregister
        '''
        # create message
        msg             = CoapMessage(self._hostTuple)
        msg.messageType = MessageType.NON
        msg.codeClass   = CodeClass.Request
        msg.codeDetail  = RequestCode.GET
        msg.messageId   = random.randint(0, 65535)

        if observePath == 'core':
            msg.addOption( CoapOption(OptionType.UriPath, '.well-known') )
            msg.addOption( CoapOption(OptionType.UriPath, 'core') )
        elif observePath == 'stats':
            msg.addOption( CoapOption(OptionType.UriPath, 'cli') )
            msg.addOption( CoapOption(OptionType.UriPath, 'stats') )
        elif observePath == 'stats2':
            msg.addOption( CoapOption(OptionType.UriPath, 'cli') )
            msg.addOption( CoapOption(OptionType.UriPath, 'stats2') )

        if observeAction == 'reg':
            # register
            msg.addOption( CoapOption(OptionType.Observe, 0) )
            msg.tokenLength = 2
            msg.token       = bytearray(2)
            msg.token[0]    = random.randint(0, 255)
            msg.token[1]    = random.randint(0, 255)
            self._registeredPaths[observePath] = msg.token
        elif observeAction == 'dereg':
            # deregister
            msg.addOption( CoapOption(OptionType.Observe, 1) )
            msg.tokenLength = 2
            msg.token       = self._registeredPaths[observePath]
            # assume deregistration will succeed
            del self._registeredPaths[observePath]

        # send message
        log.debug('Sending query')
        self._client.send(msg)

    def _ackConfirmNotification(self, notif):
        '''Sends an empty ACK response to a confirmable notification

        :param notif: CoapMessage Observe notification from server
        '''
        msg             = CoapMessage(notif.address)
        msg.messageType = MessageType.ACK
        msg.codeClass   = CodeClass.Empty
        msg.codeDetail  = ClientResponseCode.Empty
        msg.messageId   = notif.messageId
        msg.tokenLength = 0
        msg.token       = None

        log.debug('Sending ACK for CON notification')
        self._client.send(msg)

    def start(self):
        '''Starts networking; returns when networking is stopped.

        Only need to start client, which automatically starts server, too.
        '''
        self._client.start()

    def close(self):
        '''Releases resources'''
        self._client.close()

# Start the observer
if __name__ == '__main__':
    formattedPath = '\n\t'.join(str(p) for p in sys.path)
    log.info('Running gcoap observer with sys.path:\n\t{0}'.format(formattedPath))

    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='hostAddr')
    parser.add_option('-p', type='int', dest='hostPort', default=COAP_PORT)
    parser.add_option('-s', type='int', dest='sourcePort', default=COAP_PORT)

    (options, args) = parser.parse_args()
    
    reader = None
    try:
        observer = GcoapObserver(options.hostAddr, options.hostPort, options.sourcePort)
        print('Starting gcoap observer')
        observer.start()
    except KeyboardInterrupt:
        pass
    except:
        log.exception('Catch-all handler for gcoap observer')
        print('\nAborting; see log for exception.')
    finally:
        if observer:
            observer.close()
            log.info('gcoap observer closed')


