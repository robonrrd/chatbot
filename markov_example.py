#!/usr/bin/python
import markov
from colortext import ENDC

mc = markov.MarkovChain('new.db')
print ENDC

mc.addLine('The big dog likes ham')


for key in mc.db.keys():
    print key, mc.db[key]
print

mc.addLine('The big dog likes scratches')
mc.addLine('The big dog likes scratches')
mc.addLine('The big dog likes scratches')

for key in mc.db.keys():
    print key, mc.db[key]
    resp =  mc.db[key]
    for rr in resp:
        print rr[0]

seed = ('the', 'big')
print

for ii in range(0,10):
    print seed[0], seed[1] , mc.respond(seed)
