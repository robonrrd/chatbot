#!/usr/bin/env python
from colortext import *
import logging
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
import json
from slackclient import SlackClient


class SlackBot(base_chatbot.Bot):
        
    def __init__(self):
        super(SlackBot, self).__init__()

        # Slack specific variables and settings
        self.slackClient = None

        self.OAUTH_ACCESS_TOKEN = None
        self.BOT_USER_OAUTH_ACCESS_TOKEN = None

        # starterbot's user ID in Slack: value is assigned after the bot starts up
        self.USERID = None

        # constants
        self.RTM_READ_DELAY = 0.5 # 0.5 second delay between reading from RTM

        self.USERMAP = {}
        self.CHANNELMAP = {}

    def initialize(self, configFile):
        super(SlackBot,self).initialize(configFile)

        # slack specific arguments
        with open(configFile) as json_data_file:
            args = json.load(json_data_file)


        self.OAUTH_ACCESS_TOKEN = args.get("slack_oauth_token", None)
        self.BOT_USER_OAUTH_ACCESS_TOKEN = args.get("slack_user_oauth_token", None)

        # constants
        self.RTM_READ_DELAY = float( args.get("slack_rtm_read_delay", 0.5) )


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
                # Maybe we are being directly messaged
                result = self.nickFromUserId(channel_id)
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

            self.recordSeen(speaker, line)

            # Start creating a msg dict to pass to the markov chain
            msg = {}
            msg["p_reply"] = self.p_reply

            text = line

            # Detect and trim off any leading direct adresses (i.e. "@foo, how are you?")
            direct, txt = self.amDirectlyAddressed(line)
            if direct is not None:
                text = txt
                # If we are directly addressed, then probability of our reponse should be 1
                if direct == self.NICK:
                    # If this was a command, e.g. "chatbot, seen jane?" we
                    # execute it and return. We don't want to 'learn' commands
                    cmd_text = self.resolveUserIds(text)
                    if self.handleCommand(cmd_text):
                        return
                    # otherwise, we set a 100% chance to reply
                    msg["p_reply"] = 1.0

            text = self.resolveUserIds(text)
            text = self.preprocessText(text)
            if len(text) == 0:
                continue

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



    def registerCommands(self):
        super(SlackBot, self).registerCommands()

        self.commands.update({'seen' : self._cmd_seen})
        return


    def _cmd_seen(self, text):
        words = self.preprocessText(text).split()
        (hasBeenSeen, whatSaid, howLong) = self.hasBeenSeen(words[0])
        reply = ""
        if not hasBeenSeen:
            reply = "I haven't seen", nick
        else:
            reply = nick,"was last seen", howLong, "ago, when they said'", whatSaid,"'"

        self.SLACKCLIENT.api_call("chat.postMessage",
                                  channel=msg["channel"],
                                  text=reply)
        return True

    def run(self):
        super(SlackBot, self).run()
        self.registerCommands()
        self.joinSlack()

        while True:
            input = self.SLACKCLIENT.rtm_read()
            if len(input) == 0:
                continue
            self.parseEvents(input)
            time.sleep(self.RTM_READ_DELAY)


    
#####

if __name__ == "__main__":
    bot = SlackBot()
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        print "Reading configuration from", config_file
        bot.initialize(config_file)

    bot.run()
    bot.quit()

