#!/usr/bin/env python

'''Creates RIOT example app, and uses it to GET /ver resource from gcoaptest
server. Also creates fixed IP address (fe80::bbbb:2/64) for use of example app
as server.

Before running, may need to manually create TAP interface and fixed IP address
for gcoaptest server. See example below.

Options:

-a <addr>  -- Address of server
-d <secs>  -- Server built-in response delay, in seconds
-r <count> -- Number of times to repeat query, with a 1 second wait between
              response and next request. For 'repeat-get' test only.
-t <test> --- Name of test to run. Options:
                repeat-get -- Repeats a sinple GET request
                toobig -- Requests a response that is too long to process
-x <dir>   -- Directory in which to execute the script; must be location of
              RIOT gcoap example app.

Example:

# tap
$ sudo ip tuntap add tap0 mode tap user kbee
$ sudo ip link set tap0 up
$ sudo ip address add fe80::bbbb:1/64 dev tap0

$ ./riot2gcoaptest.py -a fe80::bbbb:1 -t repeat-get -d 1 -r 50 -x /home/kbee/dev/riot/repo/examples/gcoap

# tun
$ cd /home/kbee/dev/riot/repo/dist/tools/tunslip
$ sudo ./tunslip6 -s ttyUSB0 -t tun0 bbbb::1/64
$ sudo ip -6 route add aaaa::/64 dev tun0

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
    print('Setup RIOT client')
    ifType = 'tap' if addr[:4] == 'fe80' else 'tun'

    if ifType == 'tap':
        child = pexpect.spawn('make term')
        child.expect('gcoap example app')
    else:
        child = pexpect.spawn('make term BOARD="samr21-xpro"')
        child.expect('Welcome to pyterm!')

    # configure network interfaces
    if ifType == 'tap':
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
