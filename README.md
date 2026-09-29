# Relational algebra engine (COMP 3005 Bonus Project 1)

A small relational algebra interpreter in pure Python 3 (standard library only; matplotlib is
optional and used only to draw the report plot).

## Layout

```
ra.py                 command line entry point
raengine/
  errors.py           RAError (Lexical/Syntax/Name/Schema/Type/Data) and message formatting
  tokenizer.py        hand-written scanner, maximal munch, positions on every token
  parser.py           recursive descent parser, one method per grammar rule
  nodes.py            parse-tree nodes and the tree printer
  relation.py         Relation, tuple equality (tuple_key), data-file loader
  operators.py        condition compiler, the six operators, counters
gen.py                data generator for R(a, b) and S(b, c)
benchmark.py          runs the performance study, writes results.csv
analyze.py            builds the tables, slopes and prediction from results.csv
tests/test_cases.py   the 25 required cases plus extras
data/employees.ra     sample relations
```

## Running

```
python ra.py --tree "project[Name](select[Age>30](Employees))"
python ra.py --db data/employees.ra "project[DID](Employees)"
python ra.py --db data/employees.ra --stats "Employees join[Employees.DID=Departments.DID] Departments"
python -m unittest discover -s tests -v          # run the tests
python gen.py --n 1000 --m 1000 --match 1 --out data/gen.ra
python benchmark.py                               # long: see REPORT.md
python analyze.py
```

Options: `--db FILE` (repeatable), `--tree` (print tree, do not execute), `--stats` (operator
counters and wall time), `--limit N` (tuples to print, default 100), `-f FILE` (read query from file).

## What is supported

`select`, `project`, `rename`, `union`, `intersect`, `minus`, `times`, `join[cond]` (theta join),
conditions with `= != < <= > >=`, `and`, `or`, `not`, parentheses, qualified names (`Emp.DID`),
numbers and single-quoted strings (with `''` for a literal quote). Precedence and associativity
are in GRAMMAR.md. Errors are reported in six categories (Lexical, Syntax, Name, Schema, Type,
and Data for bad relation files), with a position and a caret for query errors. No stack traces.

## Decisions on the open questions in the spec

* Keywords are contextual (case 8): see GRAMMAR.md.
* `project[Name, Name](R)` is a Schema error: a result cannot have two attributes with the same name.
* `times` and `join` qualify all output columns with the relation name. If two qualified names
  collide (for example `R times R`) it is a Schema error; use `rename`.
* Union compatibility compares attribute names (not qualifiers) and types, position by position.
* Comparing a number with a string is a Type error, checked before any tuple is read. A quoted
  `'30'` is a string, an unquoted `30` is a number.
* Tuple equality is defined in `relation.py::tuple_key` (a number never equals a string).
* Join is a nested loop over every pair; the condition is evaluated on every pair. It is
  "times then select" semantically, but pairs are tested as they are generated so the full
  product is never stored.

## Why the self join in case 20 needs `rename`

`Emp join[Emp.MgrID=Emp.EID] Emp` has two inputs that both call their columns `Emp.EID`,
`Emp.MgrID`, and so on. The output would have two columns with the same qualified name, and the
condition `Emp.MgrID=Emp.EID` cannot say which copy of `Emp` each side refers to, so the engine
rejects it (Schema error). Attribute names only distinguish columns through their relation
qualifier; without `rename[E2](Emp)` there is no way to give the second copy a different qualifier,
so "an employee joined with their manager" cannot be written.

## Known limitations

* Everything is in memory; no nulls; no optimisation; nested-loop join only (by design).
* Keywords must be lowercase. Numbers are int or float; `3` and `3.0` are equal.
* Relation files need one tuple per line and `{` on the header line.
* Pure Python is slow for the largest join (4.1 billion comparisons at 64000 x 64000).
