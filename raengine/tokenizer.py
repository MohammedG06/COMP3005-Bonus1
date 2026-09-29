"""Hand-written, character-by-character scanner. No regex, no split-on-spaces.

Token types:
  IDENT   a word (keywords are NOT special here; the parser decides by context)
  NUM     an optionally negative integer or decimal, value is int/float
  STR     a single-quoted string, value is the decoded text ('' -> ')
  EOF     end of input
  and one type per symbol, equal to its text: ( ) [ ] , . = != < <= > >=
"""

from .errors import RAError


class Token:
    __slots__ = ("type", "text", "value", "pos")

    def __init__(self, type_, text, value, pos):
        self.type = type_
        self.text = text
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"{self.type}({self.text!r}@{self.pos})"


def _is_letter(c):
    return c.isalpha() or c == "_"


def _is_digit(c):
    return "0" <= c <= "9"


_SINGLE = "()[],.="


def tokenize(src):
    toks = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        start = i

        if _is_letter(c):
            i += 1
            while i < n and (_is_letter(src[i]) or _is_digit(src[i])):
                i += 1
            text = src[start:i]
            toks.append(Token("IDENT", text, text, start))

        elif _is_digit(c) or (c == "-" and i + 1 < n and _is_digit(src[i + 1])):
            # A '-' only starts a number when a digit follows immediately.
            if c == "-":
                i += 1
            while i < n and _is_digit(src[i]):
                i += 1
            if i + 1 < n and src[i] == "." and _is_digit(src[i + 1]):
                i += 1
                while i < n and _is_digit(src[i]):
                    i += 1
            if i < n and _is_letter(src[i]):
                raise RAError("Lexical", f"malformed number: digits followed directly by {src[i]!r}", start)
            text = src[start:i]
            value = float(text) if "." in text else int(text)
            toks.append(Token("NUM", text, value, start))

        elif c == "'":
            i += 1
            buf = []
            while True:
                if i >= n:
                    raise RAError("Lexical", "unterminated string (missing closing quote)", start)
                if src[i] == "'":
                    if i + 1 < n and src[i + 1] == "'":  # doubled quote = one literal quote
                        buf.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(src[i])
                i += 1
            toks.append(Token("STR", src[start:i], "".join(buf), start))

        elif c == "!":
            if i + 1 < n and src[i + 1] == "=":
                i += 2
                toks.append(Token("!=", "!=", None, start))
            else:
                raise RAError("Lexical", "'!' must be followed by '=' (the only operator starting with '!' is '!=')", start)

        elif c == "<" or c == ">":
            # maximal munch: look at the next character before deciding
            if i + 1 < n and src[i + 1] == "=":
                i += 2
            else:
                i += 1
            text = src[start:i]
            toks.append(Token(text, text, None, start))

        elif c in _SINGLE:
            i += 1
            toks.append(Token(c, c, None, start))

        else:
            raise RAError("Lexical", f"unexpected character {c!r}", start)

    toks.append(Token("EOF", "", None, n))
    return toks
