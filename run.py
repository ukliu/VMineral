#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division

import yaml
import json
import urllib2
import csv
import re

with open('./config', 'r') as config_yaml:
    config = yaml.load(config_yaml)

def update_output(docid, sentid, minerals, ages, locations, lemma):
    output.append({
        "docid": docid,
        "sentid": sentid,
        "minerals": minerals,
        "ages": ages,
        "locations": locations,
        "lemma": lemma
    })


def filter_output(item):
    if item['docid'] in acknowledgements.keys() and item['sentid'] < acknowledgements[item['docid']]:
        return True
    elif item['docid'] in refs.keys() and item['sentid'] < refs[item['docid']]:
        return True
    else:
        return False

# Format output before writing to CSV
def formatted(item):
    return {
        'docid': item['docid'],
        'sentid': item['sentid'],
        'minerals': ';'.join(item['minerals']),
        'ages': ';'.join(item['ages']),
        'locations': ';'.join(item['locations']),
        'lemma': item['lemma']
    }

def formatRef(ref, total):
    return {
        'docid': ref['id'].encode('utf-8'),
        'title': ref['title'].encode('utf-8'),
        'volume': ref['volume'].encode('utf-8'),
        'journal': ref['journal'].encode('utf-8'),
        'link': ';'.join([l['url'] for l in ref['link'] if l['type'] != 'filepath']).encode('utf-8'),
        'publisher': ref['publisher'].encode('utf-8'),
        'author': ';'.join([a['name'] for a in ref['author']]).encode('utf-8'),
        'pages': ref['pages'].encode('utf-8'),
        'number': ref['number'].encode('utf-8'),
        'identifier': ';'.join(i['id'] for i in ref['identifier']).encode('utf-8') if 'identifier' in ref else '',
        'impact': total / len(output)
    }

# Set up lists of terms we are interested in
minerallist = config['terms']
agelist = ['ma', 'age', 'dating', 'ka', 'ga', 'kyr', 'myr', 'year', 'geochronology', 'm.a.', 'k.a.', 'date']

# list of articles having age formation
articleID = []

# Titles of articles
titles = {}

# dictionary of age-containing article length before reference
# Keys are docids and values are sentids
## note refs has fewer items than articleID since articleID counts paper that has age information in reference part
refs = {}
acknowledgements = {}

output = []

# Open the input file
'''
0  -  docid
1  -  sentid
2  -  wordidx
3  -  words
4  -  poses
5  -  ners
6  -  lemmas
7  -  dep_paths
'''
with open('./input/sentences_nlp352.txt') as textlines:
    # Look for lines containing V mineral names, location, or age information
    for line in textlines.readlines():
        # Clean up the input
        sline = line.lower().split('\t')
        tL = re.sub('[{}"]\'', '', sline[6])
        tLL = re.sub(r',,,', ',;,', tL)
        # create an array of lemmas
        lemmas = tLL.split(',') #get rid of {}",,, in the raw texts

        # If there is an age term in the lemmas and we haven't accounted for this article yet, record it
        if len(list(set(agelist).intersection(set(lemmas)))) > 0 and sline[0] not in articleID:
            articleID.append(sline[0])

        # If there is a mention of references in the lemmas and we have seen this docid, update refs with the docid and sentid
        if ('reference' in lemmas or 'referenc' in lemmas or 'references' in lemmas) and sline[0] in articleID:
            refs.update({ sline[0]: int(sline[1]) })

        # If there is a mention of acknowledgements in the lemmas and we have seen this docid, update acknowledgements with the docid and sentid
        if ('acknowledgement' in lemmas or
            'acknowledgements' in lemmas or
            'acknowledge' in lemmas or
            'thank' in lemmas or
            'thanks' in lemmas) and sline[0] in articleID:
            acknowledgements.update({ sline[0]: int(sline[1]) })


        # record the title of all articles if this is the first sentence in an article
        if sline[1] == '1':
            titles.update({ sline[0]: tLL })

        # Clean up the ners
        ners = re.sub('[{}"]', '', sline[5]).split(',')

        # Get an array that is the interesction of minerals and lemmas
        minerals_found = list(set(minerallist).intersection(set(lemmas)))

        # Store ages found
        ages_found = []

        # Store location words found
        locations_found = []

        # Record all words tagged as 'LOCATION' in ners
        if 'location' in ners:
            for pos in [i for i,j in enumerate(ners) if j == 'location']:
                locations_found.append(lemmas[pos])

        # Find and record dates using the 'NUMBER' tag in ners
        if 'number' in ners:
            for pos in [i for i,j in enumerate(ners) if j == 'number']:
                if pos < len(lemmas) - 1 and lemmas[pos + 1] in agelist:
                    if pos > 0 and lemmas[pos - 1] == '±':
                        ages_found.append(lemmas[pos - 2] + lemmas[pos - 1] + lemmas[pos] + lemmas[pos + 1])
                    else:
                        ages_found.append(lemmas[pos] + lemmas[pos + 1])

        # If we found anything, record it
        if len(minerals_found) > 0 or len(ages_found) > 0 or len(locations_found) > 0:
            update_output(sline[0], int(sline[1]), minerals_found, ages_found, locations_found, ' '.join(lemmas))



# Filter the output in place
output[:] = [formatted(item) for item in output if filter_output(item)]

# Write the output to disk
with open('./output/results.csv', 'w') as out:
    writer = csv.DictWriter(out, fieldnames=['docid', 'sentid', 'minerals','ages', 'locations', 'lemma'])
    writer.writeheader()
    writer.writerows(output)

# Find unique documents
uniqueDocs = dict(set([(item['docid'], 0) for item in output]))
for item in output:
    uniqueDocs[item['docid']] += 1

outputRefs = []

# Find the metadata for each
for docid in uniqueDocs.keys():
    response = json.load(urllib2.urlopen('https://geodeepdive.org/api/v1/articles?id=' + docid))
    outputRefs.append(response['success']['data'][0])

outputRefs = [formatRef(ref, uniqueDocs[ref['id']]) for ref in outputRefs]


with open('./output/unique_docs.csv', 'w') as out2:
    writer = csv.DictWriter(out2, fieldnames=['docid', 'title', 'author', 'journal', 'publisher', 'identifier', 'pages', 'number', 'volume', 'link', 'impact'])
    writer.writeheader()
    writer.writerows(outputRefs)
