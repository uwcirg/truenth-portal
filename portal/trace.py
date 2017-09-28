"""Module for capturing trace info during a request

NB this doesn't replace logging, intended to capture
specific details around tricky tasks.

"""
from flask import g


def establish_trace(opening_line):
    """Establish the begin of a trace - w/o this trace won't function

    Open up the trace for the request, capturing opening_line

    """
    if not hasattr(g, 'trace'):
        g.trace = []
    g.trace.append(opening_line)


def trace(line):
    """Add given line to trace, if active"""
    if hasattr(g, 'trace'):
        g.trace.append(line)


def dump_trace(last_line=None):
    """Return the active trace, a list of strings"""
    if hasattr(g, 'trace'):
        if last_line:
            g.trace.append(last_line)
        return g.trace
