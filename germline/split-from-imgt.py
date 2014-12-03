#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys


IMGT_LICENSE = '''
   # To use the IMGT germline databases (IMGT/GENE-DB), you have to agree to IMGT license: 
   # academic research only, provided that it is referred to IMGT®,
   # and cited as "IMGT®, the international ImMunoGeneTics information system® 
   # http://www.imgt.org (founder and director: Marie-Paule Lefranc, Montpellier, France). 
   # Lefranc, M.-P., IMGT®, the international ImMunoGeneTics database,
   # Nucl. Acids Res., 29, 207-209 (2001). PMID: 11125093
'''

print IMGT_LICENSE


# Parse lines in IMGT/GENE-DB such as:
# >M12949|TRGV1*01|Homo sapiens|ORF|...

open_files = {}
current_file = None

def verbose_open_w(name):
    print " ==> %s" % name
    return open(name, 'w')

# Create isolated files for some sequences
SPECIAL_SEQUENCES = [
]

for l in sys.stdin:

    if ">" in l:
        current_file = None
        current_special = None

        if "Homo sapiens" in l and ("V-REGION" in l or "D-REGION" in l or "J-REGION" in l):
            seq = l.split('|')[1]
            system = seq[:4]

            if system.startswith('IG') or system.startswith('TR'):

                if system in open_files:
                    current_file = open_files[system]
                else:
                    name = '%s.fa' % system
                    current_file = verbose_open_w(name)
                    open_files[system] = current_file

            if seq in SPECIAL_SEQUENCES:
                name = '%s.fa' % seq.replace('*', '-')
                current_special = verbose_open_w(name)


    if current_file:
            current_file.write(l)

    if current_special:
            current_special.write(l)

