"""
Based on the code from https://github.com/gns24/pydatomic project
"""
from uuid import UUID
from datetime import datetime
from collections import namedtuple

from .compat import texttype


class ImmutableDict(dict):
    _hash = None

    def __hash__(self):
        if self._hash is None:
            print('compute hash')
            self._hash = hash(frozenset(self.items()))
        return self._hash

    def _immutable(self):
        raise TypeError("{} object is immutable"
                        .format(self.__class__.__name__))

    __delitem__ = __setitem__ = _immutable
    clear = pop = popitem = setdefault = update = _immutable


class Symbol(texttype):

    def __repr__(self):
        return self


class Keyword(texttype):

    def __repr__(self):
        return ':{}'.format(self)


class List(tuple):

    def __repr__(self):
        return '[{}]'.format(' '.join(map(repr, self)))


class Tuple(tuple):

    def __repr__(self):
        return '({})'.format(' '.join(map(repr, self)))


class Dict(ImmutableDict):

    def __repr__(self):
        return '{{{}}}'.format(' '.join('{!r} {!r}'.format(*i)
                               for i in self.items()))


class Set(frozenset):

    def __repr__(self):
        return '#{{{}}}'.format(' '.join(map(repr, self)))


class TaggedElement(namedtuple('TaggedElement', 'name, value')):

    def __repr__(self):
        return '#{} {!r}'.format(self.name, self.value)


def coroutine(func):
    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr
    return start


@coroutine
def appender(l):
    while True:
        l.append((yield))


def inst_handler(time_string):
    return datetime.strptime(time_string[:23], '%Y-%m-%dT%H:%M:%S.%f')


TAG_HANDLERS = {'inst': inst_handler, 'uuid': UUID}

STOP_CHARS = " ,\n\r\t"

_CHAR_HANDLERS = {
    'newline': '\n',
    'space': ' ',
    'tab': '\t',
}

_CHAR_MAP = {
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}

_END_CHARS = {
    '#': '}',
    '{': '}',
    '[': ']',
    '(': ')',
}


@coroutine
def tag_handler(tag_name, tag_handlers):
    while True:
        c = (yield)
        if c in STOP_CHARS+'{"[(\\#':
            break
        tag_name += c
    elements = []
    handler = parser(appender(elements), tag_handlers)
    handler.send(c)
    while not elements:
        handler.send((yield))
    if tag_name in tag_handlers:
        yield tag_handlers[tag_name](elements[0]), True
    else:
        yield TaggedElement(tag_name, elements[0]), True
        yield None, True


@coroutine
def character_handler():
    r = (yield)
    while 1:
        c = (yield)
        if not c.isalpha():
            if len(r) == 1:
                yield r, False
            else:
                yield _CHAR_HANDLERS[r], False
        r += c


def parse_number(s):
    s = s.rstrip('MN').upper()
    if 'E' not in s and '.' not in s:
        return int(s)
    return float(s)


@coroutine
def number_handler(s):
    while 1:
        c = (yield)
        if c in "0123456789+-eEMN.":
            s += c
        else:
            yield parse_number(s), False


@coroutine
def symbol_handler(s):
    while 1:
        c = (yield)
        if c in '}])' + STOP_CHARS:
            if s[0] == ':':
                yield Keyword(s[1:]), False
            else:
                yield Symbol(s), False
        else:
            s += c


@coroutine
def parser(target, tag_handlers, stop=None):
    handler = None
    while True:
        c = (yield)
        if handler:
            v = handler.send(c)
            if v is None:
                continue
            else:
                handler = None
                v, consumed = v
                if v is not None:
                    target.send(v)
                if consumed:
                    continue
        if c == stop:
            return
        if c in STOP_CHARS:
            continue
        if c in 'tfn':
            expecting = {'t': 'rue', 'f': 'alse', 'n': 'il'}[c]
            for char in expecting:
                assert (yield) == char
            target.send({'t': True, 'f': False, 'n': None}[c])
        elif c == ';':
            while (yield) != '\n':
                pass
        elif c == '"':
            chars = []
            while 1:
                char = (yield)
                if char == '\\':
                    char = (yield)
                    char2 = _CHAR_MAP.get(char)
                    if char2 is not None:
                        chars.append(char2)
                    else:
                        chars.append(char)
                elif char == '"':
                    target.send(''.join(chars))
                    break
                else:
                    chars.append(char)
        elif c == '\\':
            handler = character_handler()
        elif c in '0123456789':
            handler = number_handler(c)
        elif c in '-.':
            c2 = (yield)
            if c2.isdigit():    # .5 should be an error
                handler = number_handler(c+c2)
            else:
                handler = symbol_handler(c+c2)
        elif c.isalpha() or c == ':':
            handler = symbol_handler(c)
        elif c in '[({#':
            if c == '#':
                c2 = (yield)
                if c2 != '{':
                    handler = tag_handler(c2, tag_handlers)
                    continue
            end_char = _END_CHARS[c]
            l = []
            p = parser(appender(l), tag_handlers, stop=end_char)
            try:
                while 1:
                    p.send((yield))
            except StopIteration:
                pass
            if c == '[':
                target.send(List(l))
            elif c == '(':
                target.send(Tuple(l))
            elif c == '{':
                if len(l) % 2:
                    raise Exception("Map literal must contain an even "
                                    "number of elements")
                target.send(Dict(zip(l[::2], l[1::2])))
            else:
                target.send(Set(l))
        else:
            raise ValueError("Unexpected character in edn", c)


def loads(s, tag_handlers=None):
    l = []
    target = parser(appender(l), dict(tag_handlers or (), **TAG_HANDLERS))
    for c in s.decode('utf-8'):
        target.send(c)
    target.send(' ')
    if len(l) != 1:
        raise ValueError("Expected exactly one top-level element "
                         "in edn string", s)
    return l[0]