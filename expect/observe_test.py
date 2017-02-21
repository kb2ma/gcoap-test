#!/usr/bin/env python
# Copyright (c) 2016, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0

'''Tests Observe server. Creates RIOT example as the server, and reuses the
soscoap stats_reader as the client.

Options:

-a <addr>  -- Address of server
-x <dir>   -- Directory in which to execute the server script; must be location
              of the RIOT gcoap example app.
-y <dir>   -- Directory in which to execute the client script; must be location
              of the stats reader Python app.
-z <dir>   -- Directory in which to execute the remote client and server scripts;
              must be location of the libcoap example apps.

Example:

# tap example
# Set up networking
$ sudo ip tuntap add tap0 mode tap user kbee
$ sudo ip link set tap0 up
$ sudo ip address add fe80::bbbb:1/64 dev tap0

# Run test
$ ./observe_test.py -a fe80::bbbb:1 -x /home/kbee/dev/riot/repo/examples/gcoap -y /home/kbee/dev/soscoap/repo/examples/client -z /home/kbee/dev/libcoap/repo/examples

'''
from __future__ import print_function
import time
import os
import pexpect
import re
#from   stats_reader import StatsReader

def main(addr, serverDir, clientDir, remoteDir):
    '''Common setup for all tests

    server -- RIOT gcoap example server

    :param addr: string Server address
    :param serverDir: string Directory in which to run server, or None if pwd
    :param clientDir: string Directory in which to run client, or None if pwd
    :param remoteDir: string Directory in which to run remote client and server,
                             or None if pwd
    '''
    xfaceType = 'tap' if addr[:4] == 'fe80' else 'tun'
    print('Setup RIOT server for {0} interface'.format(xfaceType))

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
    print('Server setup OK')

    print('Setup stats reader client')
    client = pexpect.spawn('python stats_reader.py -s 5682 -a fe80::bbbb:2%tap0 -q stats', cwd=clientDir, env={'PYTHONPATH': '../..'})
    client.expect('Starting stats reader')
    print('Client setup OK')

    print('Setup libcoap remote server')
    remoteServer = pexpect.spawn(remoteDir + '/coap-server')
    # No output when start remote server
    remoteServer.expect(pexpect.TIMEOUT, timeout=2)
    print('Remote server started')

    try:
        registerObserve(remoteDir, client)
        triggerNotification(server, client)
        time.sleep(2)
        triggerNotification(server, client)
        deregisterObserve(remoteDir, client)
        time.sleep(2)
        verifyNoNotification(server, client)
    finally:
        server.close()
        print('Server close OK')
        client.close()
        print('Client close OK')
        remoteServer.close()
        print('Remote server close OK')

def registerObserve(remoteDir, client):
    print('Register for /cli/stats')

    remoteClient = pexpect.spawn(remoteDir + '/coap-client -N -m post -U -T 5a coap://[::1]:5681/reg')
    remoteClient.expect('v:1 t:NON c:POST')
    remoteClient.close()
    print('Remote client ran OK')

    pattern = '(2\.05; Observe len: 1; val: )(\d+\r\n)'
    client.expect(pattern, timeout=5)
    # Rerun regex to extract and print second group, the Observe option value.
    match = re.search(pattern, client.after)
    print('Client received /reg with Observe: {0}'.format(match.group(2)))

def deregisterObserve(remoteDir, client):
    print('Deregister from /cli/stats')

    remoteClient = pexpect.spawn(remoteDir + '/coap-client -N -m post -U -T 5a coap://[::1]:5681/dereg')
    remoteClient.expect('v:1 t:NON c:POST')
    remoteClient.close()
    print('Remote client ran OK')

    client.expect('2\.05; Observe len: 0;')
    print('Client received /dereg with no Observe')

def triggerNotification(server, client):
    server.sendline('coap get fe80::bbbb:1 5683 /time')
    server.expect('\w+ \d+ \d+:\d+:\d+\r\n')
    print('Server got time: {0}'.format(server.after))

    pattern = '(2\.05; Observe len: 1; val: )(\d+\r\n)'
    client.expect(pattern, timeout=5)
    # Rerun regex to extract and print second group, the Observe option value.
    match = re.search(pattern, client.after)
    print('Client received /cli/stats with Observe: {0}'.format(match.group(2)))

def verifyNoNotification(server, client):
    server.sendline('coap get fe80::bbbb:1 5683 /time')
    server.expect('\w+ \d+ \d+:\d+:\d+\r\n')
    print('Server got time: {0}'.format(server.after))

    client.expect(pexpect.TIMEOUT, timeout=2)
    print('Client did not receive /cli/stats notification, as expected')

if __name__ == "__main__":
    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='addr')
    parser.add_option('-x', type='string', dest='serverDir', default=None)
    parser.add_option('-y', type='string', dest='clientDir', default=None)
    parser.add_option('-z', type='string', dest='remoteDir', default=None)

    (options, args) = parser.parse_args()

    main(options.addr, options.serverDir, options.clientDir, options.remoteDir)
