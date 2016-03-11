""" Module for helper functions used inside jinja2 templates """

# NB, each blueprint must individually load any functions defined below
# for them to appear in the namespace when invoked from respective blueprint
# See @<blueprint>.context_processor decorator for more info.

def split_string(s, delimiter=','):
    """Given string (or tuple) return the delimited values"""
    # If given a tuple, split already happened
    if isinstance(s, (list, tuple)):
        return s
    return s.split(delimiter)
