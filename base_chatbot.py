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
import json


from threading import Timer, RLock

import logger
import markov
from colortext import *

# Required 'msg' dict keys
#  text
#  speaker
#  p_reply


class Bot(object):
    def __init__(self):
        self.NICK = None
        self.REALNAME = None
        self.OWNERS = None
        self.READONLY = False

        # Caches of status
        self.seen = {} # lists of who said what when
        # Set up a lock for the seen db
        self.seendb_lock = RLock()
        self.SEENDB = None

        # Markov chain settings
        self.p_reply = 0.1
        self.MARKOVDB = None

        # Regular db saves
        self.SAVE_PERIOD = 100
        self.save_count = 0

        # Commands
        self.commands = {}

        # signal handling
        signal.signal(signal.SIGINT, self.signalHandler)
        signal.signal(signal.SIGTERM, self.signalHandler)
        signal.signal(signal.SIGQUIT, self.signalHandler)


    def initialize(self, configFile):
        with open(configFile) as json_data_file:
            args = json.load(json_data_file)
        
        self.NICK = args.get("nick", "chatbot")
        self.REALNAME = args.get("realname", "Arthur J. Chatbot")
        if "owners" in args:
            self.OWNERS = args.get("owners", [])
        else:
            self.OWNERS = [None]
        self.READONLY = args.get("readonly", False)
        self.SEENDB = args.get("seendb", "seendb")

        # Markov chain settings
        pstr = args.get("p_reply", "0.1")
        p = float(pstr)
        if p < 0:
            p = 0
        elif p > 1:
            p = 1
        self.p_reply = p
        self.MARKOVDB = args.get("markovdb", "chatbot_markovdb")

        # Regular db saves
        self.SAVE_PERIOD = int(args.get("save_period", 100))
        self.save_count = 0


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
        if random.random() > msg["p_reply"]:
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
        print "Saving Markov chain database"
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


    def recordSeen(self, name, text):
        with self.seendb_lock:
            self.seen[name] = [time.time(), text]


    @staticmethod
    def elapsedTime(ss):
        reply = ""
        startss = ss
        if ss > 31557600:
            years = ss // 31557600
            reply = reply + ("%g years " % years)
            ss = ss - years*31557600

        if ss > 2678400: # 31 days
            months = ss // 2678400
            reply = reply + ("%g months " % months)
            ss = ss - months*2678400

        if ss > 604800:
            weeks = ss // 604800
            reply = reply + ("%g weeks " % weeks)
            ss = ss - weeks*604800

        if ss > 86400:
            days = ss // 86400
            reply = reply + ("%g days " % days)
            ss = ss - days*86400

        if ss > 3600:
            hours = ss // 3600
            reply = reply + ("%g hours " % hours)
            ss = ss - hours*3600

        if ss > 60:
            minutes = ss // 60
            reply = reply + ("%g minutes " % minutes)
            ss = ss - minutes*60


    def hasBeenSeen(self, name):
        with self.seendb_lock:
            if name in self.seen:
                last_seen = self.seen[name][0] # in seconds since epoch
                since = self.elapsedTime(time.time() - last_seen)
                return (True, self.seen[name], since)
            else:
                return (False, None, None)


    def loadSeenDatabse(self):
        with self.seendb_lock:
            try:
                with open(self.SEENDB, 'rb') as seendb:
                    self.seen = pickle.load(seendb)
            except IOError:
                logging.error(WARNING +
                              ("Unable to open seen db '%s' for reading" %
                               self.SEENDB))

    def saveSeenDatabase(self):
        print "Saving 'seen' database"
        with self.seendb_lock:
            try:
                with open(self.SEENDB, 'wb') as seendb:
                    pickle.dump(self.seen, seendb)
            except IOError:
                logging.error(ERROR +
                              ("Unable to open seed db '%s' for writing" %
                               self.SEENDB))


    def registerCommands(self):
        return


    def handleCommand(self, text):
        words = self.preprocessText(text).split()
        try:
            return self.commands[words[0]](' '.join(words[1:]))
        except:
            print "No function called '"+words[0]+"' found"
            return False



    def run(self):
        self.loadMarkovChain()
        self.loadSeenDatabse()
        # do nothing

        
    def quit(self):
        self.saveMarkovDatabase()
        self.saveSeenDatabase()
        sys.exit(0)
