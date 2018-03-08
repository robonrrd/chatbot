#!/usr/bin/env python
from colortext import *
import logging
import argparse
import base_chatbot
import string
import random
import time
import re
import pickle
import sys
import time
import os
import shutil
from slackclient import SlackClient


class SlackBot(base_chatbot.Bot):
        
    def __init__(self, args):
        super(SlackBot, self).__init__(args)

        # Slack specific variables and settings
        self.slackClient = None

        self.OAUTH_ACCESS_TOKEN = "YOUR_TOKEN_HERE"
        self.BOT_USER_OAUTH_ACCESS_TOKEN = "YOUR_USER_TOKEN_HERE"

        # starterbot's user ID in Slack: value is assigned after the bot starts up
        self.USERID = None
        self.BOT_NAME = "chatbot"

        # constants
        self.RTM_READ_DELAY = 0.5 # 0.5 second delay between reading from RTM

        self.USERMAP = {}
        self.CHANNELMAP = {}


    # Join the Slack network
    def joinSlack(self):

        # instantiate Slack client
        self.SLACKCLIENT = SlackClient(self.BOT_USER_OAUTH_ACCESS_TOKEN)

        #if self.SLACKCLIENT.rtm_connect(with_team_state=False):
        if self.SLACKCLIENT.rtm_connect():
            print("Slackbot connected and running")
            # Read bot's user ID by calling Web API method `auth.test`
            self.USERID = self.SLACKCLIENT.api_call("auth.test")["user_id"]
            return
        else:
            print("Connection failed. Exception traceback printed above.")
            exit(1)


    def nickFromUserId(self, user_id):
        if user_id in self.USERMAP:
            return self.USERMAP[user_id]
        else:
            result = self.SLACKCLIENT.api_call("users.info", user=user_id)
            if result["ok"] is False:
                print "Could not detemine real name for ", user_id
                return None

            name = result["user"]["name"]
            self.USERMAP[user_id] = name
            return name


    def channelFromChannelId(self, channel_id):
        if channel_id in self.CHANNELMAP:
            return self.CHANNELMAP[channel_id]
        else:
            result = self.SLACKCLIENT.api_call("channels.info", channel=channel_id)
            if result["ok"] is False:
                print "Could not detemine real channel name for ", channel_id
                return None

            channel = result["channel"]["name"]
            self.CHANNELMAP[channel_id] = channel
            return channel


    def amDirectlyAddressed(self, text):
        MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
        matches = re.search(MENTION_REGEX, text)

        # the first group contains the username, the second group contains the remaining message
        if matches:
            nick = self.nickFromUserId(matches.group(1))
            return (nick, matches.group(2).strip())
        else:
            return (None, None)
        

    def resolveUserIds(self, text):
        MENTION_REGEX = "(.*)<@(|[WU].+?)>(.*)"
        matches = re.search(MENTION_REGEX, text)
        while matches:
            nick = self.nickFromUserId(matches.group(2))
            text = matches.group(1)+nick+matches.group(3)
            matches = re.search(MENTION_REGEX, text)
        return text


    def parseMessage(self, event):
        speaker = self.nickFromUserId(event["user"])
        if speaker is None:
            print "Unknown user; ignoring"
            return
        
        # Unparsed body of the message
        try:
            sentences = self.splitTextIntoSentences(str(event["text"]))
        except:
            return

        for line in sentences:
            if self.containsURL(line):
                continue

            # Start creating a msg dict to pass to the markov chain
            msg = {}
            msg["p_reply"] = self.p_reply

            # Detect and trim off any leading direct adresses (i.e. "@foo, how are you?")
            direct, txt = self.amDirectlyAddressed(line)
            if direct is not None:
                text = txt
                # If we are directly addressed, then probability of our reponse should be 1
                if direct == self.BOT_NAME:
                    msg["p_reply"] = 1.0
                else:
                    text = line
            else:
                text = line

            text = self.resolveUserIds(text)
            text = self.preprocessText(text)
            if len(text) == 0:
                continue

            print "Heard:",text

            msg["text"] = text
            msg["speaker"] = speaker
            msg["channel"] = self.channelFromChannelId(event["channel"])

            reply = self.possiblyReply(msg)
            if reply is not None:
                print "..Reply:", reply
                # Sends the response back to the channel
                self.SLACKCLIENT.api_call("chat.postMessage",
                                          channel=msg["channel"],
                                          text=reply)
            else:
                print "..No reply"

            self.addPhrase(msg["text"])


    def parseEvents(self, events):
        """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
        """
        for event in events:
            if event["type"] == "message" and not "subtype" in event:
                self.parseMessage(event)


    def run(self):
        super(SlackBot, self).run()
        self.joinSlack()

        while True:
            input = self.SLACKCLIENT.rtm_read()
            if len(input) == 0:
                continue
            self.parseEvents(input)
            time.sleep(self.RTM_READ_DELAY)


    
#####

if __name__ == "__main__":

    PARSER = argparse.ArgumentParser(description='A snarky slack bot.')
    PARSER.add_argument("--nick", help="The bot's nickname", default="chatbot")
    PARSER.add_argument("--realname", help="The bot's real name", default="Python chatbot")
    PARSER.add_argument("--channels", help="The list of channels to join", default="#testing")
    PARSER.add_argument("--ignore", help="The optional list of nicks to ignore", default="")
    PARSER.add_argument("--owners", help="The list of owner nicks", default="")
    PARSER.add_argument("--save_period", help="How often (# of changes) to save databases", default=100)
    PARSER.add_argument("--seendb", help="Path to seendb", default="./seendb.pkl")
    PARSER.add_argument("--markovdb", help="Path to markovdb", default="./chatbotdb")
    PARSER.add_argument("--p", help="Probability (0..1) to reply", default="0.1")
    PARSER.add_argument("--readonly", help="The bot will not learn from other users, only reply to them", dest='readonly', action='store_true')
    PARSER.set_defaults(readonly=False)

    bot = SlackBot(PARSER.parse_args())
    bot.run()
    bot.quit()

