import vim, re, sys, traceback
from jslex import JsLexer

def quote(s):
    return "'" + s.replace("'", "''") + "'"

def dbg(s):
    if (vim.eval('exists("g:jsindent_wip")') == '1' and
        int(vim.eval('g:jsindent_wip'))):
        with open('/home/aron/vim-js.log', 'a') as f:
            f.write(s)
            if not s.endswith('\n'):
                f.write('\n')

def expand(ws):
    """
    Expand tabs in ws according to &tabstop.
    """
    indent = int(vim.eval("strdisplaywidth('%s')" % ws))
    return ' ' * indent

def unexpand(ws):
    """
    Unexpand tabs in ws according to &tabstop.
    """
    ts = int(vim.eval("&tabstop"))
    return ws.replace(' ' * ts, '\t')

def shift_right(ows, count=1):
    """
    Given a whitespace string, returns the string increased by shiftwidth.
    """
    indent = len(expand(ows))
    sw = int(vim.eval("&shiftwidth"))
    if indent % sw:
        indent -= indent % sw
    indent += sw * count
    ws = ' ' * indent
    if not int(vim.eval("&expandtab")):
        ws = unexpand(ws)
    return ws

def shift_left(ows):
    """
    Given a whitespace string, returns the string reduced by shiftwidth.
    """
    indent = len(expand(ows))
    sw = int(vim.eval("&shiftwidth"))
    if indent % sw:
        indent -= indent % sw
    elif indent:
        indent -= sw
    ws = ' ' * indent
    if '\t' in ows:
        ws = unexpand(ws)
    return ws

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
        dbg("> %r" % self[-1])

    def pop(self):
        token = self.stack.pop()
        dbg("< %r" % token)
        if not self.stack:
            # Prepare for a following pop() by manufacturing a new initws.
            self.push(None, shift_left(token.ws))
        return token

    def update(self, **kwargs):
        self[-1].update(**kwargs)
        dbg("! %r" % self[-1])

    @property
    def realws(self):
        return next(token.ws for token in reversed(self.stack) if token.real)

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

def get_indent_(lnum):
    # How many lines of context to use?
    # Note that lnum is 1-based, but buffer indexing is 0-based.
    context = 100
    if vim.eval('exists("g:jsindent_context")') == "1":
        try:
            context = int(vim.eval('g:jsindent_context'))
        except ValueError:
            pass
    if context:
        start = lnum - context - 1
        if start < 0:
            start = 0
    else:
        start = 0

    # Collect the context lines prior to and excluding this one.
    lines_before = vim.current.buffer[start:lnum-1]
    js = '\n'.join(lines_before).rstrip()
    dbg(js)

    # Kill everything up to the script tag
    js = re.sub(r'(?s)^.*<script[^>]*>', '', js, count=1)

    # Find the initial whitespace on the first line of code.
    initial = re.match(r'\s*', js).group(0).rsplit('\n', 1)[-1]

    stack = TokenStack(initial)
    dbgline = ''
    for name, tok in JsLexer().lex(js):
        dbgline += tok
        dbg("| %r" % dbgline)
        if name == 'ws':
            if '\n' in tok:
                if stack.tok == 'if_cond' and stack.real:
                    while stack.tok == 'if_cond':
                        stack.pop()
                # Continuously track the indent at each level, so we can
                # overwrite our guesses with reality. This also upholds the
                # principle of least surprise, since it keeps us from
                # "correcting" the user's indentation.
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

    this = vim.current.buffer[lnum-1].lstrip()
    if this.startswith(tuple('])}')):
        # Current line begins with closing punctuation, pop once more
        stack.pop()
    elif this.startswith('{') and stack.tok == 'if_cond':
        # Starting a block on the line following if (condition)
        stack.pop()

    dbg("stack=%r" % stack)
    return len(stack.ws)

def get_indent(lnum):
    try:
        return get_indent_(lnum)
    except:
        dbg("".join(traceback.format_exception(*sys.exc_info())))
        raise
