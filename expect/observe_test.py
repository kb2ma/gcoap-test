#!/usr/bin/env python
# Copyright (c) 2017, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0

'''Tests Observe server. Uses three components:

* Observe server -- RIOT gcoap example
* Observe client -- gcoap-test Observer sends requests to server.
* Support client/server -- CoAP client and server used to support the Observe
                           client and server. The support server is used as the
                           target for CoAP messages sent by the RIOT gcoap
                           example to trigger its Observe notifications. The
                           support client is used to send commands to the
                           gcoap-test Observer client. The support client and
                           server are provided by libcoap's example apps.

Options:

-a <addr>  -- Address of gcoap server
-r <ack|ignore|reset|reset_non>
           -- Notification response options; only applies to 'observe' test.
              If this option is absent, notifications are sent non-confirmably.
              'ack' -- send ACK for confirmable notifications;
              'ignore' -- ignore confirmable notifications
              'reset' -- send RST for confirmable notifications
              'reset_non' -- send RST for non-confirmable notifications
-i         -- Ignore confirmable; only applies to 'observe' test for the client
              to ignore confirmable notifications
-t <test> --- Name of test to run. Options:
                observe -- Register and listen for notifications for /cli/stats
                toomanymemos -- Try to register for too many resources
                toomany4resource -- Try to register more than one observer for
                                    a resource
                change-token -- Re-register an observer for a resource with a
                                new token
                two-observers -- Register two observers, each for a different
                                 resource
                reg-cleanup -- Ensures registrations are deleted properly
-x <dir>   -- Directory in which to execute the server script; must be the
              location of the RIOT gcoap CLI test app (riot-gcoap-test).
-y <dir>   -- Directory in which to execute the client script; must be the
              location of the gcoap observer Python app.
-z <dir>   -- Directory in which to execute the support client and server
              scripts; must be the location of the libcoap example apps.

Example:

# tap example
# Set up networking
$ sudo ip tuntap add tap0 mode tap user kbee
$ sudo ip link set tap0 up
$ sudo ip address add fe80::bbbb:1/64 dev tap0

# Run test; uses special riot-gcoap-test app
$ ./observe_test.py -a fe80::bbbb:2 -t observe -x /home/kbee/dev/riot-gcoap-test/repo -y /home/kbee/dev/gcoap-test/repo -z /home/kbee/dev/libcoap/repo/examples

# tun example
# Reset samr21 board, *then* set up networking.
# Must reset board and networking before each test!
$ cd /home/kbee/dev/riot/repo/dist/tools/tunslip
$ sudo ./tunslip6 -s ttyUSB0 -t tun0 bbbb::1/64
# new terminal
$ sudo ip -6 route add aaaa::/64 dev tun0

# Run test
$ ./observe_test.py -a bbbb::2 -t observe -x /home/kbee/dev/riot-gcoap-test/repo -y /home/kbee/dev/gcoap-test/repo -z /home/kbee/dev/libcoap/repo/examples

'''
from __future__ import print_function
import time
import os
import signal
import pexpect
import re

