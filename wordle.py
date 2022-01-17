#!python3
import sys
import os
import re
import getopt
import operator
import time
import random
import multiprocessing as mp
import string

def usage():
    progname = sys.argv[0]
    message = '''
Wordle Hinter: find words that might fit a Wordle puzzle.

Usage:"
    {progname} -g <greenpattern> -y <yellowchars> -e <eliminated> [-p] [-l wordlist] [-n N] [-f] [-s]

<greenpattern> should use dots for unknowns, and letters where known, e.g. '..B.Y'
If no <greenpattern> is supplied, it is assumed to be '.....', i.e. 5 unknown characters.

<yellowchars> should just be the other letters where the position is unknown, e.g. 'AE'

<eliminated> represents the letters already ruled out (greyed out in Wordle), e.g. 'ST'

Neither parameter is case sensitive.

-p is an optional flag causing the program to print all options, even if there are a lot.
It is often worth piping the output through column (if available).

-l overrides the default wordlist filename, if you want to use a different dictionary.

-n prints the best N options for the next guess. If omitted, default is N=1.

-f fast mode (quick but not fantastic recommendations)
-s slow mode (slower, but hopefully better, method for generating recommendations)
If neither -f nor -s is specified, the default is to use both and compare the results.
WARNING: Running slow mode with no green/yellow/grey constraints takes hours. The answer is TARES. 

Examples:
    {progname} -g '...RT' -p | column
    {progname} -g '.AIN.' -y 'T' -e 'S'
    {progname} -l mywordlist.txt -f

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
        yellowregex += "(?![^" + char + "]{5})"                     # Yellow means we know a character is present, so each regex says "must not be a string containing five characters that aren't this one"
    if len(grey)>0:
        greyregex = "(?!.*["+grey+"].*)"                            # Grey means the character isn't present, so this regex says "must not be a string containing any character in this list"
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

# Method 1 for finding a good next guess
def method1(words, green):
    # When converting to a score, the aim is to bisect the option space, so closest to 50% match is best
    goal = len(words)/2

    # Find letter frequencies in the un-fixed positions
    positions={}
    for pos in range(5):
        if not green[pos]==".":
            continue

        positions[pos]={}
        for word in words:
            if not word[pos] in positions[pos]:
                positions[pos][word[pos]]=1
            else:
                positions[pos][word[pos]]+=1

    for pos in positions.keys():
        for char in positions[pos].keys():
            positions[pos][char] = abs(positions[pos][char] - goal)     # Convert to distance from being a perfect bisector

    # Sum up the total distance for each candidate next-guess
    m1dict={}
    for word in words:
        score = 0
        for pos in positions.keys():
            score += positions[pos][word[pos]]
        m1dict[word]=score

    return m1dict

# Method 2 - see how a each guessword would reduce the solution space
def method2(trylist, wordlist, origgreen, origyellow, origgrey):
    retdict={}
    cnt=0
    pid=os.getpid()
    starttime=time.time()

    for guessword in trylist:
        cnt+=1
        guesswordscore = 0
        avetime = (time.time() - starttime)/cnt
        esttime = (len(trylist)-cnt)*avetime/60
        # print(f"PID {pid} is on {cnt} of {len(trylist)}. Average time is {avetime:2.4f}, estimate {esttime:4.1f} minutes")

        # One of the words in wordlist must be the true answer. Evaluate guessword against each, and see what the resulting solution space would be.
        for trueword in wordlist:
            

            # Maybe we got lucky...
            if guessword == trueword:   
                continue                    # Don't add anything to the solution space count, as we found it

            # If not, then the resulting pattern updates would be...
            newgreen=origgreen
            newyellow=origyellow
            newgrey=origgrey
            yellowpositions=""
            yellowregex=""
            greyregex=""
            for pos in range(5):
                g = guessword[pos]
                t = trueword[pos]
                if g == t:
                    newgreen = newgreen[:pos] + g + newgreen[pos+1:]
                elif g in trueword:
                    yellowpositions += "(?!" + ("."*pos) + g + ("."*(4-pos)) + ")"
                    if not g in newyellow:
                        newyellow+=g
                elif not g in trueword and not g in newgrey:
                    newgrey+=g
            if len(newgrey)>0:
                greyregex = "(?!.*["+newgrey+"].*)"
            for char in newyellow:
                yellowregex += "(?=.*"+char+")"
            regexstr = '^'+yellowpositions+yellowregex+greyregex+newgreen+'$'
            #print("Guess",guessword,"True",trueword,"Regex",regexstr)
            newregex = re.compile(regexstr)

            # ...and count how many words that would remove
            kills = 0
            for w in wordlist:
                if not newregex.match(w):
                    kills += 1

            # The score is the size of the remaining wordlist
            guesswordscore += len(wordlist) - kills

        
        # (end of trueword loop)

        # We can now calculate the average tree depth under guessword
        guesswordscore /= len(wordlist)
        retdict[guessword]=guesswordscore

    return retdict

# Method 3 - letter frequency analysis is fast, but can we apply it across all positions rather than treating each position separately?
def method3(trylist, wordlist):

    # Count letter frequency across remaining solution options
    wordsContaining={ char:0 for char in string.ascii_lowercase }
    for w in wordlist:
        for ch in wordsContaining.keys():
            if ch in w:
                wordsContaining[ch] += 1
    
    # Convert from absolute frequency to distance from 50% (aim is to bisect solution space with each letter)
    goal = len(words)/2
    for ch in wordsContaining.keys():
        wordsContaining[ch] = abs(wordsContaining[ch] - goal)
   
    # Add up the score for each candidate word in trylist
    m3dict={}
    for guessword in trylist:
        m3dict[guessword]=0
        for pos in range(5):
            if guessword[pos] in guessword[:pos]:
                m3dict[guessword] += len(wordlist)          # Penalise repeated letters, as they add no new information
            else:
                m3dict[guessword] += wordsContaining[ch]

    return m3dict

# #### HACKMAIN for testing
# gwords = readListFromFile("wordlelist.txt")
# words = list(gwords)
# filterWords(words,buildRegex('...e.', 'a', 'sortidl'))
# m2dict = method2(words, words, '...e.', 'a', 'sortidl')
# m2bestwords = sorted(m2dict.items(), key=operator.itemgetter(1), reverse=False)
# print("\nRanked options:")
# print(m2bestwords[0:20])
# sys.exit(0)

#### MAIN
if __name__ == '__main__':

    # Read commandline arguments
    argv = sys.argv[1:]
    try:
        opts, args = getopt.getopt(argv, "g:y:pl:n:e:fs")
    except:
        usage()

    greenpattern = "....."    # Default: five characters, could be anything
    yellowletters = ""
    greyletters = ""
    printall = False
    wordlist_filename = "wordlelist.txt"
    n = 1
    fast = True 
    slow = True 

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
        if opt == '-f':
            slow = False
        if opt == '-s':
            fast = False

    if not fast and not slow:
        fast = True 
        slow = True

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
    if fast:
        ### Method 1: somewhat naive heuristic, aiming to hit greens (basically ignores yellows, so probably not optimal)
        m1start = time.time()
        m1dict=method1(words, greenpattern)
        m1bestwords = sorted(m1dict.items(), key=operator.itemgetter(1), reverse=False)
        m1end = time.time()

        print("\nFor the next guess, method 1 suggests that you try",m1bestwords[0][0])
        if n>1:
            print("\nOther reasonable options:")
            for w in m1bestwords[1:n]:
                print(w[0])

        ### Method 3: treats yellows and greens equally, also not really optimal
        m3start = time.time()
        m3dict=method3(words, words)
        m3bestwords = sorted(m3dict.items(), key=operator.itemgetter(1), reverse=False)
        m3end = time.time()

        print("\nFor the next guess, method 3 suggests that you try",m3bestwords[0][0])
        if n>1:
            print("\nOther reasonable options:")
            for w in m3bestwords[1:n]:
                print(w[0])
    if slow:
        ### Implementation 2: don't treat each char separately, see which word best halves the remaining solution space
        m2start = time.time()

        # Initialise a dictionary to keep score
        m2dict = {}
        # This part can take a while, so let's play with multi-processing.
        cores = mp.cpu_count()
        mypool = mp.Pool(processes=cores)
        l = len(words)
        wordslices = [words[int(l*(i/cores)):int(l*((i+1)/cores))] for i in range(cores)]
        results = mypool.starmap(method2, [(wordslices[i], words, greenpattern, yellowletters, greyletters) for i in range(cores)])
        for res in results:
            m2dict.update(res)

        # # Or maybe let's just see if the old M2 still works
        # m2dict=method2(words, words, greenpattern, yellowletters, greyletters)

        m2bestwords = sorted(m2dict.items(), key=operator.itemgetter(1), reverse=False)

        m2end = time.time()

        print("For the next guess, method 2 suggests that you try",m2bestwords[0][0])
        if n>1:
            print("\nOther reasonable options:")
            for w in m2bestwords[1:n]:
                print(w[0])

    if fast and slow:
        print("SCORE COMPARISON")
        print('Method1 recommended {0:}, scored {1:6.2f} by M1 and {2:6.2f} by M2, found in {3:6.4f} seconds.'.format(m1bestwords[0][0], m1bestwords[0][1], m2dict[m1bestwords[0][0]], m1end-m1start))
        print('Method2 recommended {0:}, scored {1:6.2f} by M1 and {2:6.2f} by M2, found in {3:6.4f} seconds.'.format(m2bestwords[0][0], m1dict[m2bestwords[0][0]], m2bestwords[0][1], m2end-m2start))

