"""
Tests of the to_json module.
"""

from typing import Any

from xontrib.xgit.to_json import to_json, JsonReturn, remap_ids

_id = remap_ids

def cmp(result: Any, expected: Any):
    exceptions: list[Exception] = []
    remapped_expected: JsonReturn= None
    remapped_actual: JsonReturn = None
    try:
        remapped_actual = remap_ids(result, 'actual')
    except Exception as ex:
        exceptions.append(ex)
    try:
        remapped_expected = remap_ids(expected, 'expected')
    except Exception as ex:
        exceptions.append(ex)

    if exceptions:
        raise ExceptionGroup("Could not understand the JSON", exceptions)

    assert remapped_actual == remapped_expected, f"{remapped_actual} != {remapped_expected}"

def test_to_json_None():
    cmp(to_json(None), None)

def test_to_json_True():
    cmp(to_json(True), True)

def test_to_json_False():
    cmp(to_json(False), False)

def test_to_json_int():
    cmp(to_json(42), 42)

def test_to_json_float():
    cmp(to_json(42.0), 42.0)

def test_to_json_str():
    cmp(to_json('foo'), 'foo')

def test_to_json_list():
    cmp(to_json([1, 2, 3]), {'_id': 1, '_list': [1, 2, 3]})

def test_to_json_dict():
    cmp(to_json({'x': 42}), {'_id': 1, '_map': {'x': 42}})

def test_to_json_nested():
    cmp(to_json({'x': [1, 2, 3]}), {'_id': 1, '_map': {'x': {'_id': 2, '_list': [1, 2, 3]}}})

def test_to_json_nested2():
    cmp(to_json({'x': {'y': 42}}), {'_id': 1, '_map': {'x': {'_id': 2, '_map': {'y': 42}}}})

def test_to_json_nested3():
    a1 = to_json({'x': {'y': [1, 2, 3]}})
    a2a = {'_id': 4, '_list': [1, 2, 3]}
    a2b = {'_id': 2, '_map': {'y': a2a}}
    a2 = {'_id': 0, '_map': {'x': a2b}}
    a2 = cmp(a1, a2)

def test_to_json_nested_max():
    value = {'x': {'y': {'z': 42}}}
    result = to_json(value, max_levels=2)
    if 0:
        expected = {
            '_id': 1, '_map': {
                'x': {'_id': 2, '_map': {
                    'y': {'_id': 3, '_map': {
                        'z': {'_id': 4, '_maxdepth': 2}}}}}}}
    else:
        expected = {
            '_id': 1, '_map': {
                'x': {'_id': 2, '_map': {
                    'y': {'_id': 4, '_maxdepth': 2}}}}}
    cmp(result, expected)

def test_to_json_special():
    class Special:
        pass
    sut = [Special()]
    expected = {
        '_id': 1, '_list': [
                {
                    '_id': 2,
                    '_cls': 'Special',
                    '_attrs': {
                        'special': 'K'
                    }
                }
             ]
    }
    actual = to_json(sut, special_types={
        Special: lambda s, _: ({'special': 'K'}),
        }
    )
    cmp(actual, expected)