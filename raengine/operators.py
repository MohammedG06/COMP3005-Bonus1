"""Bottom-up evaluation of the parse tree, plus the six operators.

The tree is executed exactly as written (no optimisation, no rewriting).
Conditions are compiled once per operator into closures f(a, b) with attribute
positions already resolved, so no name lookup happens per tuple. No eval/exec.
  select: f(row, None)         join: f(left_row, right_row)
"""

import operator

from .errors import RAError
from .relation import Relation, dedupe, tuple_key

OPS = {"=": operator.eq, "!=": operator.ne, "<": operator.lt,
       "<=": operator.le, ">": operator.gt, ">=": operator.ge}
TYPE_WORD = {"num": "number", "str": "string"}


class Stats:
    """Counters. Each operator increments its own."""

    def __init__(self):
        self.select_evals = 0       # once per tuple a selection condition is evaluated on
        self.join_comparisons = 0   # once per pair a join condition is evaluated on
        self.times_pairs = 0        # pairs produced by times
        self.project_tuples = 0     # input tuples read by project

    def __str__(self):
        return (f"select_evals={self.select_evals} join_comparisons={self.join_comparisons} "
                f"times_pairs={self.times_pairs} project_tuples={self.project_tuples}")


# ---- name resolution -------------------------------------------------------
def _qname(col):
    return f"{col[0]}.{col[1]}"


def resolve(cols, attr):
    label = f"{attr.qual}.{attr.name}" if attr.qual else attr.name
    hits = [i for i, (r, n) in enumerate(cols) if n == attr.name and (attr.qual is None or r == attr.qual)]
    if not hits:
        raise RAError("Name", f"unknown attribute '{label}' (available: {', '.join(_qname(c) for c in cols)})", attr.pos)
    if len(hits) > 1:
        raise RAError("Name", f"attribute '{label}' is ambiguous; qualify it, e.g. "
                              f"{' or '.join(_qname(cols[i]) for i in hits)}", attr.pos)
    return hits[0]


# ---- condition compiler ----------------------------------------------------
def compile_cond(c, cols, types, nl):
    """nl = number of columns that come from the left tuple (all of them for select)."""
    k = c.kind
    if k == "And":
        f, g = compile_cond(c.left, cols, types, nl), compile_cond(c.right, cols, types, nl)
        return lambda a, b: f(a, b) and g(a, b)
    if k == "Or":
        f, g = compile_cond(c.left, cols, types, nl), compile_cond(c.right, cols, types, nl)
        return lambda a, b: f(a, b) or g(a, b)
    if k == "Not":
        f = compile_cond(c.child, cols, types, nl)
        return lambda a, b: not f(a, b)

    def operand(o):
        if o.kind == "Attr":
            i = resolve(cols, o)
            return ("attr", i, types[i])
        if o.kind == "Num":
            return ("const", o.value, "num")
        return ("const", o.value, "str")

    L, R = operand(c.left), operand(c.right)
    if L[2] != "any" and R[2] != "any" and L[2] != R[2]:
        raise RAError("Type", f"cannot compare a {TYPE_WORD[L[2]]} with a {TYPE_WORD[R[2]]} "
                              f"({_describe(c.left)} {c.op} {_describe(c.right)})", c.pos)
    opf = OPS[c.op]

    if L[0] == "attr" and R[0] == "attr":
        i, j = L[1], R[1]
        if i < nl and j >= nl:
            j -= nl
            return lambda a, b: opf(a[i], b[j])
        if i >= nl and j < nl:
            i -= nl
            return lambda a, b: opf(b[i], a[j])
        if i < nl:
            return lambda a, b: opf(a[i], a[j])
        i -= nl
        j -= nl
        return lambda a, b: opf(b[i], b[j])
    if L[0] == "attr":
        i, v = L[1], R[1]
        if i < nl:
            return lambda a, b: opf(a[i], v)
        i -= nl
        return lambda a, b: opf(b[i], v)
    if R[0] == "attr":
        i, v = R[1], L[1]
        if i < nl:
            return lambda a, b: opf(v, a[i])
        i -= nl
        return lambda a, b: opf(v, b[i])
    const = opf(L[1], R[1])
    return lambda a, b: const


def _describe(o):
    if o.kind == "Attr":
        return f"{o.qual}.{o.name}" if o.qual else o.name
    if o.kind == "Num":
        return str(o.value)
    return "'" + o.value + "'"


