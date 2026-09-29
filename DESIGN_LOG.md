# DESIGN_LOG.md

One entry per working session. Only write things that really happened. The assignment needs
**at least three** specific occasions where AI gave something wrong, slow or incomplete
(what the problem was, how you found it). So far this log has **one** real one. Add the others
as you find them while you read, run and question this code (see the checklist at the bottom).

## 2026-09-27: first working session with Claude (AI assistant)

**Goal:** get a complete first version of the whole project (tokenizer, parser, tree printer,
six operators, errors, generator, benchmark, tests, docs) using the simplest design.

**What was done:** Claude chose pure Python, a package split (tokenizer / parser / nodes /
relation / operators), contextual keywords for case 8, and the precedence levels in GRAMMAR.md.
All 25 required cases plus extras were turned into `tests/test_cases.py` and pass.

**Where the AI was wrong (real):**

1. *Runtime estimate.* Before writing any code, Claude told me the 64000 x 64000 nested-loop
   join "could take hours" in Python and suggested a faster language or an overnight run. After
   the join was written, a smoke test measured about 16 million comparisons per second in Claude's
   sandbox (4000 x 4000 in about 1.1 s), so the estimate was far too pessimistic for that
   environment. Lesson: measure before planning around a guess. My own machine will differ; my
   own timings go in REPORT.md.

**What broke / still open:**

* (fill in: anything that broke when I ran or changed the code myself)

## Checklist for finding more real AI mistakes (do these yourself, then log what you find)

* Read `test_15` against the assignment: case 15 as written gives the same result with or
  without the parentheses under my precedence rules, so Claude added a second assertion.
  Decide whether the test suite really proves what case 15 wants.
* Try a few queries the tests do not cover (nested parentheses in conditions, `A times B times C`,
  numbers like `3.5` and `-0`, a relation whose name is `select`) and log any wrong result
  or bad error message.
* Check every claim in GRAMMAR.md (for example the LL(1) claim in 5.4) against the parser code,
  and log anything overstated.
* Run `--stats` and confirm the join counter equals n*m in the benchmark; log if it does not.
