"""Relations (sets of tuples), our own tuple equality, and the relation-definition loader.

A relation's columns are (qualifier, name) pairs. Column types are 'num', 'str',
or 'any' (only for a column of an empty relation).
"""

from .errors import RAError


# ---- tuple equality -----------------------------------------------------
def tuple_key(row):
    """Our definition of tuple equality: two tuples are equal iff their keys are equal.
    A number never equals a string ('1' and 1 are different values)."""
    return tuple(("s", v) if isinstance(v, str) else ("n", v) for v in row)


def dedupe(rows):
    """Remove duplicate tuples, keeping first occurrences in order."""
    seen = set()
    out = []
    for r in rows:
        k = tuple_key(r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def infer_types(rows, names, relname):
    types = []
    for i, name in enumerate(names):
        kinds = {"str" if isinstance(r[i], str) else "num" for r in rows}
        if len(kinds) > 1:
            raise RAError("Data", f"column {name} of {relname} mixes numbers and strings")
        types.append(kinds.pop() if kinds else "any")
    return types


class Relation:
    def __init__(self, name, cols, types, rows, qualified=False):
        self.name = name
        self.cols = cols          # list of (qualifier, attribute name)
        self.types = types        # list of 'num' | 'str' | 'any'
        self.rows = rows          # list of tuples, no duplicates
        self.qualified = qualified  # show 'Rel.attr' in output headers (set by times/join)

    def display_names(self):
        return [f"{r}.{n}" if self.qualified else n for r, n in self.cols]

    def format(self, limit=None):
        names = self.display_names()
        shown = self.rows if limit is None else self.rows[:limit]
        cells = [[str(v) for v in r] for r in shown]
        widths = [max([len(nm)] + [len(c[i]) for c in cells]) for i, nm in enumerate(names)]
        lines = [" | ".join(nm.ljust(w) for nm, w in zip(names, widths)).rstrip(),
                 "-+-".join("-" * w for w in widths)]
        for c in cells:
            lines.append(" | ".join(v.ljust(w) for v, w in zip(c, widths)).rstrip())
        n = len(self.rows)
        lines.append(f"({n} tuple{'s' if n != 1 else ''})")
        if limit is not None and n > limit:
            lines.append(f"... {n - limit} more tuples not shown (use --limit)")
        return "\n".join(lines)


def relation_from_rows(name, attrs, rows):
    rows = dedupe([tuple(r) for r in rows])
    return Relation(name, [(name, a) for a in attrs], infer_types(rows, attrs, name), rows)


# ---- relation-definition loader (hand-written, no regex) -----------------
def _err(source, lineno, msg):
    return RAError("Data", f"{source}, line {lineno}: {msg}")


def _number_or_none(text):
    """Return int/float if text is a number (optional '-', digits, optional '.digits')."""
    i, n = 0, len(text)
    if i < n and text[i] == "-":
        i += 1
    d0 = i
    while i < n and "0" <= text[i] <= "9":
        i += 1
    if i == d0:
        return None
    if i < n and text[i] == ".":
        i += 1
        d1 = i
        while i < n and "0" <= text[i] <= "9":
            i += 1
        if i == d1:
            return None
    if i != n:
        return None
    return float(text) if "." in text else int(text)


def _skip_ws(s, i):
    while i < len(s) and s[i] in " \t":
        i += 1
    return i


def _read_ident(s, i):
    j = i
    while j < len(s) and (s[j].isalpha() or s[j] == "_" or ("0" <= s[j] <= "9" and j > i)):
        j += 1
    return s[i:j], j


def _parse_header(s, lineno, source):
    """Name (A, B, C) = {     ->  (name, [attrs], rest_after_brace)"""
    name, i = _read_ident(s, 0)
    if not name:
        raise _err(source, lineno, "expected a relation name")
    i = _skip_ws(s, i)
    if i >= len(s) or s[i] != "(":
        raise _err(source, lineno, "expected '(' after relation name")
    i += 1
    attrs = []
    while True:
        i = _skip_ws(s, i)
        a, i = _read_ident(s, i)
        if not a:
            raise _err(source, lineno, "expected an attribute name")
        attrs.append(a)
        i = _skip_ws(s, i)
        if i < len(s) and s[i] == ",":
            i += 1
            continue
        if i < len(s) and s[i] == ")":
            i += 1
            break
        raise _err(source, lineno, "expected ',' or ')' in attribute list")
    if len(set(attrs)) != len(attrs):
        raise _err(source, lineno, f"relation {name} has a repeated attribute name")
    i = _skip_ws(s, i)
    if i >= len(s) or s[i] != "=":
        raise _err(source, lineno, "expected '=' after attribute list")
    i = _skip_ws(s, i + 1)
    if i >= len(s) or s[i] != "{":
        raise _err(source, lineno, "expected '{'")
    return name, attrs, s[i + 1:].strip()


def _split_values(s, lineno, source):
    vals = []
    i, n = 0, len(s)
    while True:
        i = _skip_ws(s, i)
        if i < n and s[i] == "'":
            i += 1
            buf = []
            while True:
                if i >= n:
                    raise _err(source, lineno, "unterminated quoted string")
                if s[i] == "'":
                    if i + 1 < n and s[i + 1] == "'":
                        buf.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(s[i])
                i += 1
            vals.append("".join(buf))  # quoted => always a string
        else:
            j = i
            while j < n and s[j] != ",":
                j += 1
            raw = s[i:j].strip()
            if raw == "":
                raise _err(source, lineno, "empty value")
            for ch in raw:
                if ch in " \t()'":
                    raise _err(source, lineno, f"value {raw!r} must be quoted (it contains a space, parenthesis or quote)")
            num = _number_or_none(raw)
            vals.append(num if num is not None else raw)
            i = j
        i = _skip_ws(s, i)
        if i >= n:
            return vals
        if s[i] == ",":
            i += 1
            continue
        raise _err(source, lineno, "expected ',' between values")


def load_relations(text, source="<data>"):
    rels = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        lineno = i + 1
        i += 1
        if s == "" or s.startswith("//"):
            continue
        name, attrs, rest = _parse_header(s, lineno, source)
        if name in rels:
            raise _err(source, lineno, f"relation {name} is defined twice")
        rows = []
        if rest != "}":
            if rest != "":
                raise _err(source, lineno, "nothing may follow '{' on the header line")
            closed = False
            while i < len(lines):
                s2 = lines[i].strip()
                ln = i + 1
                i += 1
                if s2 == "" or s2.startswith("//"):
                    continue
                if s2 == "}":
                    closed = True
                    break
                vals = _split_values(s2, ln, source)
                if len(vals) != len(attrs):
                    raise _err(source, ln, f"expected {len(attrs)} values for {name} but found {len(vals)}")
                rows.append(tuple(vals))
            if not closed:
                raise _err(source, lineno, f"relation {name} is missing its closing '}}'")
        rels[name] = relation_from_rows(name, attrs, rows)
    return rels
