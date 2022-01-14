# WordleHint
Cheat at Wordle.


How to use:

Wordle starts with a blank 5-character word. We might guess 'SORES' first. The result is this:

![.](https://via.placeholder.com/40/444444/FFFFFF?text=S) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=O) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=R) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=E) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=S)

So we know that there is an E in the fourth position, and that the letters S, O and R do not appear.

We can now use WordleHint:
$ ./wordle.py -g '...e.' -e 'sor'

Here we have specified the green squares (-g) as four unknowns (.) plus an 'e' in position 4, and the eliminated letters (-e) as s, o & r. Note that upper/lower case doesn't matter. 

The output tells us that there are now 238 possible words, and our next guess should be 'LAVED'. 

![.](https://via.placeholder.com/40/444444/FFFFFF?text=L) ![.](https://via.placeholder.com/40/AAAA00/FFFFFF?text=A) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=V) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=E) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=D)

Now we have a yellow letter (A) and three more eliminated (L, V, D). 

$ ./wordle.py -g '...e.' -e 'sorlvd' -y 'a'

The next guess is 'WAKEN':

![.](https://via.placeholder.com/40/444444/FFFFFF?text=W) ![.](https://via.placeholder.com/40/AAAA00/FFFFFF?text=A) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=K) ![.](https://via.placeholder.com/40/00AA00/FFFFFF?text=E) ![.](https://via.placeholder.com/40/444444/FFFFFF?text=N)

No more successes, but three more eliminations: W, K & N.

$ ./wordle.py -g '...e.' -e 'sorlvdwkn' -y 'a'

We're now down to five possible words, and as it happens, the first one is correct: 'ABBEY'. 
