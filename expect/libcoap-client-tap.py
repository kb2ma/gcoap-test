#!/usr/bin/env python

'''Uses libcoap example client to query gcoap server. Assumes gcoap server exists.

Example:

./libcoap-client.py -a <address>
'''
from __future__ import print_function
import time
import pexpect

def main(addr, repeatCount):
    dir  = '/home/kbee/dev/libcoap/repo/examples'

    print('Get /cli/stats')
    for x in range(repeatCount):
        time.sleep(3)
        child = pexpect.spawn('{0}/coap-client -N -m get -U -T 5a coap://[{1}%tap0]/cli/stats'.format(dir, addr))
        child.expect('.*\n')
        print('Success: {0}'.format(child.after))

if __name__ == "__main__":
    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='addr')
    parser.add_option('-r', type='int', dest='repeatCount', default=1)

    (options, args) = parser.parse_args()

    main(options.addr, options.repeatCount)
