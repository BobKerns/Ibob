"""
Tests of the to_json module.
"""

from pathlib import Path
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

def test_to_json_None(repository):
    cmp(to_json(None, repository=repository), None)

def test_to_json_True(repository):
    cmp(to_json(True, repository=repository), True)

def test_to_json_False(repository):
    cmp(to_json(False, repository=repository), False)

def test_to_json_int(repository):
    cmp(to_json(42,repository=repository), 42)

def test_to_json_float(repository):
    cmp(to_json(42.0, repository=repository), 42.0)

def test_to_json_str(repository):
    cmp(to_json('foo', repository=repository), 'foo')

def test_to_json_list(repository):
    cmp(to_json([1, 2, 3], repository=repository), {'_id': 1, '_list': [1, 2, 3]})

def test_to_json_dict(repository):
    cmp(to_json({'x': 42}, repository=repository), {'_id': 1, '_map': {'x': 42}})

def test_to_json_nested(repository):
    cmp(to_json({'x': [1, 2, 3]}, repository=repository), {'_id': 1, '_map': {'x': {'_id': 2, '_list': [1, 2, 3]}}})

def test_to_json_nested2(repository):
    cmp(to_json({'x': {'y': 42}}, repository=repository), {'_id': 1, '_map': {'x': {'_id': 2, '_map': {'y': 42}}}})

def test_to_json_nested3(repository):
    a1 = to_json({'x': {'y': [1, 2, 3]}}, repository=repository)
    a2a = {'_id': 4, '_list': [1, 2, 3]}
    a2b = {'_id': 2, '_map': {'y': a2a}}
    a2 = {'_id': 0, '_map': {'x': a2b}}
    a2 = cmp(a1, a2)

def test_to_json_nested_max(repository):
    value = {'x': {'y': {'z': 42}}}
    result = to_json(value, max_levels=2, repository=repository)
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

def test_to_json_special(repository):
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
    actual = to_json(sut,
                     repository=repository,
                     special_types={
        Special: lambda s, _: ({'special': 'K'}),
        }
    )
    cmp(actual, expected)

def test_to_json_special2(repository):
    sut = [Path('foo')]
    expected = {
        '_id': 1, '_list': [
                'foo'
             ]
    }
    actual = to_json(sut, repository=repository)
    cmp(actual, expected)