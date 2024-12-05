"""
Tests of the to_json module.
"""

from pathlib import Path
from typing import Any

from xontrib.xgit.views.to_json import to_json, JsonReturn, remap_ids

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
        # Fallback for 3.10
        ExceptionGroup = globals().get('ExceptionGroup', Exception)
        raise ExceptionGroup("Could not understand the JSON", exceptions)

    assert remapped_actual == remapped_expected, (
        f"{remapped_actual} != {remapped_expected}"
    )

def test_to_json_None(f_repo):
    cmp(to_json(None, repository=f_repo.repository), None)

def test_to_json_True(f_repo):
    cmp(to_json(True, repository=f_repo.repository), True)

def test_to_json_False(f_repo):
    cmp(to_json(False, repository=f_repo.repository), False)

def test_to_json_int(f_repo):
    cmp(to_json(42,repository=f_repo.repository), 42)

def test_to_json_float(f_repo):
    cmp(to_json(42.0, repository=f_repo.repository), 42.0)

def test_to_json_str(f_repo):
    cmp(to_json('foo', repository=f_repo.repository), 'foo')

def test_to_json_list(f_repo):
    cmp(to_json([1, 2, 3], repository=f_repo.repository),
        {'_id': 1, '_list': [1, 2, 3]})

def test_to_json_dict(f_repo):
    cmp(to_json({'x': 42},
                repository=f_repo.repository),
        {'_id': 1, '_map': {'x': 42}})

def test_to_json_nested(f_repo):
    cmp(to_json({'x': [1, 2, 3]},
                repository=f_repo.repository), {
        '_id': 1, '_map': {'x': {'_id': 2, '_list': [1, 2, 3]}}
    })

def test_to_json_nested2(f_repo):
    cmp(to_json({'x': {'y': 42}},
                repository=f_repo.repository), {
        '_id': 1, '_map': {'x': {'_id': 2, '_map': {'y': 42}}}
    })

def test_to_json_nested3(f_repo):
    a1 = to_json({'x': {'y': [1, 2, 3]}},
                 repository=f_repo.repository)
    a2a = {'_id': 4, '_list': [1, 2, 3]}
    a2b = {'_id': 2, '_map': {'y': a2a}}
    a2 = {'_id': 0, '_map': {'x': a2b}}
    a2 = cmp(a1, a2)

def test_to_json_nested_max(f_repo):
    value = {'x': {'y': {'z': 42}}}
    result = to_json(value,
                     max_levels=2,
                     repository=f_repo.repository)
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

def test_to_json_special(f_repo):
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
                     repository=f_repo.repository,
                     special_types={
        Special: lambda s, _: ({'special': 'K'}),
        }
    )
    cmp(actual, expected)

def test_to_json_special2(f_repo):
    sut = [Path('foo')]
    expected = {
        '_id': 1, '_list': [
                'foo'
             ]
    }
    actual = to_json(sut, repository=f_repo.repository)
    cmp(actual, expected)