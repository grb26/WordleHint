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
import itertools

def usage():
    print("Nope.")
    sys.exit(1)
    progname = sys.argv[0]
    message = f'''
Wordle Hinter: find words that might fit a Wordle puzzle.

Usage:
    {progname} [-e] [-w wordlist] [-g guesslist] [-n N] [-f] [-s] [word1:result1 word2:result2 ...]

The result pattern should use characters g, y & x to represent green (correct), yellow (present in the word but not in that location) and grey (not present in the word) respectively.

For example: amaze:yxgxg

Inputs are not case sensitive. If no word:result patterns are specified, attempt to calculate the optimal first guess.

-e enables 'Easy mode', whereby guesses do not need to respect the green & yellow results previously obtained (this is the default behaviour for Wordle).

-w overrides the default wordlist filename, if you want to use a different dictionary. This is the list of possible solution words.
-g specifies a different guesslist filename. This is the list of words to consider in guesses. It can sometimes be optimal to guess a word that cannot possibly be the solution, as it reveals more information. The default is to use the solution wordlist.

-n prints the best N options for the next guess. If omitted, default is N=1. If N=0, all possible solutions are printed (consider piping through 'column' if the output is large).

-f fast mode (quick but not fantastic recommendations)
-s slow mode (slower, but hopefully better, method for generating recommendations)
If neither -f nor -s is specified, the default is to use both and compare the results.

'''

    print(message, file=sys.stderr)
    sys.exit(1)

# Function to turn known letters into a compiled regex for word matching/elimination
def buildRegex(known):
    green="....."
    yellow=""
    grey=""
    regex=""
    for clue in known:
        if not re.match('^[a-z]{5}:[gyxe]{5}$', clue):
            usage()

        for lpos in range(5):       # Letter position
            rpos = lpos+6           # Result position
        
            if clue[rpos] == 'g':
                green = green[:lpos] + clue[lpos] + green[lpos+1:]
            
            elif clue[rpos] == 'y':
                yellow += "(?=.*" + clue[lpos] + ")(?!" + ("."*lpos) + clue[lpos] + ("."*(4-lpos)) + ")"
            
            elif clue[rpos] == 'x':
                grey += "(?!.*" + clue[lpos] + ")"

            elif clue[rpos] == 'e':
                pass                # We're in easy mode, so this position is not imposing a constraint

            else:
                usage()     # Shouldn't really be possible to get here

    regex = "^" + yellow + grey + green + "$"
    # print("Debug: regex is", regex)
    return re.compile(regex)

