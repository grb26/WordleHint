#!python3
import sys
import os
import re
import getopt
import operator
import time
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
    print(message, file=sys.stderr)
    sys.exit(1)

# ------- Part 1: Find possible words ---------

# Function to turn known letters into a compiled regex for word matching/elimination
def buildRegex(green, yellow, grey):
    if len(green) != 5:
        print("\nFATAL: I only work on five-letter words. The green pattern must be of length 5 (or absent).\n", file=sys.stderr)
        usage()
    yellowregex=""
    greyregex=""
    for char in yellow:
        yellowregex += "(?![^" + char + "]{5})"                     # Yellow means we know a character is present, so this regex says "must not contain five characters that aren't this one"
    for char in grey:
        if not (char in green or char in yellow):                   # Can't be grey AND yellow/green, so assume user error and ignore the grey
            greyregex += "(?!.*" + char + ".*)"                     # Grey means we know a character is not present, so this regex says "must not contain this character"
    # Compile regexes to implement inputs
    regexstr = '^'+yellowregex+greyregex+green+'$'
    return re.compile(regexstr)

# Subroutine to filter (in place) a list of words, using the supplied regex
def filterWords(wlist, regex):
    for word in tuple(wlist):                                       # Need to create a copy of wlist, as we're modifying it place. Can't iterate over it and modify it at the same time, we end up shooting at a moving target.
        if not regex.match(word):
            wlist.remove(word)
#    return wlist                                                    # Not necessary, as wlist is passed in by reference anyway, but harmless

# Function to read a file into a list
def readListFromFile(wordlist_filename):
    if not ( os.path.isfile(wordlist_filename) and os.access(wordlist_filename, os.R_OK) ):
        print("Could not read wordlist file",wordlist_filename, file=sys.stderr)
        sys.exit(3)
    fh = open(wordlist_filename,"r")
    words = []
    for line in fh.readlines():
        w = line.rstrip().lower()
        words.append(w)
    fh.close()
    return words



# Read commandline arguments
argv = sys.argv[1:]
try:
    opts, args = getopt.getopt(argv, "g:y:pl:n:e:")
except:
    usage()

greenpattern = "....."    # Default: five characters, could be anything
yellowletters = ""
greyletters = ""
printall = False
wordlist_filename = "wordlelist.txt"
n = 1

for opt,arg in opts:
    if opt == '-g':
        greenpattern = arg.lower()
    if opt == '-y':
        yellowletters = arg.lower()
    if opt == '-e':
        greyletters = arg.lower()
    if opt == '-p':
        printall = True
    if opt == '-l':
        wordlist_filename = arg
    if opt == '-n':
        n = int(arg)

# Read and filter the word list, based on the supplied inputs, to get candidate words
words = readListFromFile(wordlist_filename)
regex = buildRegex(greenpattern, yellowletters, greyletters)
filterWords(words, regex)

# Display findings
if len(words)>20 and not printall:
    print("There are", len(words), "candidate words")
    print("Random word:",random.choice(words))
elif len(words)==0:
    print("No matches found. We're gonna need a bigger wordlist.")
else:
    print("\nCandidate words:")
    print("\n".join(words))


# ------- Part 2: suggest a good (possibly optimal?) next guess ---------

### Method 1: somewhat naive heuristic, aiming to hit greens (basically ignores yellows, so probably not optimal)
m1start = time.time()

# When converting to a score, the aim is to bisect the option space, so closest to 50% match is best
goal = len(words)/2

# Find letter frequencies in the un-fixed positions
positions={}
for pos in range(5):
    if not greenpattern[pos]==".":
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
m1dict={}
for word in words:
    score = 0
    for pos in positions.keys():
        score += positions[pos][word[pos]]
    m1dict[word]=score

# Find the best options
m1bestwords = sorted(m1dict.items(), key=operator.itemgetter(1), reverse=False)

m1end = time.time()

print("\nFor the next guess, method 1 suggests that you try",m1bestwords[0][0])
if n>1:
    print("\nOther reasonable options:")
    for w in m1bestwords[1:n]:
        print(w[0])

### Implementation 2: don't treat each char separately, see which word best halves the remaining solution space
m2start = time.time()

# When converting to a score, the aim is to bisect the option space, so closest to 50% match is best
goal = len(words)/2

# Initialise a dictionary to keep score
m2dict = {}

# If I were to guess guessword...
for guessword in words:

    guesswordscore = 0

    #print("Debug:",prefix,guessword)

    # And if the real answer happens to be trueword...
    for trueword in words:

        # Maybe we got lucky...
        if guessword == trueword:
            continue

        # If not, then the resulting pattern updates would be...
        newgreen=greenpattern
        newyellow=yellowletters
        newgrey=greyletters
        for pos in range(5):
            g = guessword[pos]
            t = trueword[pos]
            if g == t:
                newgreen[pos] == g
            elif g in trueword and not g in newgreen and not g in newyellow:
                newyellow+=g
            elif not g in trueword and not g in newgrey:
                newgrey+=g

        # So now I can generate a new wordlist...
        newwords = list(words)
        newwords.remove(guessword)
        newregex = buildRegex(newgreen, newyellow, newgrey)
        filterWords(newwords, newregex)

        # ...and record the size of the resulting search space
        guesswordscore += len(newwords)

        del newwords

    # (end of trueword loop)

    # We can now calculate the average tree depth under guessword
    guesswordscore /= len(words)
    m2dict[guessword] = guesswordscore

# (end of guessword loop)

m2bestwords = sorted(m2dict.items(), key=operator.itemgetter(1), reverse=False)

m2end = time.time()

print("\nFor the next guess, method 2 suggests that you try",m2bestwords[0][0])
if n>1:
    print("\nOther reasonable options:")
    for w in m2bestwords[1:n]:
        print(w[0])

print("SCORE COMPARISON")
print("M1 recommendations, generated in",(m1end-m1start),"seconds")
for i in range(n):
    w = m1bestwords[i][0]
    print(w, m1dict[w], m2dict[w])
print("M2 recommendations, generated in",(m2end-m2start),"seconds")
for i in range(n):
    w = m2bestwords[i][0]
    print(w, m1dict[w], m2dict[w])
