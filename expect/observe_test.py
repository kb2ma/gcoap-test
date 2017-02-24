#!/usr/bin/env python
# Copyright (c) 2017, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0

'''Tests Observe server. Creates RIOT example as the server, and reuses the
soscoap stats_reader as the client.

Options:

-a <addr>  -- Address of server
-t <test> --- Name of test to run. Options:
                observe -- Register and listen for notifications for /cli/stats
                toomanymemos -- Try to register for too many resources
                toomanyobs -- Try to register too many observers
-x <dir>   -- Directory in which to execute the server script; must be the
              location of the RIOT gcoap example app.
-y <dir>   -- Directory in which to execute the client script; must be the
              location of the gcoap observer Python app.
-z <dir>   -- Directory in which to execute the remote client and server scripts;
              must be the location of the libcoap example apps.

Example:

# tap example
# Set up networking
$ sudo ip tuntap add tap0 mode tap user kbee
$ sudo ip link set tap0 up
$ sudo ip address add fe80::bbbb:1/64 dev tap0

# Run test
$ ./observe_test.py -a fe80::bbbb:1 -t observe -x /home/kbee/dev/riot/repo/examples/gcoap -y /home/kbee/dev/gcoap-test/repo -z /home/kbee/dev/libcoap/repo/examples

'''
from __future__ import print_function
import time
import os
import pexpect
import re
#from   stats_reader import StatsReader

def main(addr, testName, serverDir, clientDir, remoteDir):
    '''Common setup for all tests

    server -- RIOT gcoap example server

    :param addr: string Server address
    :param testName: string Name of test to run
    :param serverDir: string Directory in which to run server, or None if pwd
    :param clientDir: string Directory in which to run client, or None if pwd
    :param remoteDir: string Directory in which to run remote client and server,
                             or None if pwd
    '''
    xfaceType = 'tap' if addr[:4] == 'fe80' else 'tun'
    print('Setup Observe test for {0} interface'.format(xfaceType))

    if xfaceType == 'tap':
        server = pexpect.spawn('make term', cwd=serverDir)
        server.expect('gcoap example app')
    else:
        server = pexpect.spawn('make term BOARD="samr21-xpro"')
        server.expect('Welcome to pyterm!')
    time.sleep(1)

    # configure network interfaces
    if xfaceType == 'tap':
        server.sendline('ifconfig 6 add unicast fe80::bbbb:2/64')
        server.expect('success:')
    else:
        server.sendline('ifconfig 8 add unicast bbbb::2/64')
        server.expect('success:')
        server.sendline('ncache add 8 bbbb::1')
        server.expect('success:')
    time.sleep(2)
    print('gcoap Server setup OK')

    client = pexpect.spawn('python -m gcoaptest.observer -s 5684 -a fe80::bbbb:2%tap0', cwd=clientDir, env={'PYTHONPATH': '../../soscoap/repo'})
    client.expect('Starting gcoap observer')
    time.sleep(1)
    print('Client setup OK')

    remoteServer = pexpect.spawn(remoteDir + '/coap-server')
    # No output when start remote server
    remoteServer.expect(pexpect.TIMEOUT, timeout=2)
    print('Remote server setup OK')
    print('Pause 20 seconds to seed Observe value\n')
    time.sleep(20)

    try:
        client2 = None
        if testName == 'observe':
            registerObserve(remoteDir, client, 'stats')
            triggerNotification(server, client, 'stats')
            time.sleep(2)
            triggerNotification(server, client, 'stats')
            deregisterObserve(remoteDir, client, 'stats')
            time.sleep(2)
            verifyNoNotification(server, client, 'stats')

        elif testName == 'toomanymemos':
            registerObserve(remoteDir, client, 'stats')
            registerObserve(remoteDir, client, 'core', expectsRejection=True)

        elif testName == 'toomanyobs':
            registerObserve(remoteDir, client, 'stats')

            client2 = pexpect.spawn('python -m gcoaptest.observer -s 5686 -a fe80::bbbb:2%tap0', cwd=clientDir, env={'PYTHONPATH': '../../soscoap/repo'})
            client2.expect('Starting gcoap observer')
            time.sleep(1)
            print('Client 2 setup OK')

            registerObserve(remoteDir, client2, 'stats', remotePort=5687, expectsRejection=True)
    finally:
        server.close()
        client.close()
        if client2:
            client2.close()
        remoteServer.close()
        print('\nServer, client, remote server close OK')

def registerObserve(remoteDir, client, resource, remotePort=5685, expectsRejection=False):
    '''Registers for Observe notifications for a resource.

    :param remoteDir: string Directory in which to run libcoap example client
    :param client: spawn Pexpect process for observer Python client
    :param resource: string Name of the resource on the gcoap server to observe
    :param remotePort: int Port on which client listens for commands from
                       remote client
    :param expectsRejection: boolean If true, we expect the client Observe
                             registration will fail
    '''
    regCmd       = '{0}/coap-client -N -m post -U -T 5a coap://[::1]:{1}/reg/{2}'
    remoteClient = pexpect.spawn(regCmd.format(remoteDir, remotePort, resource))
    remoteClient.expect('v:1 t:NON c:POST')
    remoteClient.close()
    print('Remote client sent /reg command to client')

    if expectsRejection:
        i = client.expect('2\.05; Observe len: 0', timeout=5)
        print('Client registration for {0} rejected, as expected'.format(resource))
    else:
        pattern = '(2\.05; Observe len: 1; val: )(\d+\r\n)'
        client.expect(pattern, timeout=5)
        # Rerun regex to extract and print second group, the Observe option value.
        match = re.search(pattern, client.after)
        print('Client registered for {0}; Observe value: {1}'.format(resource, match.group(2)))

def deregisterObserve(remoteDir, client, resource, remotePort=5685):
    deregCmd     = '{0}/coap-client -N -m post -U -T 5a coap://[::1]:{1}/dereg/{2}'
    remoteClient = pexpect.spawn(deregCmd.format(remoteDir, remotePort, resource))
    remoteClient.expect('v:1 t:NON c:POST')
    remoteClient.close()
    print('Remote client sent /dereg command to client')

    client.expect('2\.05; Observe len: 0;')
    print('Client deregistered from {0}; no Observe value, as expected'.format(resource))

def triggerNotification(server, client, resource):
    server.sendline('coap get fe80::bbbb:1 5683 /time')
    server.expect('\w+ \d+ \d+:\d+:\d+\r\n')

    pattern = '(2\.05; Observe len: 1; val: )(\d+\r\n)'
    client.expect(pattern, timeout=5)
    # Rerun regex to extract and print second group, the Observe option value.
    match = re.search(pattern, client.after)
    print('Client received {0} notification; Observe value: {1}'.format(resource, match.group(2)))

def verifyNoNotification(server, client, resource):
    server.sendline('coap get fe80::bbbb:1 5683 /time')
    server.expect('\w+ \d+ \d+:\d+:\d+\r\n')

    client.expect(pexpect.TIMEOUT, timeout=2)
    print('Client did not receive {0} notification, as expected'.format(resource))

if __name__ == "__main__":
    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='addr')
    parser.add_option('-t', type='string', dest='testName')
    parser.add_option('-x', type='string', dest='serverDir', default=None)
    parser.add_option('-y', type='string', dest='clientDir', default=None)
    parser.add_option('-z', type='string', dest='remoteDir', default=None)

    (options, args) = parser.parse_args()

    main(options.addr, options.testName, options.serverDir, options.clientDir,
                                                            options.remoteDir)
