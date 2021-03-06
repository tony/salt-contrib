#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Get some grains information that is only available in Amazon AWS

Author: Erik Günther, J C Lawrence <claw@kanga.nu>, Mark McGuire

"""
import logging
import httplib
import socket
import json

# Set up logging
LOG = logging.getLogger(__name__)


def _call_aws(url):
    """
    Call AWS via httplib. Require correct path.
    Host: 169.254.169.254

    """
    conn = httplib.HTTPConnection("169.254.169.254", 80, timeout=1)
    conn.request('GET', url)
    response = conn.getresponse()
    if response.status == 200:
        return response.read()


def _get_ec2_hostinfo(path=""):
    """
    Recursive function that walks the EC2 metadata available to each minion.
    :param path: URI fragment to append to /latest/meta-data/

    Returns a nested dictionary containing all the EC2 metadata. All keys
    are converted from dash case to snake case.
    """
    resp = _call_aws("/latest/meta-data/%s" % path).strip()
    d = {}
    for line in resp.split("\n"):
        if line[-1] != "/":
            call_response = _call_aws("/latest/meta-data/%s" % (path + line))
            # avoid setting empty grain
            if call_response == '':
                d[line] = None
            elif call_response is not None:
                line = _dash_to_snake_case(line)
                try:
                    data = json.loads(call_response)
                    if isinstance(data, dict):
                        data = _snake_caseify_dict(data)
                    d[line] = data
                except ValueError:
                    d[line] = call_response
            else:
                return line
        else:
            d[_dash_to_snake_case(line[:-1])] = _get_ec2_hostinfo(path + line)
    return d


def _camel_to_snake_case(s):
    return s[0].lower() + "".join((("_" + x.lower()) if x.isupper() else x) for x in s[1:])


def _dash_to_snake_case(s):
    return s.replace("-", "_")


def _snake_caseify_dict(d):
    nd = {}
    for k, v in d.items():
        nd[_camel_to_snake_case(k)] = v
    return nd


def _get_ec2_additional():
    """
    Recursive call in _get_ec2_hostinfo() does not retrieve some of
    the hosts information like region, availability zone or
    architecture.

    """
    response = _call_aws("/latest/dynamic/instance-identity/document")
    # _call_aws returns None for all non '200' reponses,
    # catching that here would rule out AWS resource
    if response:
        data = json.loads(response)
        return _snake_caseify_dict(data)
    else:
       raise httplib.BadStatusLine("Could not read EC2 metadata")


def ec2_info():
    """
    Collect all ec2 grains into the 'ec2' key.
    """
    try:
        grains = _get_ec2_additional()
        grains.update(_get_ec2_hostinfo())
        return {'ec2' : grains}

    except httplib.BadStatusLine, error:
        LOG.debug(error)
        return {}

    except socket.timeout, serr:
        LOG.info("Could not read EC2 data (timeout): %s" % (serr))
        return {}

    except socket.error, serr:
        LOG.info("Could not read EC2 data (error): %s" % (serr))
        return {}

    except IOError, serr:
        LOG.info("Could not read EC2 data (IOError): %s" % (serr))
        return {}

if __name__ == "__main__":
    print ec2_info()
