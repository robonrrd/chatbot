#!/usr/bin/env python
from colortext import *
import logging
import base_chatbot
import irc
import string
import random
import time
import re
import pickle
import sys
import time
import os
import shutil

# Added msg fields:
#  speaking_to

class IRCBot(base_chatbot.Bot):
        
    def __init__(self, args):
        super(IRCBot, self).__init__(args)

        # IRC specific variables and settings
        self.IDENT='pybot'
        self.irc = None
        self.HOST = None
        self.PORT = None
        self.CHANNELINIT = None
        self.IGNORE = None

    def initialize(self, configFile):
        super(IRCBot,self).initialize(configFile)

        # IRC specific arguments
        with open(configFile) as json_data_file:
            args = json.load(json_data_file)

        self.HOST = args.get("irc_host", "irc.perl.org")
        self.PORT = int(args.get("irc_port", 6667))
        self.CHANNELINIT = args.get("irc_channels", ["#testing"])
        self.IGNORE = args.get("irc_ignore", [])


    @staticmethod
    def logChannel(speaker, msg):
        logging.debug(CYAN + speaker + PLAIN + " : " + BLUE + msg)

        
    # Join the IRC network
    def joinIRC(self):
        self.irc = irc.Irc(self.HOST, self.PORT, self.NICK, self.IDENT,
                           self.REALNAME)

        # Join the initial channels
        for chan in self.CHANNELINIT:
            self.irc.join(chan)
            if not self.irc.isop(self.NICK, chan):
                op_reqs = [
                    'Op me!', 'Yo, ops?',
                    'What does a kobold have to do to get ops around here?']
                which = random.randint(0, len(op_reqs)-1)
                self.irc.privmsg(chan, op_reqs[which])


    # private message from user
    # :itsjoe!~joe@example.com PRIVMSG gravy :foo
    # public channel message
    # :itsjoe!~joe@example.com PRIVMSG #test :foo
    # TODO: take 'words' instead to simplify parsing.
    def parsePrivMessage(self, line):
        # ignore any line with a url in it
        m = re.search('^:(\w*)!.(\w*)@(\S*)\s(\S*)\s(\S*) :(.*)', line)
        if m is None:
            return

        # Ignore anything that isn't a PRIVMSG
        if m.group(4)  != 'PRIVMSG':
            return

        # pull out the data we care about
        speaker =  m.group(1)                      # the nick of who's speaking
        speaker_email = m.group(2)+'@'+m.group(3)  # e.g. foo@bar.com
        speaking_to = m.group(5)                   # could be self.NICK or a channel
        text = m.group(6)
        text = self.preprocessText(text)


        if speaking_to[0] == "#":
            nick = speaker.lower()
            # Lock here to avoid writing to the seen database while pickling it.
            with self.seendb_lock:
                self.seen[nick] = [speaking_to, time.time(), string.strip(text)]

        if speaker in self.IGNORE:
            return

        msg = {
            "text"        : text,
            "speaker"     : speaker,
            "speaking_to" : speaking_to,
            "p_reply"     : self.p_reply
        }

        if speaking_to == self.NICK and speaker in self.OWNERS:
            self.parsePrivateMessageFromOwner(msg)
        elif msg["speaking_to"] != self.NICK:
            self.parsePublicMessage(msg)


    def parsePrivateMessageFromOwner(self, msg):
        # The owner can issue commands to the bot, via strictly constructed
        # private messages
        words = msg["text"].split()

        logging.info("Received private message: '" + string.strip(msg["text"]) + "'")

        # simple testing
        if len(words) == 1 and words[0] == 'ping':
            self.logChannel(msg["speaker"], GREEN + 'pong')
            self.irc.privmsg(msg["speaker"], 'pong')
            return

        # set internal variables
        elif len(words) == 3 and words[0] == "set":
            # set reply probability
            if words[1] == "p_reply":
                self.logChannel(msg["speaker"],
                                GREEN + "SET P_REPLY " + words[2])
                self.p_reply = float(words[2])
                self.irc.privmsg(msg["speaker"], str(self.p_reply))
            else:
                reply = self.dunno(msg)
                self.irc.privmsg(msg["speaking_to"], reply)
            return

        elif len(words) == 2 and words[0] == "get":
            # set reply probability
            if words[1] == "p_reply":
                self.logChannel(msg["speaker"],
                                GREEN + "GET P_REPLY " + str(self.p_reply))
                self.irc.privmsg(msg["speaker"], str(self.p_reply))
            else:
                reply = self.dunno(msg)
                self.irc.privmsg(msg["speaking_to"], reply)
            return

        # leave a channel
        elif len(words) == 2 and (words[0] == 'leave' or words[0] == 'part'):
            self.logChannel(msg["speaker"], PURPLE + "PART " + words[1])
            self.irc.part(words[1])
            return

        # join a channel
        elif len(words) == 2 and words[0] == 'join':
            channel = str(words[1])
            if channel[0] != '#':
                channel = '#' + channel

            self.logChannel(msg["speaker"], PURPLE + "JOIN " + channel)
            self.irc.send('JOIN ' + channel + '\r\n')
            return

        # quit
        elif len(words) == 1 and (words[0] == 'quit' or words[0] == 'exit'):
            self.logChannel(msg["speaker"], RED + "QUIT")
            self.quit()

        # if we've hit no special commands, parse this message like it was public
        self.parsePublicMessage(msg)


    def parsePublicMessage(self, msg):
        # add the spoken phrase to the log
        self.logChannel(msg["speaker"], msg["text"])

        # If a user has issued a command, don't do anything else.
        #if self.handleCommands(msg):
        #    return

        reply = self.possiblyReply(msg)

        if reply is None:
            self.logChannel(self.NICK, "EMPTY_REPLY")
        else:
            self.irc.privmsg(msg["speaking_to"], reply)
            self.logChannel(self.NICK, reply)
        self.addPhrase(msg["text"])


    # information about MODE changes (ops, etc.) in channels
    def parseModeMessage(self, words):
        # right now, we only care about ops
        if len(words) < 5:
            return
        channel = words[2]
        action = words[3]
        on_who = words[4]

        if action == "+o":
            self.irc.addop(channel, on_who)
            return

        if action == "-o":
            self.irc.rmop(channel, on_who)
            return

        
    # update who list when users part or join.
    def handlePartJoin(self, words):
        m = re.search('^:(\w*)!', words[0])
        if m is None:
            return

        user = m.group(1)
        channel = words[2]

        if words[1] == 'PART':
            self.irc.rmwho(channel, user)
        elif words[1] == 'JOIN':
            # strip the leading ':'
            self.irc.addwho(channel[1:], user)


    def run(self):
        super(IRCBot, self).run()
        
        self.joinIRC()

        while True:
            try:
                recv = self.irc.readlines()
            except irc.ConnectionClosedException:
                logging.warning(WARNING + "Connection closed: Trying to reconnect in 5 seconds...")
                time.sleep(5)
                self.joinIRC()
                continue

            for line in recv:
                # strip whitespace and split into words
                words = string.rstrip(line)
                words = string.split(words)

                if words[0]=="PING":
                    self.irc.pong(words[1])
                elif words[1] == 'PRIVMSG':
                    self.parsePrivMessage(line)
                elif words[1] == "MODE":
                    self.parseModeMessage(words)
                elif words[1] == 'PART' or words[1] == 'JOIN':
                    self.handlePartJoin(words)

    
#####

if __name__ == "__main__":
    bot = IRCBot()

    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        print "Reading configuration from", config_file
        bot.initialize(config_file)

    bot.run()
    bot.quit()