# Filter guesslist in easy mode, where we don't have to respect yellow & green results
def buildEasyRegex(known):
    myknown = [ clue[:6] + re.sub('[yg]', 'e', clue[6:]) for clue in known ]
    return buildRegex(myknown)

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
def method1(trylist, wordlist, known):

    # When converting to a score, the aim is to bisect the option space, so closest to 50% match is best
    goal = len(wordlist)/2

    # Which letters are known vs unknown? Need to pull out the greens from our clues
    unfixed = [i for i in range(5)]
    fixed = {}
    for clue in known:
        for pos in range(6,11):
            if clue[pos] == 'g':
                fixed[pos-6] = 1
    for f in fixed.keys():
        unfixed.remove(f)

    if len(unfixed) == 0:
        print("Duh... wut? We already know the answer.", file=sys.stderr)
        sys.exit(1)

    # Find letter frequencies in the unfixed positions
    positions={}
    for pos in unfixed:
        positions[pos]={ l:0 for l in string.ascii_lowercase }
        for word in wordlist:
            positions[pos][word[pos]]+=1

    for pos in positions.keys():
        for char in positions[pos].keys():
            positions[pos][char] = abs(positions[pos][char] - goal)/goal     # Normalize to distance from being a perfect bisector

    # Sum up the total distance for each candidate next-guess
    m1dict={}
    for word in trylist:
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

    scale = len(trylist) * len(wordlist) / 10**5        # If this is large (>10^5) search space, we'll do a bit of extra logging

    for guessword in trylist:

        if scale>1:
            if cnt>0:
                avetime = 1000*(time.time() - starttime)/cnt
                esttime = (len(trylist)-cnt)*avetime/60000
                print(f"PID {pid}: {cnt}/{len(trylist)}   Average {avetime:8.2f}ms   Remaining {esttime:4.1f} mins")
            else:
                print(f"PID {pid} initialized - let the crunching commence!")

        guesswordscore = 0

        # One of the words in wordlist must be the true answer. Evaluate guessword against each, and see what the resulting solution space would be.
        for trueword in wordlist:
            # print("Debug: guessword",guessword,"against trueword",trueword)

            # Maybe we got lucky...
            if guessword == trueword:   
                continue                    # Don't add anything to the solution space count, as we found it

            # If not, then the resulting pattern updates would be...
            newknown = guessword + ':'
            for pos in range(5):
                g = guessword[pos]
                t = trueword[pos]
                if g == t:
                    newknown += 'g'
                elif g in trueword:
                    newknown += 'y'
                else:
                    newknown += 'x'
            # print("Debug: new knowns are",newknown)
            newregex = buildRegex(known+[newknown])

            # ...and count how many words that would remove
            kills = filterWords(wordlist, newregex, justCount=True)

            # The score is the size of the remaining wordlist
            guesswordscore += (len(wordlist) - kills) / len(wordlist)
            # print("Debug: guessword",guessword,"against trueword",trueword,"scores",guesswordscore)

        # (end of trueword loop)

        # We can now calculate the average tree depth under guessword
        guesswordscore /= len(wordlist)
        m2dict[guessword] = guesswordscore
        cnt += 1 

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
    goal = len(wordlist)/2
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

# Method 2 - see how a each guessword would reduce the solution space
def methodblind(trylist, wordlist, known, firstguess):

    mybdict={}
    cnt=0
    pid=os.getpid()
    starttime=time.time()

    scale = len(trylist) * len(wordlist) / 10**5        # If this is large (>10^5) search space, we'll do a bit of extra logging

    for secondguess in trylist:

        if scale>1:
            if cnt>0:
                avetime = 1000*(time.time() - starttime)/cnt
                esttime = (len(trylist)-cnt)*avetime/60000
                print(f"PID {pid}: {cnt}/{len(trylist)}   Average {avetime:8.2f}ms   Remaining {esttime:4.1f} mins")
            else:
                print(f"PID {pid} initialized - let the crunching commence!")

        guesswordscore = 0

        # One of the words in wordlist must be the true answer. Evaluate guesses against each, and see what the resulting solution space would be.
        for trueword in wordlist:
            # print("Debug: guesses",firstguess,secondguess,"against trueword",trueword)

            # Maybe we got lucky...
            if firstguess == trueword or secondguess == trueword:   
                continue                    # Don't add anything to the solution space count, as we found it

            # If not, then the resulting pattern updates would be...
            updates=[]
            for guessword in [firstguess, secondguess]:
                newknown = guessword + ':'
                for pos in range(5):
                    g = guessword[pos]
                    t = trueword[pos]
                    if g == t:
                        newknown += 'g'
                    elif g in trueword:
                        newknown += 'y'
                    else:
                        newknown += 'x'
                updates.append(newknown)
            # print("Debug: new knowns are",newknown)
            newregex = buildRegex(known+updates)

            # ...and count how many words that would remove
            kills = filterWords(wordlist, newregex, justCount=True)

            # The score is the size of the remaining wordlist
            guesswordscore += (len(wordlist) - kills) / len(wordlist)
            # print("Debug: guesses",firstguess,secondguess,"against trueword",trueword,"scores",guesswordscore)

        # (end of trueword loop)

        # We can now calculate the average tree depth under this guess-pair
        guesswordscore /= len(wordlist)
        mybdict['+'.join([firstguess,secondguess])] = guesswordscore
        cnt += 1 

    return mybdict



