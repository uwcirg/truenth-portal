from __future__ import unicode_literals  # isort:skip

import io

from portal.dict_tools import dict_compare, dict_match, strip_empties


def test_shallow_empty():
    d = {'one': 1, 'two': 'two', 'three': [3], 'four': None}
    expected = {k: v for k, v in d.items() if v}
    assert expected == strip_empties(d)


def test_nested_empty_dict():
    d = {'one': 1, 'two': {'nested one': 1, 'empty list': [
        {'empty key': None}]}}
    expected = {'one': 1, 'two': {'nested one': 1}}
    assert expected == strip_empties(d)


def test_false_values():
    # need to retain boolean False, as it's not "empty"
    d = {'one': 1, 'two': False, 'three': {'nested zero': 0}}
    assert d == strip_empties(d)


def test_dict_match_matches():
    d1 = {'one': 1, 'two': False, 'three': {'nested zero': 0}}
    d2 = {'one': 1, 'two': False, 'three': {'nested zero': 0}}
    assert dict_match(d1, d2, io.StringIO())


def test_dict_match_not_match():
    d1 = {'one': 1, 'two': True, 'three': {'nested zero': 0}}
    d2 = {'one': 1, 'two': False, 'three': {'nested zero': 0}}
    assert not dict_match(d1, d2, io.StringIO())


def test_dict_compare_same():
    d1 = {'one': 1, 'two': False, 'three': {'nested zero': 0}}
    d2 = {'one': 1, 'two': False, 'three': {'nested zero': 0}}
    assert dict_compare(d1, d2) == (set(), set(), {}, {'one', 'two', 'three'})


def test_dict_compare_different():
    d1 = {'one': 1, 'two': False, 'three': {'nested zero': 0}}
    d2 = {'one': 1, 'three': {'nested zero': 1}, 'four': False}
    assert dict_compare(d1, d2) == (
        {'two'}, {'four'},
        {'three': ({'nested zero': 0}, {'nested zero': 1})}, {'one'})
