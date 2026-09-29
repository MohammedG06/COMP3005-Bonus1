"""Parse-tree nodes and the tree printer.

Expression kinds: Relation, Select, Project, Rename, Union, Intersect, Minus, Times, Join
Condition kinds:  Cmp, And, Or, Not
Operand kinds:    Attr, Num, Str
"""

CMP_NAMES = {"=": "Eq", "!=": "Ne", "<": "Lt", "<=": "Le", ">": "Gt", ">=": "Ge"}
BINARY = ("Union", "Intersect", "Minus", "Times", "Join")
UNARY = ("Select", "Project", "Rename")


class Node:
    def __init__(self, kind, pos, **fields):
        self.kind = kind
        self.pos = pos
        for k, v in fields.items():
            setattr(self, k, v)

    def children(self):
        if self.kind in UNARY:
            return [self.child]
        if self.kind in BINARY:
            return [self.left, self.right]
        return []

    def label(self):
        k = self.kind
        if k == "Relation":
            return f"Relation({self.name})"
        if k == "Select":
            return f"Select(cond={cond_str(self.cond)})"
        if k == "Project":
            return "Project(attrs=[" + ", ".join(attr_str(a) for a in self.attrs) + "])"
        if k == "Rename":
            return f"Rename(as={self.name})"
        if k == "Join":
            return f"Join(cond={cond_str(self.cond)})"
        return k  # Union, Intersect, Minus, Times


def attr_str(a):
    return f"{a.qual}.{a.name}" if a.qual else a.name


def operand_str(o):
    if o.kind == "Attr":
        return f"Attr({attr_str(o)})"
    if o.kind == "Num":
        return f"Num({o.value})"
    return "Str('" + o.value.replace("'", "''") + "')"


def cond_str(c):
    if c.kind == "Cmp":
        return f"{CMP_NAMES[c.op]}({operand_str(c.left)}, {operand_str(c.right)})"
    if c.kind in ("And", "Or"):
        return f"{c.kind}({cond_str(c.left)}, {cond_str(c.right)})"
    if c.kind == "Not":
        return f"Not({cond_str(c.child)})"
    raise ValueError(c.kind)


def render_tree(root):
    lines = [root.label()]

    def walk(node, prefix):
        kids = node.children()
        for i, k in enumerate(kids):
            last = i == len(kids) - 1
            lines.append(prefix + ("└── " if last else "├── ") + k.label())
            walk(k, prefix + ("    " if last else "│   "))

    walk(root, "")
    return "\n".join(lines)
