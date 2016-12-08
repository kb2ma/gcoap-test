#!/usr/bin/env python

'''Uses libcoap example client to query gcoap server. Assumes gcoap server
exists.

Options:

-a <addr>  -- Address of server
-r <count> -- Number of times to repeat query, with a 3 second wait between
              response and next request.

Example:

# Uses address for fixed tap address created by riot2gcoaptest.py
$ PATH=${PATH}:/home/kbee/dev/libcoap/repo/examples ./libcoap2riot.py -a fe80::bbbb:2 -r 30
'''
from __future__ import print_function
import time
import re
import pexpect

def main(addr, repeatCount):
    print('Test: libcoap client GET /cli/stats from RIOT gcoap server')
    addrSuffix = '%tap0' if addr[:4] == 'fe80' else ''
    
    for x in range(repeatCount):
        time.sleep(3)
        cmdText = 'coap-client -N -m get -U -T 5a coap://[{0}{1}]/cli/stats'
        child   = pexpect.spawn(cmdText.format(addr, addrSuffix))
        pattern = '(v.*\n)(\d+\r\n)'
        child.expect(pattern)
        # Rerun regex to extract and print second group, the response payload.
        match = re.search(pattern, child.after)
        print('Success: {0}'.format(match.group(2)))

if __name__ == "__main__":
    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='addr')
    parser.add_option('-r', type='int', dest='repeatCount', default=1)

    (options, args) = parser.parse_args()

    main(options.addr, options.repeatCount)