# ---- schema helpers --------------------------------------------------------
def product_schema(left, right, node):
    cols = left.cols + right.cols
    seen = set()
    for c in cols:
        if c in seen:
            raise RAError("Schema", f"both inputs of {node.kind.lower()} have an attribute {_qname(c)}, so the "
                                    f"qualified names collide; use rename on one side", node.pos)
        seen.add(c)
    return cols, left.types + right.types


def check_union_compatible(node, left, right):
    op = node.kind.lower()
    ln = [n for _, n in left.cols]
    rn = [n for _, n in right.cols]
    if len(ln) != len(rn):
        raise RAError("Schema", f"{op} needs the same number of attributes on both sides: "
                                f"left has {len(ln)} ({', '.join(ln)}), right has {len(rn)} ({', '.join(rn)})", node.pos)
    if ln != rn:
        raise RAError("Schema", f"{op} needs the same attribute names in the same order: "
                                f"left is ({', '.join(ln)}), right is ({', '.join(rn)})", node.pos)
    for name, a, b in zip(ln, left.types, right.types):
        if a != "any" and b != "any" and a != b:
            raise RAError("Schema", f"{op}: attribute {name} is a {TYPE_WORD[a]} on the left "
                                    f"but a {TYPE_WORD[b]} on the right", node.pos)


# ---- evaluation ------------------------------------------------------------
def evaluate(node, db, stats):
    k = node.kind

    if k == "Relation":
        if node.name not in db:
            known = ", ".join(sorted(db)) or "none loaded"
            raise RAError("Name", f"unknown relation '{node.name}' (known relations: {known})", node.pos)
        return db[node.name]

    if k == "Select":
        child = evaluate(node.child, db, stats)
        pred = compile_cond(node.cond, child.cols, child.types, len(child.cols))
        out = []
        for t in child.rows:
            stats.select_evals += 1
            if pred(t, None):
                out.append(t)
        return Relation(child.name, child.cols, child.types, out, child.qualified)

    if k == "Project":
        child = evaluate(node.child, db, stats)
        idx = [resolve(child.cols, a) for a in node.attrs]
        for pos, i in enumerate(idx):
            if i in idx[:pos]:
                raise RAError("Schema", f"attribute '{child.cols[i][1]}' is listed more than once in project "
                                        f"(a result relation cannot have two attributes with the same name)",
                              node.attrs[pos].pos)
        rows = []
        for t in child.rows:
            stats.project_tuples += 1
            rows.append(tuple(t[i] for i in idx))
        return Relation(child.name, [child.cols[i] for i in idx], [child.types[i] for i in idx],
                        dedupe(rows), child.qualified)

    if k == "Rename":
        child = evaluate(node.child, db, stats)
        cols = [(node.name, n) for _, n in child.cols]
        if len(set(cols)) != len(cols):
            raise RAError("Schema", f"rename[{node.name}] would give two attributes the same name; "
                                    f"project away one of them first", node.pos)
        return Relation(node.name, cols, child.types, child.rows, child.qualified)

    if k in ("Union", "Intersect", "Minus"):
        left = evaluate(node.left, db, stats)
        right = evaluate(node.right, db, stats)
        check_union_compatible(node, left, right)
        rkeys = {tuple_key(t) for t in right.rows}
        if k == "Union":
            rows = dedupe(left.rows + right.rows)
        elif k == "Intersect":
            rows = [t for t in left.rows if tuple_key(t) in rkeys]
        else:
            rows = [t for t in left.rows if tuple_key(t) not in rkeys]
        types = [a if a != "any" else b for a, b in zip(left.types, right.types)]
        return Relation(left.name, left.cols, types, rows, left.qualified)

    if k == "Times":
        left = evaluate(node.left, db, stats)
        right = evaluate(node.right, db, stats)
        cols, types = product_schema(left, right, node)
        rows = []
        for a in left.rows:
            for b in right.rows:
                stats.times_pairs += 1
                rows.append(a + b)
        return Relation(f"{left.name}_times_{right.name}", cols, types, rows, True)

    if k == "Join":
        # Semantically times followed by select[cond]. Implemented as a nested loop that
        # tests every pair without materialising the full product first.
        left = evaluate(node.left, db, stats)
        right = evaluate(node.right, db, stats)
        cols, types = product_schema(left, right, node)
        pred = compile_cond(node.cond, cols, types, len(left.cols))
        rows = []
        n = 0
        rrows = right.rows
        for a in left.rows:
            for b in rrows:
                n += 1
                if pred(a, b):
                    rows.append(a + b)
        stats.join_comparisons += n
        return Relation(f"{left.name}_join_{right.name}", cols, types, rows, True)

    raise ValueError(f"unknown node kind {k}")
