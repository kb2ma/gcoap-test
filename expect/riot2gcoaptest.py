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
              response and next request.
-x <dir>   -- Directory in which to execute the script; must be location of
              RIOT gcoap example app.

Example:

$ sudo ip tuntap add tap0 mode tap user kbee
$ sudo ip link set tap0 up
$ sudo ip address add fe80::bbbb:1/64 dev tap0

$ ./riot2gcoaptest.py -a fe80::bbbb:1 -d 1 -r 50 -x /home/kbee/dev/riot/repo/examples/gcoap
'''
from __future__ import print_function
import time
import os
import pexpect

def main(addr, serverDelay, repeatCount):

    print('Test: RIOT client GET /ver from gcoaptest server')
    child = pexpect.spawn('make term')
    child.expect('gcoap example app')

    ifType = 'tap' if addr[:4] == 'fe80' else 'tun'
    if ifType == 'tap':
        child.sendline('ifconfig 6 add unicast fe80::bbbb:2/64')
        child.expect('success:')
    
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

if __name__ == "__main__":
    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='addr')
    parser.add_option('-d', type='int', dest='serverDelay', default=0)
    parser.add_option('-x', type='string', dest='execDir', default='')
    parser.add_option('-r', type='int', dest='repeatCount', default=1)

    (options, args) = parser.parse_args()

    # Must run RIOT client from gcoap example directory
    if options.execDir:
        curdir = os.getcwd()
        os.chdir(options.execDir)
    try:
        main(options.addr, options.serverDelay, options.repeatCount)
    finally:
        if options.execDir:
            os.chdir(curdir) 
