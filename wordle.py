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
import math


def usage():
    progname = sys.argv[0]
    message = f'''
Wordle Hinter: find words that might fit a Wordle puzzle.

Usage:
    {progname} [-e] [-w wordlist] [-g guesslist] [-r] [-n N] [-a] [word1:result1 word2:result2 ...]

The 'result' pattern should use characters g, y & x:
    g = green (correct letter in the correct position)
    y = yellow (the letter is present in the word but not in that position) 
    x = grey (the letter not present in the word) 
For example: 'amaze:yxgxg'

Word:result inputs are not case sensitive, although the flags (-r, -n etc) are. 

If no word:result patterns are specified, attempt to calculate the optimal first guess.

-e              enables 'Easy mode'

-w <wordlist>   overrides the default list of possible solutions
-g <guesslist>  overrides the default list of allowed guesses
-r              reuses the solution wordlist as the guesslist (equivalent to -g <wordlist>) 

-s <guess>      prints the score for <guess> as the next guess, against the best score in <guesslist>
-n <N>          prints the best N options for the next guess, with scores

-a              prints all possible solution words

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
        if not re.match('^[A-Z]{5}:[GYXE]{5}$', clue):
            usage()

        for lpos in range(5):       # Letter position
            rpos = lpos+6           # Result position
        
            if clue[rpos] == 'G':
                green = green[:lpos] + clue[lpos] + green[lpos+1:]
            
            elif clue[rpos] == 'Y':
                yellow += "(?=.*" + clue[lpos] + ")(?!" + ("."*lpos) + clue[lpos] + ("."*(4-lpos)) + ")"
            
            elif clue[rpos] == 'X':
                grey += "(?!.*" + clue[lpos] + ")"

            elif clue[rpos] == 'E':
                pass                # We're in easy mode, so this position is not imposing a constraint

            else:
                usage()     # Shouldn't really be possible to get here

    regex = "^" + yellow + grey + green + "$"
    # print("Debug: regex is", regex)
    return re.compile(regex)

# Filter guesslist in easy mode, where we don't have to respect yellow & green results
def buildEasyRegex(known):
    myknown = [ clue[:6] + re.sub('[YG]', 'E', clue[6:]) for clue in known ]
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
def readListFromFile(filename):
    if not ( os.path.isfile(filename) and os.access(filename, os.R_OK) ):
        print("Could not read file",filename, file=sys.stderr)
        sys.exit(3)
    fh = open(filename,"r")
    words = []
    for line in fh.readlines():
        w = line.rstrip().upper()
        words.append(w)
    fh.close()
    return words


# Rank guesses according to the expected entropy 
def rankGuesses(guesslist, solutionlist, known):

    guessscores={}
    cnt=0
    pid=os.getpid()
    starttime=time.time()

    scale = len(guesslist) * len(solutionlist) / 10**5        # If this is large (>10^5) search space, we'll do a bit of extra logging

    for guessword in guesslist:

        if scale>1:
            if cnt>0:
                avetime = 1000*(time.time() - starttime)/cnt
                esttime = (len(guesslist)-cnt)*avetime/60000
                print(f"PID {pid}: {cnt}/{len(guesslist)}   Average {avetime:8.2f}ms   Remaining {esttime:4.1f} mins")
            else:
                print(f"PID {pid} initialized - let the crunching commence!")

        guesswordscore = 0

        # Information theory: estimate the entropy of this guessword by calculating -SUM[ P(x).log2(P(x)) ] over all outcomes x.
        # x is an outcome pattern (e.g. 'GXYXY') for a particular guess.
        counter = {}
        for sword in solutionlist:
            result = ''
            for pos in range(5):
                if sword[pos] == guessword[pos]:
                    result += 'G'
                elif sword[pos] in guessword:
                    result += 'Y'
                else:
                    result += 'X'
            if result in counter:
                counter[result] += 1
            else:
                counter[result] = 1
        
        for outcome in counter.keys():
            probability = counter[outcome] / len(solutionlist)
            guesswordscore -= probability * math.log(probability,2)
        
        guessscores[guessword] = guesswordscore
        cnt += 1 

    return guessscores


#### MAIN
if __name__ == '__main__':

    # Read commandline arguments
    argv = sys.argv[1:]
    try:
        opts, args = getopt.gnu_getopt(argv, "w:g:n:e:ras:")
    except:
        print('Failed to parse inputs correctly')
        usage()

    known = [x.upper() for x in args]        # Remaining options after parsing out the getopt params
    wordlist_filename = "allowed_solutions.txt"
    guesslist_filename = "allowed_guesses.txt"      # This list contains guesses permitted by Wordle. Much larger than the words it actually picks solutions from.
    n = 1
    easy = False 
    reuse_wordlist_for_guesslist = False
    showall = False
    showscore = False

    for opt,arg in opts:
        if opt == '-w':
            wordlist_filename = arg
        if opt == '-g':
            guesslist_filename = arg
        if opt == '-n':
            n = int(arg)
        if opt == '-e':
            easy = True
        if opt == '-a':
            showall = True
        if opt == '-r':
            reuse_wordlist_for_guesslist = True
        if opt == '-s':
            showscore = arg.rstrip().upper()

    if reuse_wordlist_for_guesslist:
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
        print("Only two possible solutions:", swords[0], "and", swords[1])
        sys.exit(0)
    elif len(swords)>20 and not showall:
        print("There are", len(gwords),"valid guesses available. There are",len(swords), "candidate solutions, including gems such as",random.choice(swords),"and",random.choice(swords))
    elif len(swords)==0:
        print("No possible solutions found. We're gonna need a bigger wordlist.")
        sys.exit(0)
    else:
        print("\nThere are",len(gwords),"valid guesses available. There are",len(swords),"candidate solutions:")
        print("\n".join(swords))


    # ------- Part 2: suggest a good (possibly optimal?) next guess ---------
    guessdict={}        
    
    # This part can take a while, so let's play with multi-processing.
    cores = mp.cpu_count()
    mypool = mp.Pool(processes=cores)
    l = len(gwords)
    wordslices = [gwords[int(l*(i/cores)):int(l*((i+1)/cores))] for i in range(cores)]
    results = mypool.starmap(rankGuesses, [(wordslices[i], swords, known) for i in range(cores)])
    for res in results:
        guessdict.update(res)

    bestwords = sorted(guessdict.items(), key=operator.itemgetter(1), reverse=True)

    # Bias in favour of guesses that are possible solutions, if the entropy scores are equal.
    if bestwords[0][0] in swords:
        print("For the next guess, try",bestwords[0][0])
    else:
        i=1
        while not bestwords[i][0] in swords:
            i+=1
        if bestwords[0][1] == bestwords[i][1]:
            print("For the next guess, try",bestwords[i][0])
        else:
            print(f"The best guess in your guess list is {bestwords[0][0]}, with a score of {bestwords[0][1]:1.4f}")
            print("That's not in the solution list, though.")
            print(f"The best guess in the solution list is {bestwords[i][0]}, with a score of {bestwords[i][1]:1.4f}")

    # Print the scores of the top N guesses (if -n was specified on the command line)
    if n>1:
        print("\nRanked options:")
        for i in range(min(n, len(bestwords))):
            if bestwords[i][0] in swords:
                highlight = ' - valid solution'
            else:
                highlight = ''
            print(f'{i+1:3n}: {bestwords[i][0]} (score: {bestwords[i][1]:1.4f}){highlight}')

    # Show the score of the specific word queried in the -s parameter, if present
    if showscore:
        if showscore in gwords:
            i=0
            while not bestwords[i][0] == showscore:
                i+=1
            if bestwords[0][1] > guessdict[showscore]:
                print(f'{showscore} would score {guessdict[showscore]:1.4f}, and ranks {i+1} out of {len(gwords)} valid guesses. The top guess {bestwords[0][0]} scored {bestwords[0][1]:1.4f}.')
            else:
                print(f'{showscore} would score {guessdict[showscore]:1.4f}, which is as good as it gets! Top guess!')
        else:
            print(showscore,"is not a valid guess.")