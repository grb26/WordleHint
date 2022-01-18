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
    message = f'''
Wordle Hinter: find words that might fit a Wordle puzzle.

Usage:
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
def buildRegex(known):
    green="....."
    yellow=""
    grey=""
    regex=""
    for clue in known:
        if not re.match('^(g[1-5][a-z]|y[1-5][a-z]|x[a-z])$', clue):
            usage()
        
        if clue[0] == 'g':
            pos = int(clue[1]) - 1    # Convert position identifier to zero-index
            green = green[:pos] + clue[2] + green[pos+1:]
        
        elif clue[0] == 'y':
            pos = int(clue[1]) - 1    # Convert position identifier to zero-index
            yellow += "(?=.*" + clue[2] + ")(?!" + ("."*pos) + clue[2] + ("."*(4-pos)) + ")"
        
        elif clue[0] == 'x':
            grey += "(?!.*" + clue[1] + ")"
        else:
            usage()     # Shouldn't really be possible to get here

    regex = "^" + yellow + grey + green
    # print("Debug: regex is", regex)
    return re.compile(regex)

# Subroutine to filter (in place) a list of words, using the supplied regex, optionally just returning the number of words that would have been removed without actually doing it
def filterWords(words, regex, justCount=False):
    killlist = []
    for i in range(len(words)):
        if not regex.match(words[i]):
            killlist.append(i)
    if not justCount:
        killlist.reverse()
        for i in killlist:
            del(words[i])
    return len(killlist)

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
def method1(words, known):
    # When converting to a score, the aim is to bisect the option space, so closest to 50% match is best
    goal = len(words)/2

    # Which letters are known vs unknown? Need to pull out the greens from our clues
    unfixed = [i for i in range(5)]
    for clue in known:
        if re.match('^g[1-5][a-z]$', clue) and (int(clue[1])-1) in unfixed:
            unfixed.remove(int(clue[1]) - 1)   # Convert position identifier to zero-index
    if len(unfixed) == 0:
        print("Duh... wut? We already know the answer.", file=sys.stderr)
        sys.exit(1)

    # Find letter frequencies in the unfixed positions
    positions={}
    for pos in unfixed:
        positions[pos]={}
        for word in words:
            if not word[pos] in positions[pos]:
                positions[pos][word[pos]]=1
            else:
                positions[pos][word[pos]]+=1

    for pos in positions.keys():
        for char in positions[pos].keys():
            positions[pos][char] = abs(positions[pos][char] - goal)/goal     # Normalize to distance from being a perfect bisector

    # Sum up the total distance for each candidate next-guess
    m1dict={}
    for word in words:
        score = 0
        for pos in positions.keys():
            score += positions[pos][word[pos]]
        m1dict[word]=score/len(positions)

    return m1dict

# Method 2 - see how a each guessword would reduce the solution space
def method2(trylist, wordlist, known):
    m2dict={}
    cnt=0
    pid=os.getpid()
    starttime=time.time()

    for guessword in trylist:
        cnt+=1
        guesswordscore = 0
        avetime = (time.time() - starttime)/cnt
        esttime = (len(trylist)-cnt)*avetime/60
        #print(f"PID {pid} is on {cnt} of {len(trylist)}. Average time is {avetime:2.4f}, estimate {esttime:4.1f} minutes")

        # One of the words in wordlist must be the true answer. Evaluate guessword against each, and see what the resulting solution space would be.
        for trueword in wordlist:
            # print("Debug: guessword",guessword,"against trueword",trueword)

            # Maybe we got lucky...
            if guessword == trueword:   
                continue                    # Don't add anything to the solution space count, as we found it

            # If not, then the resulting pattern updates would be...
            newknown = []
            for pos in range(5):
                g = guessword[pos]
                t = trueword[pos]
                if g == t:
                    newknown.append('g' + str(pos+1) + g)
                elif g in trueword:
                    newknown.append('y' + str(pos+1) + g)
                elif not g in trueword and not ('x'+g) in known:
                    newknown.append('x' + g)
            # print("Debug: new knowns are",newknown)
            newregex = buildRegex(known+newknown)

            # ...and count how many words that would remove
            kills = filterWords(wordlist, newregex, justCount=True)

            # The score is the size of the remaining wordlist
            guesswordscore += (len(wordlist) - kills) / len(wordlist)
            # print("Debug: guessword",guessword,"against trueword",trueword,"scores",guesswordscore)
        
        # (end of trueword loop)

        # We can now calculate the average tree depth under guessword
        guesswordscore /= len(wordlist)
        m2dict[guessword]=guesswordscore

    return m2dict

# Method 3 - letter frequency analysis is fast, but can we apply it across all positions rather than treating each position separately?
def method3(trylist, wordlist):

    # Count letter frequency across remaining solution options
    wordsContaining={ char:0 for char in string.ascii_lowercase }
    for w in wordlist:
        for ch in wordsContaining.keys():
            if ch in w:
                wordsContaining[ch] += 1
    
    # Convert from absolute frequency to normalized distance from 50% (aim is to bisect solution space with each letter)
    goal = len(words)/2
    for ch in wordsContaining.keys():
        wordsContaining[ch] = abs(wordsContaining[ch] - goal) / goal

    # Add up the score for each candidate word in trylist
    m3dict={}
    for guessword in trylist:
        m3dict[guessword]=0
        for pos in range(5):
            if guessword[pos] in guessword[:pos]:
                m3dict[guessword] += 1         # Penalise repeated letters, as they add no new information
            else:
                m3dict[guessword] += wordsContaining[guessword[pos]] / 5 

    return m3dict

#### MAIN
if __name__ == '__main__':

    # Read commandline arguments
    argv = sys.argv[1:]
    try:
        opts, args = getopt.gnu_getopt(argv, "pl:n:fsm")
    except:
        usage()

    known = [x.lower() for x in args]        # Remaining options after parsing out the getopt params
    printall = False
    wordlist_filename = "wordlelist.txt"
    n = 1
    fast = True 
    slow = True 
    multicore = False

    for opt,arg in opts:
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
        if opt == '-m':
            multicore = True

    if not fast and not slow:
        fast = True 
        slow = True

    # Read and filter the word list, based on the supplied inputs, to get candidate words
    words = readListFromFile(wordlist_filename)
    regex = buildRegex(known)
    filterWords(words, regex)

    # Display findings
    if len(words)>20 and not printall:
        print("There are", len(words), "candidate words, including gems such as",random.choice(words),"and",random.choice(words))
    elif len(words)==0:
        print("No matches found. We're gonna need a bigger wordlist.")
        sys.exit(0)
    else:
        print("\nCandidate words:")
        print("\n".join(words))


    # ------- Part 2: suggest a good (possibly optimal?) next guess ---------
    if fast:
        ### Method 1: somewhat naive heuristic, aiming to hit greens (basically ignores yellows, so probably not optimal)
        m1start = time.time()
        m1dict=method1(words, known)
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

        print("For the next guess, method 3 suggests that you try",m3bestwords[0][0])
        if n>1:
            print("\nOther reasonable options:")
            for w in m3bestwords[1:n]:
                print(w[0])
    if slow:
        m2start = time.time()
        m2dict={}        
        
        if multicore:
            # This part can take a while, so let's play with multi-processing.
            cores = mp.cpu_count()
            mypool = mp.Pool(processes=cores)
            l = len(words)
            wordslices = [words[int(l*(i/cores)):int(l*((i+1)/cores))] for i in range(cores)]
            results = mypool.starmap(method2, [(wordslices[i], words, known) for i in range(cores)])
            for res in results:
                m2dict.update(res)
        else:
            m2dict=method2(words, words, known)

        m2bestwords = sorted(m2dict.items(), key=operator.itemgetter(1), reverse=False)

        m2end = time.time()

        print("For the next guess, method 2 suggests that you try",m2bestwords[0][0])
        if n>1:
            print("\nOther reasonable options:")
            for w in m2bestwords[1:n]:
                print(w[0])

    if fast and slow:
        print("\nSCORE COMPARISON")
        m1=m1bestwords[0][0]
        m2=m2bestwords[0][0]
        m3=m3bestwords[0][0]
        print('Method1 top {0:}, scores M1: {1:4.2f} M2: {2:4.2f} M3: {3:4.2f}, found in {4:6.4f} seconds.'.format(m1, m1dict[m1], m2dict[m1], m3dict[m1], m1end-m1start))
        print('Method2 top {0:}, scores M1: {1:4.2f} M2: {2:4.2f} M3: {3:4.2f}, found in {4:6.4f} seconds.'.format(m2, m1dict[m2], m2dict[m2], m3dict[m2], m2end-m2start))
        print('Method3 top {0:}, scores M1: {1:4.2f} M2: {2:4.2f} M3: {3:4.2f}, found in {4:6.4f} seconds.'.format(m3, m1dict[m3], m2dict[m3], m3dict[m3], m3end-m3start))

