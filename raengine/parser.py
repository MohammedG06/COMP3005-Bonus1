"""Recursive descent parser. One method per grammar rule in GRAMMAR.md.

Left recursion is removed by turning  expr ::= expr op term | term
into a loop:                          expr ::= term { op term }
and building the tree left-to-right inside the loop, so operators are left associative.

Keywords are contextual: the tokenizer emits every word as IDENT and the parser only
treats a word as a keyword in a position where the grammar expects one.
"""

from .errors import RAError
from .tokenizer import tokenize
from .nodes import Node

CMP_TOKENS = ("=", "!=", "<", "<=", ">", ">=")


class Parser:
    def __init__(self, source):
        self.src = source
        self.toks = tokenize(source)
        self.i = 0

    # ---- helpers -------------------------------------------------------
    def peek(self, k=0):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def advance(self):
        t = self.toks[self.i]
        if t.type != "EOF":
            self.i += 1
        return t

    @staticmethod
    def describe(t):
        if t.type == "EOF":
            return "end of input"
        if t.type == "STR":
            return f"string {t.text}"
        return f"'{t.text}'"

    def fail(self, msg, tok=None):
        tok = tok or self.peek()
        raise RAError("Syntax", msg, tok.pos)

    def is_word(self, *words):
        t = self.peek()
        return t.type == "IDENT" and t.text in words

    def expect(self, ttype, opener=None):
        t = self.peek()
        if t.type == ttype:
            return self.advance()
        if opener is not None:
            self.fail(
                f"missing '{ttype}': the '{opener.text}' at position {opener.pos} is never closed "
                f"(found {self.describe(t)})"
            )
        self.fail(f"expected '{ttype}' but found {self.describe(t)}")

    def expect_ident(self, what):
        t = self.peek()
        if t.type != "IDENT":
            self.fail(f"expected {what} but found {self.describe(t)}")
        return self.advance()

    # ---- entry ---------------------------------------------------------
    def parse_query(self):
        node = self.parse_expr()
        t = self.peek()
        if t.type != "EOF":
            if t.type == ")":
                self.fail("unmatched ')' (no '(' is open here)")
            self.fail(
                f"unexpected {self.describe(t)}; expected an operator "
                f"(union, minus, intersect, times, join) or end of input"
            )
        return node

    # ---- expressions (lowest to highest precedence) --------------------
    def parse_expr(self):  # expr ::= term { ("union"|"minus") term }
        left = self.parse_term()
        while self.is_word("union", "minus"):
            op = self.advance()
            right = self.parse_term()
            left = Node(op.text.capitalize(), op.pos, left=left, right=right)
        return left

    def parse_term(self):  # term ::= factor { "intersect" factor }
        left = self.parse_factor()
        while self.is_word("intersect"):
            op = self.advance()
            right = self.parse_factor()
            left = Node("Intersect", op.pos, left=left, right=right)
        return left

    def parse_factor(self):  # factor ::= unit { ("times" | "join" "[" cond "]") unit }
        left = self.parse_unit()
        while self.is_word("times", "join"):
            op = self.advance()
            if op.text == "times":
                right = self.parse_unit()
                left = Node("Times", op.pos, left=left, right=right)
            else:
                lb = self.expect("[")
                cond = self.parse_cond()
                self.expect("]", lb)
                right = self.parse_unit()
                left = Node("Join", op.pos, cond=cond, left=left, right=right)
        return left

    def parse_unit(self):
        t = self.peek()
        if t.type == "(":
            lp = self.advance()
            e = self.parse_expr()
            self.expect(")", lp)
            return e
        if t.type == "IDENT":
            if t.text in ("select", "project", "rename") and self.peek(1).type == "[":
                return self.parse_unary()
            self.advance()
            return Node("Relation", t.pos, name=t.text)
        self.fail(
            f"expected a relation name, select/project/rename, or '(' but found {self.describe(t)}"
        )

    def parse_unary(self):
        kw = self.advance()
        lb = self.expect("[")
        if kw.text == "select":
            cond = self.parse_cond()
            self.expect("]", lb)
            child = self.parse_paren_expr()
            return Node("Select", kw.pos, cond=cond, child=child)
        if kw.text == "project":
            if self.peek().type == "]":
                self.fail("expected an attribute name but found ']' (an empty attribute list is not a valid projection)")
            attrs = [self.parse_attrref()]
            while self.peek().type == ",":
                self.advance()
                attrs.append(self.parse_attrref())
            self.expect("]", lb)
            child = self.parse_paren_expr()
            return Node("Project", kw.pos, attrs=attrs, child=child)
        name = self.expect_ident("a new relation name")  # rename
        self.expect("]", lb)
        child = self.parse_paren_expr()
        return Node("Rename", kw.pos, name=name.text, child=child)

    def parse_paren_expr(self):
        lp = self.expect("(")
        e = self.parse_expr()
        self.expect(")", lp)
        return e

    # ---- conditions ----------------------------------------------------
    def parse_cond(self):  # cond ::= andcond { "or" andcond }
        left = self.parse_and()
        while self.is_word("or"):
            op = self.advance()
            right = self.parse_and()
            left = Node("Or", op.pos, left=left, right=right)
        return left

    def parse_and(self):  # andcond ::= notcond { "and" notcond }
        left = self.parse_not()
        while self.is_word("and"):
            op = self.advance()
            right = self.parse_not()
            left = Node("And", op.pos, left=left, right=right)
        return left

    def parse_not(self):
        t = self.peek()
        # 'not' is the operator unless it is being used as an attribute name,
        # i.e. it is directly followed by a comparison operator or a '.'.
        if t.type == "IDENT" and t.text == "not" and self.peek(1).type not in CMP_TOKENS + (".",):
            self.advance()
            return Node("Not", t.pos, child=self.parse_not())
        if t.type == "(":
            lp = self.advance()
            c = self.parse_cond()
            self.expect(")", lp)
            return c
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_operand()
        t = self.peek()
        if t.type not in CMP_TOKENS:
            self.fail(f"expected a comparison operator (=, !=, <, <=, >, >=) but found {self.describe(t)}")
        self.advance()
        right = self.parse_operand()
        return Node("Cmp", left.pos, op=t.type, left=left, right=right)

    def parse_operand(self):
        t = self.peek()
        if t.type == "NUM":
            self.advance()
            return Node("Num", t.pos, value=t.value)
        if t.type == "STR":
            self.advance()
            return Node("Str", t.pos, value=t.value)
        if t.type == "IDENT":
            return self.parse_attrref()
        self.fail(f"expected an operand (number, quoted string or attribute name) but found {self.describe(t)}")

    def parse_attrref(self):  # attrref ::= IDENT [ "." IDENT ]
        first = self.expect_ident("an attribute name")
        if self.peek().type == ".":
            self.advance()
            second = self.expect_ident("an attribute name after '.'")
            return Node("Attr", first.pos, qual=first.text, name=second.text)
        return Node("Attr", first.pos, qual=None, name=first.text)


def parse(source):
    return Parser(source).parse_query()
