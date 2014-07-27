#!/usr/bin/env python
import itertools
import re
import sys
import os.path


if __name__ == '__main__':
    out = sys.stdout
    rfc_file = open(os.path.join(os.path.dirname(__file__), 'rfc2812.txt'))
    rfc = iter(rfc_file)
    numeric_regex = re.compile(r'^       (\d{3})    ([A-Z_]+)$')
    # Skip until the numeric replies section
    itertools.takewhile(lambda l: not l.startswith("5.1 Command responses"), rfc)
    out.write('# Generated by scripts/extract_rfc_numerics.py\n')
    out.write('NUMERIC_REPLIES = {\n')
    for line in rfc:
        match = numeric_regex.match(line)
        if match is not None:
            out.write("    '{}': '{}',\n".format(*match.group(1, 2)))
    out.write('}\n')