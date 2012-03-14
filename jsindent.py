import re, sys, traceback
from jslex import JsLexer

class Indenter(object):
    tabstop = 8
    shiftwidth = 4
    expandtab = None

    def expand(self, ws, wsonly=True):
        """
        Expand tabs in ws according to self.tabstop.
        """
        if wsonly:
            # This assertion isn't necessary for correct operation of this
            # function, but it's a safety net for the caller.
            assert set(ws) <= set(' \t')
        return ws.expandtabs(self.tabstop)

    def unexpand(self, ws, wsonly=True):
        """
        Unexpand tabs in ws according to self.tabstop.
        """
        if wsonly:
            # This assertion isn't necessary for correct operation of this
            # function, but it's a safety net for the caller.
            assert set(ws) <= set(' ')
        return ws.replace(' ' * self.tabstop, '\t')

    def _shift(self, orig, dir, count=1):
        """
        Given a string, returns the string with the indent shifted in `dir`
        direction by self.shiftwidth spaces.
        """
        assert dir in ['left', 'right']
        ows, rest = re.split(r'(?=\S|\Z)', orig, 1)
        indent = len(expand(ows))
        if dir == 'right':
            if indent % shiftwidth:
                indent -= indent % shiftwidth
            indent += shiftwidth * count
        else:
            if indent % shiftwidth:
                indent -= indent % shiftwidth
                count -= 1
            indent -= shiftwidth * count
        ws = ' ' * indent
        if (self.expandtab == False or
            (self.expandtab is None and '\t' in ows)):
            ws = self.unexpand(ws)
        return ws + rest

    def shift_right(self, orig, **kwargs):
        """
        Given a string, returns the string with the indent increased by
        self.shiftwidth.
        """
        return self._shift(orig, dir='right', **kwargs)

    def shift_left(self, orig, **kwargs):
        """
        Given a string, returns the string with the indent decreased by
        shiftwidth.
        """
        return self._shift(orig, dir='left', **kwargs)

    def last_line_indent(self, js):
        """
        Given a string of javascript lines, returns the number of spaces
        that the last line (after the last newline) should be indented.
        """
        # We require context, otherwise we're clueless.
        if '\n' not in js:
            return 0

        # Split off the last (current) line, since that's the line we're
        # indenting.
        context, current = js.rsplit('\n', 1)

        # Seed our stack with the initial whitespace on the first line of code,
        # since whitespace stored in the stack is normally the result of some
        # token.
        initial = re.match(r'\s*', context).group(0).rsplit('\n', 1)[-1]
        stack = TokenStack(initial)

        dbgline = ''
        for name, tok in JsLexer().lex(context):
            dbgline += tok
            #dbg("| %r" % dbgline)
            if name == 'ws':
                if '\n' in tok:
                    if stack.tok == 'if_cond' and stack.real:
                        while stack.tok == 'if_cond':
                            stack.pop()
                    # Continuously track the indent at each level, overwriting
                    # our guesses with reality. This also upholds the principle
                    # of least surprise, since it keeps from "correcting" the
                    # user's indentation.
                    ws = tok.rsplit('\n', 1)[1]
                    stack.update(ws=ws, real=True)
                    dbgline = ws
            else:
                if name == 'punct':
                    if tok in ['{', '(', '[']:
                        stack.push(tok)
                    elif tok in ['}', ')', ']']:
                        stack.pop()
                        if tok == ')' and stack.tok == 'if':
                            # Convert the "if" we're tracking to "if_cond"
                            stack.update(tok='if_cond')
                elif name == 'keyword':
                    if tok in ['if', 'for', 'while']:
                        stack.push('if')
                    elif tok == 'else':
                        stack.push('if_cond')

        # Pop off completed if_conds on the top of the stack. This normally
        # happens when handling the whitespace separating lines, but we don't
        # have that at the very end.
        if stack.tok == 'if_cond' and stack.real:
            while stack.tok == 'if_cond':
                stack.pop()

        current_ = current.lstrip()
        if current_.startswith(tuple('])}')):
            # Current line begins with closing punctuation, pop once more
            stack.pop()
        elif current_.startswith('{') and stack.tok == 'if_cond':
            # Starting a block on the line following if (condition)
            stack.pop()

        #dbg("stack=%r" % stack)
        return len(stack.ws)

class Token(object):
    """
    A token with the *resulting* whitespace indentation.
    The real attribute indicates whether this is guessed or actual.
    """
    def __init__(self, tok, ws, real=False):
        self.tok = tok
        self.ws = ws
        self.real = real

    def update(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return "Token(%r, %r, %r)" % (self.tok, len(expand(self.ws)), self.real)

class TokenStack(object):
    def __init__(self, initws):
        self.__dict__['stack'] = [Token(None, initws, True)]

    def __repr__(self):
        return "<TokenStack %r>" % self.stack

    def push(self, tok, ws=None):
        if ws is None:
            if self.real:
                ws = shift_right(self.ws)
            else:
                ws= self.ws
            real = False
        else:
            real = True
        while self.tok == 'if_cond':
            self.pop()
        self.stack.append(Token(tok, ws, real))
        #dbg("> %r" % self[-1])

    def pop(self):
        token = self.stack.pop()
        #dbg("< %r" % token)
        if not self.stack:
            # Prepare for a following pop() by manufacturing a new initws.
            self.push(None, shift_left(token.ws))
        return token

    def update(self, **kwargs):
        self[-1].update(**kwargs)
        #dbg("! %r" % self[-1])

    def __getattr__(self, name):
        return getattr(self[-1], name)

    def __setattr__(self, name, value):
        setattr(self[-1], name, value)

    def __len__(self):
        return len(self.stack)

    def __getitem__(self, key):
        return self.stack[key]

    def __setitem__(self, key, token):
        assert isinstance(token, Token)
        self.stack[key] = token

    def __iter__(self):
        return iter(self.stack)

    def __reversed__(self):
        return reversed(self.stack)
