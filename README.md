# WordleHint
Cheat at Wordle.
Wordle is a great little online word game: https://www.powerlanguage.co.uk/wordle/

## Installation

This is a python3 script, so you need to have python3 installed. Then you can just save the files to your computer and run `wordle.py` from the command line. The word list (allowed_solutions.txt) needs to be in the same directory, unless you explicitly specify the path using -w. 

## Parameters

Command line format: `./wordle.py [options] guess1:result1 guess2:result2 ...`

A guess:result parameter should be a word already guessed, and the resulting colours (green = g, yellow = y, eliminated (black/grey) = x).

e.g. `./wordle.py aback:gyyxx`

| Option | Description |
|-----------|-------------|
| -w <> | override the wordlist for possible solutions (default is allowed_solutions.txt)|
| -g <> | specify a different guesslist (default is allowed_guesses.txt) |
| -r | reuse the solution wordlist as the guesslist (equivalent to -g allowed_solutions.txt, or whatever argument you pass to -w) |
| -e | easy mode, i.e. allow guesses that would have been ruled out by previous green/yellow results (note that Wordle defaults to easy mode, but this is clearly cheating) |
| -n <> | print the top N guesses (default is 1) |

## Usage Example

Wordle starts with a blank 5-character word. We might guess 'TARES' first. The result is this:

![.](https://via.placeholder.com/40/444444/FFFFFF?text=T) ![.](https://via.placeholder.com/40/CCAA00/FFFFFF?text=A) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=R) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=E) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=S)

So we know that there is an E in the fourth position, an A somewhere (but not in the second position), and that the letters T, R and S do not appear.

We can now use WordleHint:

`$ ./wordle.py tares:xyxgx`

Here we specified that the guess word 'tares' resulted in three eliminated letters (x's), plus a green in the fourth position and a yellow in the second. Note that upper/lower case doesn't matter.

The output tells us that there are now 7 possible words, and our next guess should be 'ALIEN'. 

![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=A) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=L) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=I) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=E) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=N)

Now we know where the A is, and we have eliminated three more letters (L, I, N). 

`$ ./wordle.py tares:xyxgx alien:gxxgx`

With the default word list, there is only one possible answer: 'ABBEY'. 

![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=A) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=B) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=B) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=E) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=Y)

We have solved today's Wordle puzzle!

## Warning

The computational workload scales with O(n^2). Each possible guess is evaluated against each possible solution. This means that that script is very fast when there are only a few possibilities (i.e. a small dictionary and/or lots of guess:result combinations that impose constraints on the solution space), but if you feed it a much larger dictionary, it may take a **LOT** longer to run.
