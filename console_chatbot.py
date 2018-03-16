#!/usr/bin/env python
import sys
import base_chatbot


class ConsoleBot(base_chatbot.Bot):
        

    def initialize(self, configFile):
        super(ConsoleBot,self).initialize(configFile)
        self.registerCommands()


    def registerCommands(self):
        super(ConsoleBot, self).registerCommands()

        print "Registering 'test'"
        self.commands.update({'test' : self._cmd_test})
        return


    def _cmd_test(self, text):
        print "Test command"
        return True


    def amDirectlyAddressed(self, text):
        words = self.preprocessText(text).split()
        if words[0] == self.NICK:
            print "Directly addressed"
            return words[0], ' '.join(words[1:])
        return None, None


    def run(self):
        super(ConsoleBot, self).run()
        
        print "Hi, my name is", self.NICK
        while True:
            try:
                txt = raw_input("> ")
            except EOFError:
                print
                break

            direct, cmd_text = self.amDirectlyAddressed(txt)
            if direct is not None:
                # If we are directly addressed, then probability of our reponse should be 1
                if direct == self.NICK:
                    if self.handleCommand(cmd_text):
                        continue

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

