import string
import sys
import traceback
import vim
import jsindent

_vim_var_chars = tuple(string.ascii_letters + string.digits + '_')
def is_vim_var(name):
    """
    Returns True if `name` is the right mix of characters to be a vim
    variable.
    """
    # start at index 2 to skip & (settings) and : (scoping)
    return all(c in _vim_var_chars for c in name[2:])

def vimx(name, default=None):
    """
    Returns the value of a vim expression, or default if the given
    variable or setting doesn't exist.
    """
    if is_vim_var(name):
        # If the name looks like a variable or setting, return default
        # if it doesn't exist.
        if (vim.eval('exists("%s")' % name)) == '0':
            return default
    value = vim.eval('%s' % name)
    if value.isdigit():
        value = int(value)
    return value

def dbg(s):
    """
    Logs a debug line if `g:jsindent_log` is set.
    """
    logf = vimx('g:jsindent_log')
    if logf:
        try:
            with open(logf, 'a') as f:
                f.write(s + '\n')
        except Exception as e:
            print "dbg error: %s: %s" % (e.__class__.__name__, e)

# Global indenter instance to accelerate indenting sequences of lines.
indenter = None

def get_indent_(lnum):
    """
    Returns the number of spaces that line `lnum` (one-based) in the vim
    buffer should be indented.

    This is the inner function wrapped by get_indent()
    """
    # How many lines of context to use?
    # Note that lnum is 1-based, but buffer indexing is 0-based.
    context = vimx('g:jsindent_context', 100)
    if context == 0:
        start = 0
    else:
        start = lnum - context - 1
        if start < 0:
            start = 0

    # Collect the context lines including this one. NB: lnum is one-based.
    lines_before = vim.current.buffer[start:lnum]
    js = '\n'.join(lines_before).rstrip()

    # Instantiate the indenter if we haven't yet.
    global indenter
    if indenter is None:
        indenter = jsindent.Indenter()

    # Keep indenter settings sync'd with vim settings.
    # None of these should invalidate the indenter instance.
    indenter.expandtab = bool(vimx('&expandtab'))
    indenter.shiftwidth = vimx('&shiftwidth')
    indenter.tabstop = vimx('&tabstop')

    # Ask the indenter what spacing to use on the current line...
    return indenter.last_line_indent(js)

def get_indent(lnum):
    """
    Wraps get_indent_() to send exception traces to the debug log.
    """
    try:
        value = get_indent_(lnum)
        dbg(value)
        return value
    except:
        dbg("".join(traceback.format_exception(*sys.exc_info())))
        raise
