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

* Nothing broke when running the generated tests as-is — all 33 passed on first run. Real
  gaps only surfaced later, once I started testing inputs beyond the required 25 cases (see
  the 2026-09-29 entry below).

## 2026-09-29: testing edge cases in the tokenizer

**Goal:** find real gaps by throwing unusual inputs at the tokenizer, since the required
test cases all pass and don't reveal much on their own.

**Where the AI was wrong (real, #2):** `select[Age>3.](R)` produces a "Syntax error:
missing ']' ... found '.'" message. That's technically accurate — the number `3.` isn't
valid (a decimal point needs at least one digit after it, so the tokenizer only consumes
`3` and leaves the `.` as leftover) — but the message is misleading: it makes it sound like
a missing bracket rather than a malformed number. A clearer message would flag the trailing
decimal point directly. I found this by deliberately testing unusual-looking numbers, not
from any of the 25 required cases.

**Where the AI was wrong (real, #3):** `select[Age>--5](R)` fails with "Lexical error:
unexpected character '-'". The real reason is that the grammar has no standalone unary minus
operator — a `-` is only ever recognized as the start of a negative number literal, and only
when a digit immediately follows it. Since the first `-` in `--5` is followed by another `-`,
not a digit, it falls through every rule in the tokenizer and errors. The message is accurate
but doesn't explain *why* — a reader has no way to guess "there's no unary minus" from
"unexpected character". This is a genuine design gap (not just a bug): negative numbers can
only appear as literals directly after a comparison operator, never as a general expression.
I found this by testing a double-negative, which isn't covered by any required test case.

**What broke / still open:** neither of these is fixed in the code — both are documented
limitations now. Could improve the tokenizer's error messages to name the real problem
(malformed number, or "no unary minus operator") instead of the generic message, but that's
optional polish, not required by the spec.

## Checklist used to find the entries above

I worked through the suggested checklist (testing queries beyond the 25 required cases,
checking error messages for accuracy, testing `--times--` on relations, and unusual number
formats) to find the two extra AI mistakes logged on 2026-09-29.