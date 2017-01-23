#!/usr/bin/env python
# Copyright (c) 2016, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0

'''Creates RIOT example app, and uses it to send GET requests for resources
from a gcoaptest server. Internally creates a required fixed IP address to
communicate with the server.

Before running, may need to manually create network interface and fixed IP address
for gcoaptest server, as well as start the server itself. See examples below.

Options:

-a <addr>  -- Address of server
-d <secs>  -- Server built-in response delay, in seconds
-r <count> -- Number of times to repeat query, with a 1 second wait between
              response and next request. For 'repeat-get' test only.
-t <test> --- Name of test to run. Options:
                repeat-get -- Repeats a sinple GET request
                toobig -- Requests a response that is too long to process
                toomany -- Makes a request when the limit of open requests has
                           been reached
-x <dir>   -- Directory in which to execute the script; must be location of
              RIOT gcoap example app.

Example:

# tap example
# Set up networking
$ sudo ip tuntap add tap0 mode tap user kbee
$ sudo ip link set tap0 up
$ sudo ip address add fe80::bbbb:1/64 dev tap0

# Start gcoaptest server. See gcoaptest/runtester script.
# Ensure gcoap_cli binary build is up to date.

# Run test
$ ./riot2gcoaptest.py -a fe80::bbbb:1 -t repeat-get -d 1 -r 50 -x /home/kbee/dev/riot/repo/examples/gcoap

# tun example
# Reset samr21 board, then set up networking
$ cd /home/kbee/dev/riot/repo/dist/tools/tunslip
$ sudo ./tunslip6 -s ttyUSB0 -t tun0 bbbb::1/64
# new terminal
$ sudo ip -6 route add aaaa::/64 dev tun0

# Start gcoaptest server. See gcoaptest/runtester script.

# Run test
$ ./riot2gcoaptest.py -a bbbb::1 -t repeat-get -d 1 -r 50 -x /home/kbee/dev/riot/repo/examples/gcoap

Implementation Notes:

All Pexpect subprocesses are closed explicitly. Otherwise, we have seen the RIOT
terminal persist.
'''
from __future__ import print_function
import time
import os
import pexpect

def main(addr, testName, serverDelay, repeatCount):
    '''Common setup for all tests
    '''
    xfaceType = 'tap' if addr[:4] == 'fe80' else 'tun'
    print('Setup RIOT client for {0} interface'.format(xfaceType))

    if xfaceType == 'tap':
        child = pexpect.spawn('make term')
        child.expect('gcoap example app')
    else:
        child = pexpect.spawn('make term BOARD="samr21-xpro"')
        child.expect('Welcome to pyterm!')

    # configure network interfaces
    if xfaceType == 'tap':
        child.sendline('ifconfig 6 add unicast fe80::bbbb:2/64')
        child.expect('success:')
    else:
        time.sleep(1)
        child.sendline('ifconfig 8 add unicast bbbb::2/64')
        child.expect('success:')
        child.sendline('ncache add 8 bbbb::1')
        child.expect('success:')

    if testName == 'repeat-get':
        runRepeatGet(child, addr, serverDelay, repeatCount)
    elif testName == 'toobig':
        runToobig(child, addr)
    elif testName == 'toomany':
        runToomany(child, addr)
    else:
        print('Unexpected test name: {0}'.format(testName))

def runRepeatGet(child, addr, serverDelay, repeatCount):
    '''Repeats a simple GET request
    '''
    print('Test: Repeat GET /ver')
    time.sleep(1)
    child.sendline('coap post {0} 5683 /cf/delay {1}'.format(addr, serverDelay))
    child.expect('code 2\.04')
    print('Server delay set to {0}\n'.format(serverDelay))
    
    for x in range(repeatCount):
        time.sleep(1)
        child.sendline('coap get {0} 5683 /ver'.format(addr))
        child.expect('0\.1')
        print('Success: {0}'.format(child.after))
        
        child.sendline('coap info')
        child.expect('open requests.*\n')
        print(child.after)

    print('Wait to check open requests')
    time.sleep(5)
    child.sendline('coap info')
    child.expect('open requests.*\n')
    print(child.after)
    child.close()

def runToobig(child, addr):
    print('Test: GET /toobig')

    child.sendline('coap get {0} 5683 /toobig'.format(addr))
    child.expect(pexpect.TIMEOUT, timeout=5)
    print('Success: <timeout>'.format(child.after))
    child.close()

def runToomany(child, addr):
    print('Test: Too many open requests to send another')

    child.sendline('coap get {0} 5683 /ignore'.format(addr))
    child.expect('sending msg')
    print('Sent 1')

    child.sendline('coap get {0} 5683 /ignore'.format(addr))
    child.expect('sending msg')
    print('Sent 2')

    child.sendline('coap get {0} 5683 /ignore'.format(addr))
    child.expect('send failed')
    print('Sent 3; failed as expected')
    child.close()

if __name__ == "__main__":
    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='addr')
    parser.add_option('-d', type='int', dest='serverDelay', default=0)
    parser.add_option('-r', type='int', dest='repeatCount', default=1)
    parser.add_option('-t', type='string', dest='testName')
    parser.add_option('-x', type='string', dest='execDir', default='')

    (options, args) = parser.parse_args()

    # Must run RIOT client from gcoap example directory
    if options.execDir:
        curdir = os.getcwd()
        os.chdir(options.execDir)
    try:
        main(options.addr, options.testName, options.serverDelay, options.repeatCount)
    finally:
        if options.execDir:
            os.chdir(curdir) 
