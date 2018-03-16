#!/usr/bin/env python
import sys
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
    bot = ConsoleBot()

    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        print "Reading configuration from", config_file
        bot.initialize(config_file)

    bot.run()
    bot.quit()

