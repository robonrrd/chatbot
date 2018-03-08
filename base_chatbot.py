#!/usr/bin/env python
import logging
import pickle
import random
import re
import sys
import string
import signal
import time
import os
import shutil

from threading import Timer, RLock

import logger
import markov
from colortext import *

# Required 'msg' dict keys
#  text
#  speaker
#  p_reply


class Bot(object):
    def __init__(self, args):
        self.NICK = args.nick
        self.REALNAME = args.realname
        self.OWNERS = [string.strip(owner) for owner in args.owners.split(",")]
        self.READONLY = args.readonly

        # Caches of status
        self.seen = {} # lists of who said what when
        # Set up a lock for the seen db
        self.seendb_lock = RLock()
        self.SEENDB = args.seendb

        # Markov chain settings
        p = float(args.p)
        if p < 0:
            p = 0
        elif p > 1:
            p = 1
        self.p_reply = p
        self.MARKOVDB = args.markovdb

        # Regular db saves
        self.SAVE_PERIOD = float(args.save_period)
        self.save_count = 0

        # signal handling
        signal.signal(signal.SIGINT, self.signalHandler)
        signal.signal(signal.SIGTERM, self.signalHandler)
        signal.signal(signal.SIGQUIT, self.signalHandler)


    @staticmethod
    def splitTextIntoSentences(text):
         return text.split('.!?()')


    @staticmethod
    def containsURL(text):
        m = re.search('(http|ftp|https)://([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:/~+#-]*[\w@?^=%&/~+#-])?', text)
        return m is not None 


    @staticmethod
    def preprocessText(text):
        # remove all color codes
        text = re.sub('\x03(?:\d{1,2}(?:,\d{1,2})?)?', '', text)
        # remove non-alphanumeric characters
        text = re.sub(r'[^a-zA-Z0-9 ]+', '', text)
        return text


    @staticmethod
    def logMessage(speaker, msg):
        logging.debug(CYAN + speaker + PLAIN + " : " + BLUE + msg)

        
    def signalHandler(self, unused_signal, unused_frame):
        self.quit()


    def loadMarkovChain(self):
        # Open our Markov chain database
        self.mc = markov.MarkovChain(self.MARKOVDB)

        
    def possiblyReply(self, msg):
        words = self.preprocessText(msg["text"]).split()

        leading_words = ""
        seed = None

        # If we have enough words, generate a reply based on the message
        if len(words) >= 2:
            print (GREEN + "Trying to reply to '" + str(words) + "'" + ENDC)
            # Use a random bigram of the input message as a seed for the Markov chain
            max_index = min(6, len(words)-1)
            index = random.randint(1, max_index)
            seed = (words[index-1], words[index])
            leading_words = string.join(words[0:index+1])
        else:
            return None

        # If we have a reply, randomly determine if we reply with it
        if random.random() < msg["p_reply"]:
            return None

        # generate a response
        response = string.strip(self.mc.respond(seed))
        if len(leading_words) > 0:
            leading_words = leading_words + " "
        reply = leading_words + response
        #print string.join(seed) + " :: " + reply
        if len(response) == 0:
            return None
        else:
            return reply

    # Picks a random confused reply
    def dunno(self, msg):
        replies = ["I dunno, $who",
                   "I'm not following you."
                   "I'm not following you, $who."
                   "I don't understand.",
                   "You're confusing, $who."]

        which = random.randint(0, len(replies)-1)
        reply = re.sub("$who", msg["speaker"], replies[which])
        return reply

    @staticmethod
    def createBackup(source):
        if os.path.isfile(source):
            dst = source + ".bak"
            shutil.copyfile(source, dst)


            
    def saveMarkovDatabase(self):
        print "Saving database"
        self.createBackup(self.MARKOVDB)
        if self.READONLY:
            logging.info('Skipping markov db because we are read-only')
        else:
            self.mc.saveDatabase()

            
    def addPhrase(self, text):
        # add the phrase to the markov database if we're NOT in readonly mode
        if not self.READONLY:
            self.mc.addLine(text)
            self.save_count = self.save_count + 1
            if self.save_count == self.SAVE_PERIOD:
                self.saveMarkovDatabase()
                self.save_count = 0

                
    def run(self):
        self.loadMarkovChain()
        # do nothing

        
    def quit(self):
        self.saveMarkovDatabase()
        sys.exit(0)
