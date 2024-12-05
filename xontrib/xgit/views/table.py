'''
A table view of objects.
'''

from dataclasses import dataclass, field
from typing import (
    Any, Callable, Generic, Optional, TypeAlias,
    cast
)
from collections.abc import Iterable
from itertools import count

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import (
    _NO_VALUE, _NoValue,
    HeadingStrategy, ColumnKeys,
)
from xontrib.xgit.views.view import T, K, X, Rcv
from xontrib.xgit.views.multiview import MultiView, default_extractor

class ExtractorFnMulti(Generic[T,K,Rcv]):
    '''
    A function that extracts columns from a target.
    '''
    def __call__(self, target: T) -> Iterable[tuple[K, Rcv]]:
        '''
        Extract the columns from the target.
        '''
        ...

@dataclass
class Column:
    '''
    A column in a table view.
    '''
    name: str
    key: str|int = -2
    heading: Optional[str] = None
    heading_width: int = 0
    _width: int = field(default=-1, repr=False)
    @property
    def width(self):
        if self._width < 0:
            if len(self.elements) == 0:
                return 0
            self._width = max(self.heading_width,
                   max(len(e) for e in self.formatted))
        return self._width
    formatter: Optional[Callable[[Any], str]] = field(default=None, repr=False)
    format: str = '{:<{width}}'
    missing: str = ''
    ignore: bool = False
    ''''
    Whether to ignore the column. Ignored columns are not collected or displayed.
    '''
    elements: list[Any] = field(default_factory=list, repr=False)
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
    def reset(self):
        '''
        Reset the column.
        '''
        self.elements.clear()
        self._formatted.clear()
        self._width = -1

    def __repr__(self):
        args = [
            f'Column(name={self.name!r}',
            f'key={self.key!r}',
            f'heading={self.heading!r}' if self.heading else None,
            f'width={self.width!r}' if self.width >= 0 else None,
            f'missing={self.missing!r}' if self.missing else None,
            f'ignore={self.ignore!r}',
            f'format={self.format!r})',
        ]
        return ', '.join(a for a in args if a is not None)

ColumnDict: TypeAlias = dict[str|int, Column]

class TableView(MultiView[T,K,X,Rcv]):
    '''
    A table view of objects.

    This is a simple interface for displaying a table of objects and their attributes.

    This accepts a sequence of values which are assigned columns by a key.

    By default, for sequences, the key is the index in the sequence, and for mappings,
    the key is the key in the mapping.

    The columns are sized, and assigned a position in the table.
    A header name can be assigned.
    '''

    __columns: ColumnDict
    @property
    def _columns(self):
        '''
        Get/set the columns. The columns will be updated to reflect
        he target's current state.

        If the order is set and has keys not in the columns, they will
        be removed from the order. If the order is not set, it will be
        set to the keys of the columns.
        '''
        self.__collect_columns(self._target_value)
        return self.__columns

    @_columns.setter
    def _columns(self, value):
        self.__columns = value
        for column in self.__columns.values():
            column.reset()
        if self.__order:
            self.__order = [key for key in self.__order if key in self.__columns]
        else:
            self.__order = list(self.__columns.keys())

    __order: ColumnKeys
    @property
    def _order(self) -> ColumnKeys:
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

    _show_row_id: bool = False
    '''
    Whether to show the row ids.
    '''

    __column_extractor: Optional[ExtractorFnMulti[T,K,X]] = None

    @property
    def _column_extractor(self) -> ExtractorFnMulti[T,K,X]:
        '''
        Get/set the column extractor.
        '''
        val = self.__column_extractor
        if val is None:
            return cast(ExtractorFnMulti[T,K,X], default_extractor)
        return val

    @_column_extractor.setter
    def _column_extractor(self, value: Optional[ExtractorFnMulti[T,K,X]]):
        self.__column_extractor = value

    def __init__(self, target: T|_NoValue=_NO_VALUE,
                columns: Optional[ColumnDict] = None,
                column_extractor: Optional[ExtractorFnMulti[T,K,X]] = None,
                order: Optional[ColumnKeys] = None,
                heading_strategy: HeadingStrategy = 'heading-or-name',
                heading_separator: str = ' ',
                cell_separator: str = ' ',
                show_row_id: bool = False,
                **kwargs):

        '''
        Initialize the table view.

        :param target: The target to view.
        :param columns: The columns to use.
        '''
        super().__init__(target, **kwargs)
        self.__column_extractor = column_extractor
        self.__columns = columns or {}
        self.__order = order or []
        self._heading_strategy = heading_strategy
        self._heading_separator = heading_separator
        self._cell_separator = cell_separator
        self._show_row_id = show_row_id

    def __identify_columns(self, row: Any):
        '''
        Identify the columns in the table.

        This only identifies available columns, it does not collect the values.
        '''
        _, value = row
        columns = self.__columns
        order = self.__order
        ctr = count(len(columns))
        if -1 not in columns:
            columns[-1] = Column(name='Row',
                                 key=-1,
                                 ignore=not self._show_row_id)
            if len(order) == 0 and self._show_row_id:
                order[0:0] = [-1]
        column_extractor = self._column_extractor
        for key, _ in column_extractor(value):
            if not isinstance(key, (int, str)):
                key = next(ctr)
                while key in columns:
                    key = next(ctr)
            if key not in columns:
                columns[key] = Column(name=str(key), key=key)
                order.append(key)

    def __collect_columns(self, target: Iterable[tuple[K, Rcv]]):
        '''
        Collect the columns in the table.
        '''
        # Clear the columns.
        ctr = count(len(self.__columns))
        for column in self.__columns.values():
            column.reset()
        column_extractor = self._column_extractor
        for value in target:
            self.__identify_columns(value)
            for column in self.__columns.values():
                if not column.ignore:
                    column.elements.append(column.missing)
            row_id = self.__columns[-1]
            if not row_id.ignore:
                row_id.elements[-1] = value[0]
            for key, v in column_extractor(value[1]): # type: ignore
                if not isinstance(key, (int, str)):
                    key = next(ctr)
                column = self.__columns[key]
                if not column.ignore:
                    column.elements[-1] = v
        # Update the heading widths without triggering a full update.
        self.__update_heading_widths(self.__ordered(self.__columns))

    def __update_heading_widths(self, ordered: list[Column]):
        '''
        Update the heading widths.
        '''
        for column, heading in zip(ordered, self.__headings(ordered)):
            column.heading_width = len(str(heading or ''))

    def __headings(self, ordered: list[Column]) -> list[str|int|None]:
        '''
        Get the headings for the columns.
        '''
        headings: list[int|str|None]
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
                column.heading_width = len(str(heading))
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

    @property
    def _rows(self):
        '''
        Get the rows of the table.
        '''
        return zip(*(c.elements for c in self._ordered))

    @property
    def _formatted(self):
        '''
        Get the string-formatted rows.
        '''
        return zip(*(c.formatted for c in self._ordered))

    @property
    def _aligned(self):
        '''
        Get the rows with the cells padded and aligned.
        '''
        cols = self._ordered

        for row in self._formatted:
            yield tuple(c.format.format(e, width=c.width) for c, e in zip(cols, row))

    def _repr_pretty_(self, p: RepresentationPrinter, cycle: bool) -> None:
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

