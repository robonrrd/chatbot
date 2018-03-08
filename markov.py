"""Markov abstracts the markov chain and backing database."""

# Data format:
#

# self.db is a dict mapping bigrams to a list of two-item lists.  A
# bigram is a pair of words, represented by a list of two strings
# (single words). The two-item lists consist of an integer and a string (a
# word).  The number is the number of times this trigram (the indexing
# bigram plus the word) have been read.
#
# Example:
# The input strings:
#   one two three
#   one two three
#   one two buckle
#   one two many
#   one two many
#   one two many
# would result in:
#  { "one,two" : [ [ 2, "three"] , [ 1, "buckle"] , [ 3, "many"] ] }
#  { "two,three" : [ [ 2, "\n] ] }
#  { "two,buckle" : [ [ 1, "\n] ] }
#  { "two,many" : [ [ 3, "\n] ] }

import logging
import math
import os
import random
import re

from threading import RLock

from colortext import *

try:
    # use cPickle when using python2 for better performance
    import cPickle as pickle
except ImportError:
    import pickle


class MarkovChain(object):
    def __init__(self, dbFilePath=None):
        #self.db = {("","") : []}
        self.db = {}
        self.db_lock = RLock()

        self.dbFilePath = dbFilePath
        if not dbFilePath:
            self.dbFilePath = os.path.join(os.path.dirname(__file__),
                                           "markovdb")

        with self.db_lock:
            try:
                with open(self.dbFilePath, 'rb') as dbfile:
                    self.db = pickle.load(dbfile)
            except IOError:
                logging.warn(WARNING +
                             ("Unable to read database file '%s': "
                              "Using empty database" % self.dbFilePath))
            except ValueError:
                logging.warn(WARNING +
                             ("Database '%s' corrupt or unreadable: "
                              "Using empty database" % self.dbFilePath))

    def parseLineIntoSentences(self, line):
        line = re.sub('[\'/,@#<>!@#^&*]', '', line.lower())
        return line.split('.!?()')

    def bigrams(self, sentence):
        inp = sentence.split(' ')
        output = []
        for i in range(len(inp)-1):
            output.append((inp[i], inp[i+1]))
        return output

    def addLine(self, line):
        sentences = self.parseLineIntoSentences(line)
        for ss in sentences:
            bg = self.bigrams(ss)
            for ii in range(0,len(bg)-1):
                # if we're the last bigram, we map to EOL
                new_value = ""
                if ii == len(bg)-1:
                    new_value = "\n"
                else:
                    new_value = bg[ii+1][1]

                with self.db_lock:
                    if self.db.get(bg[ii]) == None:
                        # we've never seen this bigram
                        self.db[bg[ii]] = [[1, new_value]]
                    else:
                        # seen it:
                        val = self.db[bg[ii]]
                        found = False
                        for rr in val:
                            if rr[1] == new_value:
                                rr[0] = rr[0] + 1
                                found = True
                                break
                        if not found:
                            val.append([1, bg[ii+1][1]])

                        self.db[bg[ii]] = val

    def saveDatabase(self):
        with self.db_lock:
            try:
                with open(self.dbFilePath, 'wb') as dbfile:
                    pickle.dump(self.db, dbfile)
                return True
            except IOError:
                logging.error(ERROR +
                              ("Failed to write markov db to '%s'\n" %
                               self.dbFilePath))
                return False

    def respond(self, bigram):
        include_bigram = False
        # If no bigram given as a seed, pick a random one.
        if not bigram:
            with self.db_lock:
                bigram = random.choice(self.db.keys())
                include_bigram = True
                logging.info(BLUE + "Picking " + str(bigram) + " as seed")

        # Must be a bigram
        if len(bigram) != 2:
            logging.error(ERROR +
                          ("Invalid bigram %s passed as seed" % str(bigram)))
            return ""

        response = [""]
        self._respondHelper(bigram, response)
        if include_bigram:
            response[0] = bigram[0] + " " + bigram[1] + " " + response[0]
        return response[0]

    def _respondHelper(self, bigram, response):
        # does it exist in our cache?
        with self.db_lock:
            if self.db.get(bigram) == None:
                # end?
                return
                #  TODO: pick a random bigram?
                # which = random.random() * len(self.cache)
                # ii = 0
                # for k, v in self.cache.iteritems():
                #   if ii == which:
                #     bg = k
                #     break
                #   ii = ii + 1

            # pick a random response
            values = self.db[bigram]
            
            # find sum of all response appearance counts
            totalAppear = 0
            for v in values:
                totalAppear = totalAppear + v[0]

            which = int(math.floor(random.random()*totalAppear) + 1)
            ii = 0
            for v in values:
                ii = ii + v[0]
                if ii >= which:
                    if response[0] == "":
                        response[0] = v[1]
                    else:
                        response[0] = response[0] + " " + v[1]
                    newbigram = (bigram[1], v[1])
                    self._respondHelper(newbigram, response)
                    return
