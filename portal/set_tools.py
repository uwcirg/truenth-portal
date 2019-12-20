"""Module for additional set tools/utilities"""


def left_center_right(leftset, rightset):
    """Return left only, center (common) and right only elements"""
    left = leftset - rightset
    common = leftset & rightset
    right = rightset - leftset
    return left, common, right
