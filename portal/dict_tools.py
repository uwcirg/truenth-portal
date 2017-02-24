"""Module for additional dictionary tools/utilities"""


def dict_compare(d1, d2):
    """Deep order independent comparison of two dictionaries

    returns lists of: added, removed, modified, same
    """
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = {o : (d1[o], d2[o]) for o in intersect_keys if d1[o] != d2[o]}
    same = set(o for o in intersect_keys if d1[o] == d2[o])
    return added, removed, modified, same


def dict_match(newd, oldd, diff_stream):
    """Returns true/false, if the two dicts contain same key/values

    Compares deep structure, ignores key order

    :param newd: First dict to compare, i.e. new state
    :param oldd: Second dict, i.e. current or old state
    :param diff_stream: StringIO like object to report dif details
    :return: True if the two dictionaries match, False with details in
        diff_stream otherwise

    """
    added, removed, modified, same = dict_compare(newd, oldd)
    if len(same) == len(newd.keys()) and len(newd.keys()) == len(oldd.keys()):
        assert not added
        assert not removed
        assert not modified
        return True
    else:
        if added:
            diff_stream.write(
                "added {}\n".format({k:newd.get(k) for k in added}))
        if removed:
            diff_stream.write(
                "removed {}\n".format({k:oldd.get(k) for k in removed}))
        if modified:
            for k in modified.keys():
                diff_stream.write(
                    "replace {} with {}\n".format(
                        {k:oldd.get(k)},{k:newd.get(k)}))
        return False

