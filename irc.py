import errno
import logging
import socket
import string

from colortext import *

class ConnectionClosedException(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


class Irc(object):
    def __init__(self, host, port, nick, ident, realname):
        self.readbuffer = '' # store all the messages from server

        self._who = {} # lists of who is in what channels
        self._ops = {} # lists of ops is in what channels

        self.irc = socket.socket()
        self.irc.connect((host, port))
        self.send("NICK %s\r\n" % nick)
        self.send("USER %s %s bla :%s\r\n" % (ident, host, realname))

        # This is a hack, but how should I detect when I've successfully joined
        # a channel?
        self._eatLinesUntilText('End of /MOTD command')

    def __del__(self):
        if self.irc:
            self.irc.close()

    def _eatLinesUntilText(self, stopText):
        # Loop until we encounter the passed in 'stopText'
        while 1:
            temp = self.readlines()

            for line in temp:
                logging.info(YELLOW + line)
                words = string.rstrip(line)
                words = string.split(words)

                # TODO: pull this out into a method to check for pings
                if len(words) > 0 and (words[0] == "PING"):
                    self.pong(words[1])

                # This is a hack, but how should I detect when to join
                # a channel?
                if line.find(stopText) != -1:
                    return

    def _eatLinesUntilEndOfNames(self):
        # get the current population of the channel
        # :magnet.llarian.net 353 gravy = #test333 :gravy @nrrd
        # :magnet.llarian.net 366 gravy #test333 :

        population = []
        operators = []
        while True:
            temp = self.readlines()
            for line in temp:
                logging.info(YELLOW + line)
                words = string.rstrip(line)
                words = string.split(words)

                if words[0] == 'PING':
                    self.pong(words[1])

                elif words[1] == '366':
                    logging.info(DBLUE + 'Done parsing population')
                    return population, operators

                elif words[1] == '353':
                    logging.info(DBLUE + 'Population of %s: %s',
                                 words[4], words[5:])
                    # get the current population of the channel
                    for nick in words[5:]:
                        op = False
                        if nick[0] == "@":
                            op = True
                            nick = nick[1:]
                        elif nick[0] == ":":
                            nick = nick[1:]

                        population += [nick]
                        if op:
                            operators += [nick]

    def join(self, channel):
        channel = str(channel)
        if channel[0] != '#':
            channel = '#' + channel
        self.send('JOIN ' + channel + '\n')

        population, operators = self._eatLinesUntilEndOfNames()
        logging.info(DGREEN + channel + ' who: ' + ','.join(population))
        logging.info(GREEN + channel + ' ops: ' + ','.join(operators))
        self._who[channel] = self._uniquify(population)
        self._ops[channel] = self._uniquify(operators)

    def part(self, channel):
        channel = str(channel)
        if channel[0] != '#':
            channel = '#' + channel
        self.send('PART ' + channel + '\r\n')

    def readlines(self):
        try:
            recv = self.irc.recv(1024)
            if len(recv) == 0:
                raise ConnectionClosedException()

            self.readbuffer = self.readbuffer + recv
        except socket.error as (code, msg):
            logging.error(RED + 'socket error: ' + msg)
            if code != errno.EINTR:
                raise

        temp = string.split(self.readbuffer, "\n")
        self.readbuffer = temp.pop()
        return temp

    def _uniquify(self, seq):
        # not order preserving
        s = {}
        map(s.__setitem__, seq, [])
        return s.keys()

    def isop(self, nick, channel=None):
        if channel:
            return nick in self._ops[channel]
        else:
            for channel in self._ops:
                if nick in self._ops[channel]:
                    return True

        return False

    def addop(self, chan, nick):
        if self.isop(nick, channel=chan):
            return
        logging.info(PURPLE + ('Adding %s as op of %s' % (nick, chan)))
        self._ops[chan].append(nick)

    def rmop(self, chan, nick):
        if not self.isop(nick, channel=chan):
            return
        logging.info(PURPLE + ('Removing %s as op of %s' % (nick, chan)))
        self._ops[chan].remove(nick)

    def iswho(self, nick, channel=None):
        if channel:
            return nick in self._who[channel]
        else:
            for channel in self._who:
                if nick in self._who[channel]:
                    return True

        return False

    def addwho(self, chan, nick):
        if self.iswho(nick, channel=chan):
            return
        logging.info(CYAN + ('Adding %s in %s' % (nick, chan)))
        self._who[chan].append(nick)

    def rmwho(self, chan, nick):
        if not self.iswho(nick, channel=chan):
            return
        logging.info(CYAN + ('Removing %s from %s' % (nick, chan)))
        self._who[chan].remove(nick)

    # TODO: take a channel arg?
    def makeop(self, nick):
        for chan in self._who:
            for who in self._who[chan]:
                if nick == who:
                    logging.info(PURPLE + ('Setting +o on %s' % nick))
                    self.send('MODE ' + chan + ' +o ' + nick + '\r\n')
                    self.addop(chan, nick)

    # Irc communication functions
    def privmsg(self, speaking_to, text):
        logging.debug(PURPLE + speaking_to + PLAIN + " : " + BLUE + text)
        self.send('PRIVMSG '+ speaking_to +' :' + text + '\r\n')

    def pong(self, server):
        #cprint(GREEN, "PONG " + server + "\n")
        self.send("PONG %s\r\n" % server)

    def send(self, msg):
        self.irc.sendall(msg)
