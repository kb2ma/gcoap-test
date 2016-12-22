#!/usr/bin/env python

'''Uses libcoap example client to query gcoap server. Assumes gcoap server
exists.

Options:

-a <addr>  -- Address of server
-r <count> -- Number of times to repeat query, with a 3 second wait between
              response and next request.
-t <test> --- Name of test to run. Options:
                nopath -- GET request for /bogus (returns 4.04)
                repeat-get -- GET request for /cli/stats
                toobig -- POSTs to a bogus resource (/abcd)

Example:

# Assumes gcoap server exists.
# Uses address for fixed tap address created by riot2gcoaptest.py
$ PATH=${PATH}:/home/kbee/dev/libcoap/repo/examples ./libcoap2riot.py -a fe80::bbbb:2 -t repeat-get -r 30
'''
from __future__ import print_function
import time
import re
import pexpect

def main(addr, testName, repeatCount):
    if testName == 'repeat-get':
        runRepeatGet(addr, repeatCount)
    elif testName == 'toobig':
        runToobig(addr)
    elif testName == 'nopath':
        runBogus(addr)
    else:
        print('Unexpected test name: {0}'.format(testName))

def runRepeatGet(addr, repeatCount):
    '''Repeats a simple GET request
    '''
    print('Test: libcoap client GET /cli/stats from RIOT gcoap server')
    addrSuffix = '%tap0' if addr[:4] == 'fe80' else ''
    
    for x in range(repeatCount):
        time.sleep(3)
        cmdText = 'coap-client -N -m get -U -T 5a coap://[{0}{1}]/cli/stats'
        child   = pexpect.spawn(cmdText.format(addr, addrSuffix))
        pattern = '(v.*\n)(\d+\r\n)'
        child.expect(pattern, timeout=5)
        # Rerun regex to extract and print second group, the response payload.
        match = re.search(pattern, child.after)
        print('Success: {0}'.format(match.group(2)))
        child.close()

def runToobig(addr):
    '''POSTs a request that exceeds the max input size in gcoap.
    '''
    print('Test: libcoap client POST large payload to RIOT gcoap server')
    addrSuffix = '%tap0' if addr[:4] == 'fe80' else ''
    
    cmdText = 'coap-client -N -m post -U -T 5a coap://[{0}{1}]/abcd -f toobig.txt'
    child   = pexpect.spawn(cmdText.format(addr, addrSuffix))
    child.expect(pexpect.TIMEOUT, timeout=5)
    print('Success: <timeout>'.format(child.after))
    child.close()

def runBogus(addr):
    '''GETs a request that gcoap does not understand.
    '''
    print('Test: libcoap client GET bogus path from RIOT gcoap server')
    addrSuffix = '%tap0' if addr[:4] == 'fe80' else ''
    
    cmdText = 'coap-client -N -m get -U -T 5a coap://[{0}{1}]/bogus'
    child   = pexpect.spawn(cmdText.format(addr, addrSuffix))
    child.expect('4\.04\r\n')
    print('Success: {0}'.format(child.after))
    child.close()

if __name__ == "__main__":
    from optparse import OptionParser

    # read command line
    parser = OptionParser()
    parser.add_option('-a', type='string', dest='addr')
    parser.add_option('-r', type='int', dest='repeatCount', default=1)
    parser.add_option('-t', type='string', dest='testName')

    (options, args) = parser.parse_args()

    main(options.addr, options.testName, options.repeatCount)
