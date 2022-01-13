#!python3
import sys
import os
import re
import getopt
import operator
import random

def usage():
    progname = sys.argv[0]
    message = '''
Wordle Hinter: find words that might fit a Wordle puzzle.

Usage:")
    {progname} -g <greenpattern> -y <yellowchars> -e <eliminated> [-p] [-l wordlist] -n N

<greenpattern> should use dots for unknowns, and letters where known, e.g. '..B.Y'
If no <greenpattern> is supplied, it is assumed to be '.....', i.e. 5 unknown characters.

<yellowchars> should just be the other letters where the position is unknown, e.g. 'AE'

<eliminated> represents the letters already ruled out (greyed out in Wordle), e.g. 'ST'

Neither parameter is case sensitive.

-p is an optional flag causing the program to print all options, even if there are a lot.
It is often worth piping the output through column (if available).

-l overrides the default wordlist filename, if you want to use a different dictionary.

-n prints the best N options for the next guess. If omitted, default is N=1.

Examples:
    {progname} -g '...RT' -p | column
    {progname} -g '.AIN.' -y 'T' -e 'S'
    {progname} -l mywordlist.txt

    '''
    print(message)
    sys.exit(1)

# ------- Part 1: Find possible words ---------

# Read commandline arguments
argv = sys.argv[1:]
try:
    opts, args = getopt.getopt(argv, "g:y:pl:n:e:")
except:
    usage()

greenregex = "....."
yellowletters = ""
yellowregex = ""
greyletters = ""
greyregex = ""
printall = False
wordlist_filename = "wordlelist.txt"
n = 1

for opt,arg in opts:
    if opt == '-g':
        greenregex = arg
    if opt == '-y':
        yellowletters = arg
    if opt == '-e':
        greyletters = arg
    if opt == '-p':
        printall = True
    if opt == '-l':
        wordlist_filename = arg
    if opt == '-n':
        n = int(arg)
for char in yellowletters:
    if not char in greenregex:
        yellowregex += "(?![^" + char + "]{5})" 
for char in greyletters:
    if not (char in greenregex or char in yellowletters):
        greyregex += "(?!.*" + char + ".*)" 

# Check inputs
if len(greenregex) != 5:
    print("\nFATAL: I only work on five-letter words. The green pattern must be of length 5 (or absent).\n")
    usage()

# Compile regexes to implement inputs
mask = re.compile('^'+yellowregex+greyregex+greenregex+'$')

# Read the word list
if not ( os.path.isfile(wordlist_filename) and os.access(wordlist_filename, os.R_OK) ):
    print("Could not read wordlist file "+wordlist_filename)
    sys.exit(3)
fh = open(wordlist_filename,"r")
wordsdict = {}
for line in fh.readlines():
    w = line.rstrip().lower()

    # Skip it if it doesn't match the green & yellow constraints
    if mask.match(w): 
        wordsdict[w] = 1
    
fh.close()

words=list(wordsdict.keys())            # Just to save typing wordsdict.keys() all the time

if len(words)>20 and not printall:
    print("There are", len(words), "candidate words")
    print("Random word:",random.choice(words))
elif len(words)==0:
    print("No matches found. We're gonna need a bigger wordlist.")
else:
    print("\nCandidate words:")
    print("\n".join(words))


# ------- Part 2: suggest a good (possibly optimal?) next guess ---------

# When converting to a score, the aim is to bisect the option space, so closest to 50% match is best
goal = len(words)/2

# Find letter frequencies in the un-fixed positions
positions={}
for pos in range(5):
    if not greenregex[pos]==".":
        continue

    positions[pos]={}
    for word in words:
        if not word[pos] in positions[pos]:
            positions[pos][word[pos]]=1
        else:
            positions[pos][word[pos]]+=1

for pos in positions.keys():
    for char in positions[pos]:
        positions[pos][char] = abs(positions[pos][char] - goal)

# Calculate a score for each word
for word in words:
    score = 0
    for pos in positions.keys():
        score += positions[pos][word[pos]]
    wordsdict[word]=score

# Find the best options
bestwords = sorted(wordsdict.items(), key=operator.itemgetter(1), reverse=False)

print("\nFor the next guess, try",bestwords[0][0])
if n>1:
    print("\nOther reasonable options:")
    for w in bestwords[1:n]:
        print(w[0])
