# GRAMMAR.md

Everything in this file matches `raengine/tokenizer.py` and `raengine/parser.py`.
Rule names below are the names of the parser methods (`parse_expr`, `parse_term`, ...).

## 5.1 The grammar (EBNF)

`{ x }` means zero or more repetitions, `[ x ]` means optional, `|` is choice,
quoted text is a literal token.

### Queries

```ebnf
query      ::= expr EOF

expr       ::= term   { ( "union" | "minus" ) term }          (* level 1, left assoc *)
term       ::= factor { "intersect" factor }                  (* level 2, left assoc *)
factor     ::= unit   { ( "times" | "join" "[" cond "]" ) unit }  (* level 3, left assoc *)

unit       ::= "select"  "[" cond "]" "(" expr ")"
             | "project" "[" attrref { "," attrref } "]" "(" expr ")"
             | "rename"  "[" IDENT "]" "(" expr ")"
             | "(" expr ")"
             | IDENT                                          (* a relation name *)

cond       ::= andcond { "or" andcond }                       (* lowest *)
andcond    ::= notcond { "and" notcond }
notcond    ::= "not" notcond
             | "(" cond ")"
             | comparison                                     (* highest *)

comparison ::= operand CMP operand
operand    ::= NUMBER | STRING | attrref
attrref    ::= IDENT [ "." IDENT ]
CMP        ::= "=" | "!=" | "<" | "<=" | ">" | ">="
```

### Tokens (scanned by hand, character by character)

```ebnf
IDENT   ::= letter { letter | digit | "_" }          (* letter includes "_" *)
NUMBER  ::= [ "-" ] digit { digit } [ "." digit { digit } ]
STRING  ::= "'" { any-char-except-quote | "''" } "'"  (* '' is one literal quote *)
```

Whitespace between tokens is skipped and never required. Symbols are
`( ) [ ] , . = != < <= > >=`. Maximal munch is used for `<`, `>` and `!`: after
reading `<` or `>` the scanner looks at the next character and produces `<=` / `>=` if it
is `=`. A `-` starts a number only if a digit follows it immediately, so `Age>-30`
is `Age`, `>`, `-30` and no `>-` operator exists.

### Relation definitions

```ebnf
file       ::= { relation-def }
relation-def ::= IDENT "(" IDENT { "," IDENT } ")" "=" "{" NEWLINE
                 { tuple NEWLINE }
                 "}"
tuple      ::= value { "," value }
value      ::= NUMBER | STRING | BARE
BARE       ::= one or more characters, none of which is  ,  (  )  '  or whitespace
```

Lines starting with `//` and blank lines are ignored. A `BARE` value that looks like a number
is a number; any other `BARE` is a string; a `STRING` (quoted) is always a string, even `'30'`.
Duplicate tuples collapse (a relation is a set).

### Keywords are contextual (case 8)

The scanner produces `IDENT` for every word. The parser treats a word as a keyword only
where the grammar expects one:

* `union minus intersect times join` are operators only in the position right after a complete
  `unit` (`parse_expr`, `parse_term`, `parse_factor`). In an operand position any word is a name.
* `and`, `or` are operators only right after a complete comparison / condition.
* `select`, `project`, `rename` start an operator only if the next token is `[`.
* `not` is the negation operator unless the next token is a comparison operator or `.`;
  then it is an attribute named `not` (`select[not=3](R)` compares an attribute called `not`).

So `select[union=3](R)` parses: after `[` the parser expects a condition, reads the operand
`union`, then sees `=`. Keywords are case sensitive and lowercase.

## 5.2 Precedence and associativity

| Level | Operators | Associativity | Enforced by rule |
|---|---|---|---|
| 1 (loosest) | `union`, `minus` | left | `expr` |
| 2 | `intersect` | left | `term` |
| 3 (tightest) | `times`, `join[c]` | left | `factor` |
| — | `select`, `project`, `rename`, `( )` | prefix, parenthesised input | `unit` |

Conditions:

| Level | Operator | Associativity | Rule |
|---|---|---|---|
| 1 (loosest) | `or` | left | `cond` |
| 2 | `and` | left | `andcond` |
| 3 (tightest) | `not` | prefix | `notcond` |

The precedence lives in the grammar: each level is its own rule that calls the next tighter rule.
There are no special cases in the parser for grouping.

