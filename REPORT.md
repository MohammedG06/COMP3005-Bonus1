# REPORT.md: performance study

> **This file is a skeleton.** Every number must come from *your* run on *your* machine
> (the professor will ask where each number came from). Steps:
>
> 1. `python benchmark.py` (all sizes; resumable, writes `results.csv`)
> 2. `python benchmark.py --match-study 4000`
> 3. `python analyze.py` (prints all the tables, slopes and the prediction arithmetic; writes `loglog.png`)
> 4. Paste the tables in, then write each answer in your own words, based on your numbers.
>
> Delete this note when done.

## Setup

* Machine: `<CPU model, RAM, OS>`
* Language and version: `<e.g. Python 3.x>` (`python --version`)
* Query: `R join[R.b=S.b] S`, data from `gen.py` (R(a, b), S(b, c), match rate 1, seed 0)
* Timing covers evaluation of the parse tree only (not parsing, data generation or printing).

## Table (join, match rate 1)

| n | m | comparisons | wall time (s) | output tuples |
|---|---|---|---|---|
| 1000 | 1000 | | | |
| 2000 | 2000 | | | |
| 4000 | 4000 | | | |
| 8000 | 8000 | | | |
| 16000 | 16000 | | | |
| 32000 | 32000 | | | |
| 64000 | 64000 | | | |

## Questions

**1. Relationship between n, m and the comparison count.**
(Formula? Does every row match it exactly? If not, why not? Hint: check how the counter is
incremented in `operators.py` and whether the generator can produce duplicate tuples.)

**2. Log-log plot of time against n.** Insert `loglog.png`.
Slope from `analyze.py`: `<slope>`. What does that slope say about the algorithm?
(Hint: what slope does time proportional to n^k give?)

**3. Select and project at the same sizes.**
(Paste the select/project table from `analyze.py`. How do the slopes differ from the join, and why?
Think about how many times each operator touches each input tuple.)

**4. Prediction for one million tuples per side (do not run it).**
(Show the arithmetic printed by `analyze.py`: comparisons = n*m, seconds per comparison from your
largest run, and the product. Say which of the two predictions you trust more and why, and what
could make the real number differ, for example memory and cache effects.)

**5. Does changing the match rate change the comparison count? The wall time?**
(Paste the match-rate table from `python benchmark.py --match-study 4000`. Explain why the two
answers differ: what does the join do differently when a pair matches?)

**6. What would you change to make the million-tuple join feasible?** (One paragraph. You do
not have to implement it. Hash join, sort-merge join, indexes; say what each changes about the
number of comparisons.)
