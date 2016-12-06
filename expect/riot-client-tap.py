#!/usr/bin/env python

'''Creates RIOT example app, and uses it to query libcoap server for /time.

Example:

./riot-client.py -a <address>
'''
from __future__ import print_function
import time
import os
import pexpect

def main(addr, repeatCount):
    dir  = '/home/kbee/dev/riot/repo/examples/gcoap'
    os.chdir(dir)
    
    print('Get gcoap-test-server /ver')
    #print('Get libcoap example /time')
    child = pexpect.spawn('make term')
    child.expect('gcoap example app')
    #child.sendline('ifconfig')
    #child.expect('inet6 addr.*\n')
    print(child.after)
    
    for x in range(repeatCount):
        time.sleep(1)
        #child.sendline('coap get {0} 5683 /time'.format(addr))
        #child.expect('Dec.*\n')
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
    parser.add_option('-r', type='int', dest='repeatCount', default=1)

    (options, args) = parser.parse_args()

    curdir = os.getcwd()
    try:
        main(options.addr, options.repeatCount)
    finally:
        os.chdir(curdir)