#### MAIN
if __name__ == '__main__':

    # Read commandline arguments
    argv = sys.argv[1:]
    try:
        opts, args = getopt.gnu_getopt(argv, "w:g:n:fseb:")
    except:
        usage()

    known = [x.lower() for x in args]        # Remaining options after parsing out the getopt params
    wordlist_filename = "allowed_solutions.txt"
    # guesslist_filename = "allowed_guesses.txt"      # This list contains guesses permitted by Wordle. Much larger than the words it actually picks solutions from.
    guesslist_filename = ""
    n = 1
    fast = True 
    slow = True
    easy = False 
    blind = False

    for opt,arg in opts:
        if opt == '-w':
            wordlist_filename = arg
        if opt == '-g':
            guesslist_filename = arg
        if opt == '-n':
            n = int(arg)
        if opt == '-f':
            slow = False
        if opt == '-s':
            fast = False
        if opt == '-e':
            easy = True
        if opt == '-b':
            blind = arg.lower()

    if not fast and not slow:
        fast = True 
        slow = True
    if guesslist_filename == "":
        guesslist_filename = wordlist_filename

    # Read and filter the word list, based on the supplied inputs, to get candidate words
    swords = readListFromFile(wordlist_filename)
    gwords = readListFromFile(guesslist_filename)
    sregex = buildRegex(known)
    if easy:
        gregex = buildEasyRegex(known)
    else:
        gregex = sregex
    filterWords(swords, sregex)
    filterWords(gwords, gregex)


    # Display possible solutions
    if len(swords)==1:
        print("The only solution is", swords[0])
        sys.exit(0)
    elif len(swords)==2:
        print("Two possible solutions:", swords)
        sys.exit(0)
    elif len(swords)>20 and not n==0:
        print("There are", len(swords), "candidate solutions, including gems such as",random.choice(swords),"and",random.choice(swords))
    elif len(swords)==0:
        print("No possible solutions found. We're gonna need a bigger wordlist.")
        sys.exit(0)
    else:
        print("\nCandidate words:")
        print("\n".join(swords))


    # ------- Part 2: suggest a good (possibly optimal?) next guess ---------
    if blind:
        ### Niche requirement: come up with the best two guesses for any scenario, as a standard tactic for otherwise unassisted games
        bdict={}
        
        # This part can take a while, so let's play with multi-processing.
        cores = mp.cpu_count()
        mypool = mp.Pool(processes=cores)
        l = len(gwords)
        wordslices = [gwords[int(l*(i/cores)):int(l*((i+1)/cores))] for i in range(cores)]
        results = mypool.starmap(methodblind, [(wordslices[i], swords, known, blind) for i in range(cores)])
        for res in results:
            bdict.update(res)

        bbestwords = sorted(bdict.items(), key=operator.itemgetter(1), reverse=False)

        print("\nBest guesses:")
        for w in bbestwords[0:n]:
            print(w[0],"scored",w[1])
        sys.exit(0)


    if fast:
        ### Method 1: somewhat naive heuristic, aiming to hit greens (basically ignores yellows, so probably not optimal)
        m1start = time.time()
        m1dict=method1(gwords, swords, known)
        m1bestwords = sorted(m1dict.items(), key=operator.itemgetter(1), reverse=False)
        m1end = time.time()

        print("\nFor the next guess, method 1 suggests that you try",m1bestwords[0][0])
        if n>1:
            print("\nOther reasonable options:")
            for w in m1bestwords[1:n]:
                print(w[0])

        ### Method 3: treats yellows and greens equally, also not really optimal
        m3start = time.time()
        m3dict=method3(gwords, swords)
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
        
        # This part can take a while, so let's play with multi-processing.
        cores = mp.cpu_count()
        mypool = mp.Pool(processes=cores)
        l = len(gwords)
        wordslices = [gwords[int(l*(i/cores)):int(l*((i+1)/cores))] for i in range(cores)]
        results = mypool.starmap(method2, [(wordslices[i], swords, known) for i in range(cores)])
        for res in results:
            m2dict.update(res)

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

