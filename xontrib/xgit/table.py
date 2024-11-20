'''
A table view of objects.
'''

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Mapping, Optional, TypeAlias
from itertools import chain

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import _NO_VALUE, _NoValue
from xontrib.xgit.view import SequenceView

HeadingStrategy: TypeAlias = Literal['none', 'name', 'heading', 'heading-or-name']

@dataclass
class Column:
    '''
    A column in a table view.
    '''
    name: str
    heading: Optional[str] = None
    heading_width: int = 0
    @property
    def width(self):
        return max(self.heading_width,
                   max(len(e) for e in self.formatted))
    formatter: Optional[Callable[[Any], str]] = None
    format: str = '{:<{width}}'
    missing: str = ''
    ignore: bool = False
    ''''
    Whether to ignore the column. Ignored columns are not collected or displayed.
    '''
    elements: list[Any] = field(default_factory=list)
    _formatted: list[str] = field(default_factory=list, repr=False)
    @property
    def formatted(self):
        '''
        Get the formatted elements.
        '''
        if not self._formatted:
            formatter = self.formatter or str
            self._formatted = [formatter(e) for e in self.elements]
        return self._formatted

ColumnDict: TypeAlias = dict[str|int, Column]|dict[str, Column]|dict[int, Column]
ColumnKeys: TypeAlias = list[str|int]|list[str]|list[int]

class TableView(SequenceView):
    '''
    A table view of objects.

    This is a simple interface for displaying a table of objects and their attributes.

    This accepts a sequence of values which are assigned columns by a key.

    By default, for sequences, the key is the index in the sequence, and for mappings,
    the key is the key in the mapping.

    The columns are sized, and assigned a position in the table. A header name can be assigned.
    '''

    __columns: dict[str|int, Column] = {}
    @property
    def _columns(self):
        '''
        Get/set the columns. The columns will be updated to reflect the target's current state.

        If the order is set and has keys not in the columns, they will be removed from the order.
        If the order is not set, it will be set to the keys of the columns.
        '''
        self.__collect_columns(list(self._target_value))
        return self.__columns
    @_columns.setter
    def _columns(self, value):
        self.__columns = value
        for column in self.__columns.values():
            column.elements.clear()
            column._formatted.clear()
        if self.__order:
            self.__order = [key for key in self.__order if key in self.__columns]
        else:
            self.__order = list(self.__columns.keys())

    __order: list[str|int] = []
    @property
    def _order(self) -> list[str|int]:
        '''
        Get/set the order of the columns.
        '''
        if not self.__order:
            self.__order = list(self._columns.keys())
        return self.__order
    @_order.setter
    def _order(self, value):

        self.__order = value

    __heading_strategy: HeadingStrategy = 'heading-or-name'
    @property
    def _heading_strategy(self):
        '''
        Get/set the heading strategy.

        '''
        return self.__heading_strategy
    @_heading_strategy.setter
    def _heading_strategy(self, value):
        if value not in ('none', 'name', 'heading', 'heading-or-name'):
            raise ValueError(f'Invalid heading strategy: {value}')
        self.__heading_strategy = value

    _heading_separator: str = ' '
    '''
    The separator between headings.
    '''
    _cell_separator: str = ' '
    '''
    The separator between cells.
    '''

    def __init__(self, target: Iterable|_NoValue=_NO_VALUE,
                 columns: Optional[ColumnDict] = None,
                 order: Optional[ColumnKeys] = None,
                 heading_strategy: HeadingStrategy = 'heading-or-name',
                 heading_separator: str = ' ',
                 cell_separator: str = ' ',
                 **kwargs):

        '''
        Initialize the table view.

        :param target: The target to view.
        :param columns: The columns to use.
        '''
        super().__init__(target, **kwargs)
        self._columns = columns or {}
        self._order = order or []
        self._heading_strategy = heading_strategy
        self._heading_separator = heading_separator
        self._cell_separator = cell_separator

    def __identify_columns(self, target: Iterable|Mapping):
        '''
        Identify the columns in the table.

        This only identifies available columns, it does not collect the values.
        '''
        for row, value in enumerate(target):
            if isinstance(value, Mapping):
                for key, item in value.items():
                    if key not in self.__columns:
                        self.__columns[key] = Column(name=key)
                        self.__order.append(key)
            elif isinstance(value, Iterable):
                for index, item in enumerate(value):
                    if index not in self.__columns:
                        self.__columns[index] = Column(name=str(index))
                        self.__order.append(index)
            else:
               raise ValueError(f'Cannot identify columns for {value}')

    def __collect_columns(self, target: list):
        '''
        Collect the columns in the table.
        '''
        self.__identify_columns(target)
        # Clear the columns.
        for column in self.__columns.values():
            column.elements.clear()
        for value in target:
            for column in self.__columns.values():
                if not column.ignore:
                    column.elements.append(column.missing)
            if isinstance(value, Mapping):
                for key, item in value.items():
                    column = self.__columns[key]
                    if not column.ignore:
                        column.elements[-1] = item
            elif isinstance(value, Iterable):
                for index, item in enumerate(value):
                    column = self.__columns[index]
                    if not column.ignore:
                        column.elements[-1] = item
            else:
                raise ValueError(f'Cannot collect columns for {value}')
        # Update the heading widths without triggering a full update.
        self.__update_heading_widths(self.__ordered(self.__columns))

    def __update_heading_widths(self, ordered: list[Column]):
        '''
        Update the heading widths.
        '''
        for column, heading in zip(ordered, self.__headings(ordered)):
            column.heading_width = len(heading or '')

    def __headings(self, ordered: list[Column]) -> list[str|None]:
        '''
        Get the headings for the columns.
        '''
        headings: list[str|None]
        match self._heading_strategy:
            case 'none':
                headings = [None for c in ordered]
            case 'name':
                headings = [c.name for c in ordered]
            case 'heading':
                headings = [c.heading for c in ordered]
            case 'heading-or-name':
                headings = [c.heading or c.name for c in ordered]

        for heading, column in zip(headings, ordered):
            if heading is not None:
                column.heading_width = len(heading)
        return headings

    @property
    def _headings(self):
        '''
        Get the headings for the table.
        '''
        return self.__headings(self._ordered)

    @property
    def _widths(self):
        '''
        Get the widths of the columns.
        '''
        return (c.width for c in self._ordered)

    def __ordered(self, columns: dict[str|int, Column]):
        '''
        Get the ordered columns.
        '''
        return [columns[key] for key in self.__order]

    @property
    def _ordered(self):
        '''
        Get the ordered columns.
        '''
        return self.__ordered(self._columns)

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool) -> None:
        try:
            self._target_value
        except ValueError:
            p.text('TableView()')
            return
        # Only get this once, to avoid multiple passes collecting the columns.
        columns = self._ordered
        headings = self.__headings(columns)
        our_name = type(self).__name__
        their_name = type(self._target).__name__
        with p.group(0,f"{our_name}(type={their_name!r}, '''", "''')"):
            if any(headings):
                p.break_()
                fmt_headers = (
                    col.format.format(h or '', width=col.width)
                    for col, h in zip(columns, headings)
                )
                p.text(self._cell_separator.join(fmt_headers))
            p.break_()
            for row in zip(*(c.formatted for c in columns)):
                cols = (
                    col.format.format(c, width=col.width)
                    for col, c in zip(columns, row)
                )
                p.text(self._cell_separator.join(cols))
                p.break_()

