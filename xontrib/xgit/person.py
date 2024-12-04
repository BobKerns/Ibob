'''
Represent a person with name and email, for either author or committer.

Also pair with a date, as CommittedBy referencing a date and person.
'''

from datetime import datetime
import re

from xonsh.lib.pretty import RepresentationPrinter

from xontrib.xgit.types import GitLoader, InitFn
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import xontrib.xgit.context_types as ct

class Person:
    '''
    A person with a name and email.
    '''
    __loader: GitLoader|None
    __name: str
    @property
    def name(self) -> str:
        if self.__loader:
            self.__loader()
        return self.__name
    __email: str
    @property
    def email(self) -> str:
        if self.__loader:
            self.__loader()
        return self.__email
    __full_name: str
    @property
    def full_name(self) -> str:
        return self.__full_name


    def __init__(self, line: str):
        self.__full_name = line
        def loader():
            self.__name, self.__email = line.split(' <', 1)
            self.__email = self.__email.rstrip('>')
            self.__loader = None
        self.__loader = loader

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Person):
            return False
        return self.full_name == other.full_name

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.name, self.email))

    def __repr__(self) -> str:
        return f"Person({self.name!r}, {self.email!r})"

    def __str__(self) -> str:
        return self.full_name

    def _repr_pretty(self, p: RepresentationPrinter, cycle: bool):
        p.text('Person(')
        p.breakable()
        p.text(f'{self.name!r},')
        p.breakable()
        p.text(f'{self.email!r})')

RE_SPLIT = re.compile(r'^(.*?) (\d+ [-+]\d{4})$')

class CommittedBy:
    '''
    A person and a date.
    '''
    __loader: GitLoader|None
    __person: Person
    @property
    def person(self) -> Person:
        if self.__loader:
            self.__loader()
        return self.__person
    __date: datetime|InitFn['CommittedBy', datetime]
    @property
    def date(self) -> datetime:
        if self.__loader:
            self.__loader()
        if callable(self.__date):
            self.__date = self.__date(self)
        return self.__date


    def __init__(self, line: str, *,
                 repository: 'ct.GitRepository'):
        def loader():
            match = RE_SPLIT.match(line)
            if not match:
                raise ValueError(f"Invalid CommittedBy line: {line!r}")
            person, date = match.groups()
            person_ = repository.context.people.get(person)
            if person_ is None:
                person_ = Person(person)
                repository.context.people[person] = person_
            self.__person = person_
            def date_loader(self):
                timestamp, _tz = date.split(' ')
                tz = datetime.strptime(_tz, "%z").tzinfo
                dt = datetime.fromtimestamp(int(timestamp), tz=tz)
                return dt
            self.__date = date_loader
            self.__loader = None
        self.__loader = loader

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CommittedBy):
            return False
        return self.person == other.person and self.date == other.date

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.person, self.date))

    def __repr__(self) -> str:
        return f"CommittedBy({self.person!r}, {self.date!r})"

    def __str__(self) -> str:
        return f"{self.person} on {self.date:%Y-%m-%d %H:%M:%S}"

    def _repr_pretty(self, p: RepresentationPrinter, cycle: bool):
        p.text('CommittedBy(')
        p.breakable()
        p.pretty(self.person)
        p.text(',')
        p.breakable()
        p.pretty(self.date)
        p.text(')')