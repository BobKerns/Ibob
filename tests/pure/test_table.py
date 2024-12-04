''''
Test the table module.
'''

from xonsh.lib.pretty import pretty

from xontrib.xgit.table import TableView, Column

def test_table_view():
    '''
    Test the table view.
    '''
    table = TableView([
        {'a': 1, 'b': 2},
        {'a': 3, 'b': 4},
    ])
    assert table._columns == {
        -1: Column(name='Row', key=-1, heading_width=0, ignore=True, elements=[]),
        'a': Column(name='a', key='a', heading_width=1, elements=[1, 3]),
        'b': Column(name='b', key='b', heading_width=1, elements=[2, 4]),
    }


def test_table_view_cols():
    '''
    Test the table view.
    '''
    defs = {
        0: Column(name='0', heading='Key', format='{:>{width}}'),
        1: Column(name='1', heading='Value'),
    }
    table = TableView(
        [
            {'a': 1, 'b': 2},
            {'a': 3, 'b': 4},
        ],
        columns=defs,
    )
    pretty(table)