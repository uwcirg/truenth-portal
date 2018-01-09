from portal.dict_tools import strip_empties


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
