""" Module for helper functions used inside jinja2 templates """

# NB, each blueprint must individually load any functions defined below
# for them to appear in the namespace when invoked from respective blueprint
# See @<blueprint>.context_processor decorator for more info.

def split_string(s, delimiter=','):
    return s.split(delimiter)
