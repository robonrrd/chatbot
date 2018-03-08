#!/usr/bin/env python
import argparse
import base_chatbot


class ConsoleBot(base_chatbot.Bot):
        
    def run(self):
        super(ConsoleBot, self).run()
        
        print "Hi, my name is", self.NICK
        while True:
            try:
                txt = raw_input("> ")
            except EOFError:
                print
                break

            msg = {}
            msg["text"] = txt
            msg["speaker"] = "user"
            msg["speaking_to"] = None
            msg["p_reply"] = self.p_reply
            
            reply = self.possiblyReply(msg)
            if reply is not None:
                print reply

            self.addPhrase(txt)
    
#####

if __name__ == "__main__":

    PARSER = argparse.ArgumentParser(description='A snarky IRC bot.')
    PARSER.add_argument("--nick", help="The bot's nickname", default="charrak")
    PARSER.add_argument("--realname", help="The bot's real name", default="charrak the kobold")
    PARSER.add_argument("--owners", help="The list of owner nicks", default="nrrd, nrrd_, mrdo, mrdo_")
    PARSER.add_argument("--save_rate", help="How often (# of changes) to save databases", default=100)
    PARSER.add_argument("--seendb", help="Path to seendb", default="./seendb.pkl")
    PARSER.add_argument("--markovdb", help="Path to markovdb", default="./charrakdb")
    PARSER.add_argument("--p", help="Probability (0..1) to reply", default="0.1")
    PARSER.add_argument("--readonly", help="The bot will not learn from other users, only reply to them", dest='readonly', action='store_true')
    PARSER.set_defaults(readonly=False)

    bot = ConsoleBot(PARSER.parse_args())
    bot.run()
    bot.quit()