Decisions and why:

* `A union B minus C` = `(A union B) minus C`, because `union` and `minus` share a level and the
  level is left associative.
* `A minus B minus C` = `(A minus B) minus C`.
* `intersect` binds tighter than `union`/`minus`, as in SQL.
* `times` and `join` bind tightest: they behave like multiplication, `union` like addition.
* `not` binds tighter than `and`, which binds tighter than `or`.

Printed trees (`python ra.py --tree ...`) for the two required cases:

```
A union B minus C          A minus B minus C
Minus                      Minus
├── Union                  ├── Minus
│   ├── Relation(A)        │   ├── Relation(A)
│   └── Relation(B)        │   └── Relation(B)
└── Relation(C)            └── Relation(C)
```

Data where the other grouping of `A minus B minus C` gives a different answer:
`A = {1}`, `B = {1}`, `C = {1}`.
`(A minus B) minus C = {} minus {1} = {}`, but `A minus (B minus C) = {1} minus {} = {1}`.

## 5.3 Ambiguity demonstration

The deliberately naive grammar:

```ebnf
Expr ::= Expr "union" Expr
       | Expr "minus" Expr
       | "(" Expr ")"
       | IDENT
```

The input `A union B minus C` has two different parse trees under it:

```
Tree 1: (A union B) minus C          Tree 2: A union (B minus C)

        Expr                                 Expr
   ┌──────┼──────┐                    ┌───────┼───────┐
  Expr  "minus"  Expr                Expr  "union"   Expr
   │              │                   │          ┌────┼─────┐
 ┌─┼─────┐       C                    A        Expr "minus" Expr
Expr "union" Expr                               │            │
 │            │                                 B            C
 A            B
```

Concrete relations where they disagree. Let `A`, `B`, `C` each have one attribute `x`:
`A = {1}`, `B = {1}`, `C = {1}`.

* Tree 1: `(A union B) minus C = {1} minus {1} = {}`
* Tree 2: `A union (B minus C) = {1} union {} = {1}`

Two different results from the same input, so the grammar is ambiguous (it does not determine a
single meaning). The same happens for `A minus B minus C`.

The stratified (unambiguous) grammar, in its natural left-recursive form:

```ebnf
Expr   ::= Expr "union" Term | Expr "minus" Term | Term
Term   ::= Term "intersect" Factor | Factor
Factor ::= Factor "times" Unit | Unit
Unit   ::= "(" Expr ")" | IDENT
```

`union` and `minus` sit on the same level and the left operand is `Expr` (the recursion is on the
left), so the right operand can only be a `Term`, never another `union`/`minus` expression
without parentheses. For `A union B minus C` the only derivation is
`Expr → Expr minus Term`, with the inner `Expr → Expr union Term`. That forces **Tree 1**,
`(A union B) minus C`. Tree 2 would need `B minus C` as the right operand of `union`, which is an
`Expr`, but `union` only accepts a `Term` there.

## 5.4 Parsing strategy

I used a hand-written **recursive descent** parser (one method per rule, one token of lookahead,
plus a second token of lookahead only for `select[`/`not=` decisions).

Left recursion: a recursive descent method for `Expr ::= Expr "union" Term | ...` would call
itself first, before consuming any token, and recurse forever. The fix is to rewrite the rule as
iteration:

```
Expr ::= Term { ("union" | "minus") Term }
```

The exact place is `parse_expr` in `raengine/parser.py` (same for `parse_term`, `parse_factor`,
`parse_cond`, `parse_and`). The loop starts with `left = parse_term()`, and each iteration wraps
the tree built so far as the left child of the new node:
`left = Node(op, left=left, right=parse_term())`. Building the tree inside the loop is what makes
the operators **left associative**, even though the EBNF only says "repeat".

Why recursive descent: the grammar is LL(1) after removing left recursion (apart from the two
contextual keyword decisions above), the code maps one-to-one onto the grammar, and error
messages can name exactly what was expected at the position where parsing failed.

## 5.5 Sources

**TODO before submitting (write these yourself, they must be true):**

* What I actually read (for example: Crafting Interpreters chapters on scanning and parsing,
  Wikipedia on EBNF, recursive descent, maximal munch, operator precedence, Dragon Book 2.2 to 2.4).
* Where the AI was wrong or incomplete while I worked. See also DESIGN_LOG.md.