class ObserveTester(object):
    '''
    Test harness for gcoap Observe testing.
    
    Attributes:
        :_server: Observe server provided by RIOT gcoap example
        :_client: Observe client provided by gcoap-test observer
        :_supportServer: Provided by libcoap example server
        :_serverQualifiedAddr: IP address for server, including any suffixed
                               interface identifier, like '%tap0'
        :_supportServerAddr: IP address for support server
        :_clientDir: Directory in which to run client, or None if pwd
        :_supportDir: Directory in which to run support client/server, or None
                      if pwd
        :_notifResponse: If not None, observe notifications are sent confirmably.
                      'ack' -- send an ACK response to the notification
                      'ignore' -- ignore the notifications
                      'reset' -- send a RST response to the notification
                      'reset_non' -- send a RST response non-confirmably

    Usage:
        1. Create instance
        2. runTest()
        3. close() instance; best in a finally block around the first two steps
    '''

    def __init__(self, addr, serverDir, clientDir, supportDir, notifResponse):
        '''Common setup for running a test

        :param addr: string Server address
        :param serverDir: string Directory in which to run server, or None if pwd
        :param clientDir: string Directory in which to run client, or None if pwd
        :param supportDir: string Directory in which to run support client/server,
                                 or None if pwd
        :param conAction: string Direct server to send notifications confirmably
                                 and either ACK, RST, or ignore the notifications
        '''
        self._clientDir  = clientDir
        self._supportDir = supportDir
        self._notifResponse  = notifResponse
        
        xfaceType = 'tap' if addr[:4] == 'fe80' else 'tun'
        if xfaceType == 'tap':
            self._serverQualifiedAddr = '{0}%tap0'.format(addr)
            self._supportServerAddr   = 'fe80::bbbb:1'
        else:
            self._serverQualifiedAddr = addr
            self._supportServerAddr   = 'bbbb::1'
        print('Setup Observe test for {0} interface'.format(xfaceType))

        # set up server
        if xfaceType == 'tap':
            self._server = pexpect.spawn('make term', cwd=serverDir)
            self._server.expect('gcoap CLI test app')
        else:
            self._server = pexpect.spawn('make term BOARD="samr21-xpro"', cwd=serverDir)
            self._server.expect('Welcome to pyterm!')
        time.sleep(1)

        # configure network interfaces; must use unqualified server address
        if xfaceType == 'tap':
            self._server.sendline('ifconfig 6 add unicast {0}/64'.format(addr))
            self._server.expect('success:')
        else:
            self._server.sendline('ifconfig 8 add unicast {0}/64'.format(addr))
            self._server.expect('success:')
            self._server.sendline('nib neigh add 8 {0}'.format(self._supportServerAddr))
            time.sleep(1)
            self._server.sendline('nib neigh')
            self._server.expect(self._supportServerAddr)
        time.sleep(2)
        print('gcoap Server setup OK')

        # set up client
        self._clientCmd = 'python -m gcoaptest.observer -s {0} -a {1}'

        self._client = pexpect.spawn(self._clientCmd.format(5684, self._serverQualifiedAddr),
                               cwd=self._clientDir,
                               env={'PYTHONPATH': '../../soscoap/repo'})
        self._client.expect('Starting gcoap observer')
        time.sleep(1)
        print('Client setup OK')

        # set up support server
        self._supportServer = pexpect.spawn(self._supportDir + '/coap-server')
        # No output when start support server
        self._supportServer.expect(pexpect.TIMEOUT, timeout=2)
        print('Support server setup OK')

    def runTest(self, testName):
        '''Runs a test

        :param testName: string Test to run
        '''
        if testName == 'observe':
            if (self._notifResponse == 'ack'
                    or self._notifResponse == 'ignore'
                    or self._notifResponse == 'reset'):
                self._configConNotification(self._server)
            self._registerObserve(self._client, 'stats')

            self._triggerNotification(self._server, self._client, 'stats')
            if self._notifResponse == 'ack' or self._notifResponse == None:
                # normal success cases for confirm, non-confirm
                time.sleep(4)
                self._triggerNotification(self._server, self._client, 'stats')
                self._deregisterObserve(self._client, 'stats')
                time.sleep(4)
                self._verifyNoNotification(self._server, self._client, 'stats')
            else:
                if self._notifResponse == 'ignore':
                    delay = 95
                    print('Pause {0} seconds for all retries to timeout'.format(delay))
                elif self._notifResponse == 'reset' or self._notifResponse == 'reset_non':
                    delay = 4
                else:
                    # will error because delay undefined
                    pass
                time.sleep(delay)
                self._verifyNoNotification(self._server, self._client, 'stats')

        elif testName == 'toomanymemos':
            self._registerObserve(self._client, 'stats')
            self._registerObserve(self._client, 'core', expectsRejection=True)

        elif testName == 'toomany4resource':
            self._registerObserve(self._client, 'stats')

            try:
                client2 = pexpect.spawn(self._clientCmd.format(5686,
                                        self._serverQualifiedAddr),
                                        cwd=self._clientDir,
                                        env={'PYTHONPATH': '../../soscoap/repo'})
                client2.expect('Starting gcoap observer')
                time.sleep(1)
                print('Client 2 setup OK')

                self._registerObserve(client2, 'stats', commandPort=5687,
                                                  expectsRejection=True)
            finally:
                if client2:
                    client2.close()

        elif testName == 'change-token':
            self._registerObserve(self._client, 'stats')
            self._registerObserve(self._client, 'stats')

        elif testName == 'two-observers':
            self._registerObserve(self._client, 'stats')

            try:
                client2 = pexpect.spawn(self._clientCmd.format(5686,
                                        self._serverQualifiedAddr),
                                        cwd=self._clientDir,
                                        env={'PYTHONPATH': '../../soscoap/repo'})
                client2.expect('Starting gcoap observer')
                time.sleep(1)
                print('Client 2 setup OK')

                self._registerObserve(client2, 'core', commandPort=5687,
                                                 expectsRejection=False)
            finally:
                if client2:
                    client2.close()

        elif testName == 'reg-cleanup':
            self._registerObserve(self._client, 'stats')
            self._registerObserve(self._client, 'core')

            try:
                client3 = None
                client2 = pexpect.spawn(self._clientCmd.format(5686,
                                        self._serverQualifiedAddr),
                                        cwd=self._clientDir,
                                        env={'PYTHONPATH': '../../soscoap/repo'})
                client2.expect('Starting gcoap observer')
                time.sleep(1)
                print('Client 2 setup OK')

                self._registerObserve(client2, 'stats2', commandPort=5687,
                                                         expectsRejection=True)

                self._deregisterObserve(self._client, 'core')

                # Must use a third client becase we want to test the failure
                # that client2 was not cleared by the deregister step.
                client3 = pexpect.spawn(self._clientCmd.format(5688,
                                        self._serverQualifiedAddr),
                                        cwd=self._clientDir,
                                        env={'PYTHONPATH': '../../soscoap/repo'})
                client3.expect('Starting gcoap observer')
                time.sleep(1)
                print('Client 3 setup OK')

                self._registerObserve(client3, 'stats2', commandPort=5689,
                                                         expectsRejection=False)
            finally:
                if client2:
                    client2.close()
                if client3:
                    client3.close()

        else:
            print('Unexpected test name: {0}'.format(testName))

    def close(self):
        '''Releases resources
        '''
        if self._server:
            print('Force close gcoap CLI server...')
            for i in range(5):
                if self._server.isalive():
                    time.sleep(i)
                    self._server.kill(signal.SIGKILL)
            if self._server.isalive():
                print('Could not force close gcoap CLI server')

        if self._client:
            self._client.close()
        if self._supportServer:
            self._supportServer.close()
        print('\nServer, client, support server close OK')
        

    def _registerObserve(self, client, resource, commandPort=5685,
                                          expectsRejection=False):
        '''Registers for Observe notifications for a resource.

        :param client: spawn Pexpect process for observer Python client
        :param resource: string Name of the resource on the gcoap server to observe
        :param commandPort: int Port on which client listens for commands from
                            command client
        :param expectsRejection: boolean If true, we expect the client Observe
                                 registration will fail
        '''
        commandClient = None
        if self._notifResponse == 'ignore' or self._notifResponse == 'reset':
            responseCmd = '{0}/coap-client -N -m post -U -T 5a coap://[::1]:{1}/notif/con_{2}'
            commandClient = pexpect.spawn(responseCmd.format(self._supportDir, commandPort,
                                                             self._notifResponse))
            print_text = 'con_{0}'.format(self._notifResponse)
        elif self._notifResponse == 'reset_non':
            responseCmd = '{0}/coap-client -N -m post -U -T 5a coap://[::1]:{1}/notif/non_reset'
            commandClient = pexpect.spawn(responseCmd.format(self._supportDir, commandPort))
            print_text = 'non_reset'

        if commandClient:
            commandClient.expect('v:1 t:NON c:POST')
            commandClient.close()
            print('Command client sent /notif/{0} command to client'.format(print_text))
            time.sleep(1)

        regCmd       = '{0}/coap-client -N -m post -U -T 5a coap://[::1]:{1}/reg/{2}'
        commandClient = pexpect.spawn(regCmd.format(self._supportDir, commandPort,
                                                                      resource))
        commandClient.expect('v:1 t:NON c:POST')
        commandClient.close()
        print('Command client sent /reg command to client')

        if expectsRejection:
            i = client.expect('2\.05; Observe len: 0', timeout=5)
            print('Client registration for {0} rejected, as expected'.format(resource))
        else:
            pattern = '(2\.05; Observe len: 1; val: )(\d+\r\n)'
            client.expect(pattern, timeout=5)
            # Rerun regex to extract and print second group, the Observe option value.
            match = re.search(pattern, client.after)
            print('Client registered for {0}; Observe value: {1}'.format(resource,
                                                                         match.group(2)))

    def _deregisterObserve(self, client, resource, commandPort=5685):
        deregCmd     = '{0}/coap-client -N -m post -U -T 5a coap://[::1]:{1}/dereg/{2}'
        commandClient = pexpect.spawn(deregCmd.format(self._supportDir, commandPort,
                                                                        resource))
        commandClient.expect('v:1 t:NON c:POST')
        commandClient.close()
        print('Command client sent /dereg command to client')

        client.expect('2\.05; Observe len: 0;')
        print('Client deregistered from {0}; no Observe value, as expected'.format(resource))

    def _configConNotification(self, server):
        server.sendline('coap config obs.msg_type CON')
        server.expect('Observe notifications now sent CON\r\n')

    def _triggerNotification(self, server, client, resource):
        server.sendline('coap get {0} 5683 /time'.format(self._supportServerAddr))
        # Expects month day time
        server.expect('\w+ \d+ \d+:\d+:\d+\r\n')

        pattern = '(2\.05; Observe len: 1; val: )(\d+\r\n)'
        client.expect(pattern, timeout=5)
        # Rerun regex to extract and print second group, the Observe option value.
        match = re.search(pattern, client.after)
        print('Client received {0} notification; Observe value: {1}'.format(resource,
                                                                            match.group(2)))

    def _verifyNoNotification(self, server, client, resource):
        server.sendline('coap get {0} 5683 /time'.format(self._supportServerAddr))
        server.expect('\w+ \d+ \d+:\d+:\d+\r\n')

        client.expect(pexpect.TIMEOUT, timeout=2)
        print('Client did not receive {0} notification, as expected'.format(resource))

if __name__ == "__main__":
    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='addr')
    parser.add_option('-r', type='string', dest='notifResponse', default=None)
    parser.add_option('-t', type='string', dest='testName')
    parser.add_option('-x', type='string', dest='serverDir', default=None)
    parser.add_option('-y', type='string', dest='clientDir', default=None)
    parser.add_option('-z', type='string', dest='supportDir', default=None)

    (options, args) = parser.parse_args()

    tester = None
    try:
        tester = ObserveTester(options.addr, options.serverDir, options.clientDir,
                               options.supportDir, options.notifResponse)
        # pause here so tester is instantiated in case must close abruply
        print('Pause 20 seconds to seed Observe value\n')
        time.sleep(20)
        tester.runTest(options.testName)
    finally:
        if tester:
            tester.close()
