import copy
import logging
import sys
import threading

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Iterator, Self

from time import sleep

from point import Point

SCREEN_LOG_FIFO: Final[Path] = Path(__file__).parents[1] / Path('tmp/screen_log.fifo')
SCREEN_LOG_TXT: Final[Path] = Path(__file__).parents[1] / Path('tmp/screen_log.txt')

def crange(c1: str, c2: str) -> Iterator[str]:
    for c in range(ord(c1), ord(c2)+1):
        yield chr(c)

def chars(c1: str, c2: str) -> str:
    return ''.join(crange(c1, c2))

PARAMETER_BYTES: Final[str] = chars('0', '9') + ':;<=>?'
INTERMEDIATE_BYTES: Final[str] = '!"#$%&\'()*+,-./'
FINAL_BYTES: Final[str] = chars('A', 'Z') + chars('a', 'z') + '@[\\]^_`{|}~'

ESC: Final[str] = '\x1b'
CSI: Final[str] = '\x1b['

DEC_CHARSET = {
    0x60: '◆',
    0x61: '▒',
    0x62: '␉',
    0x63: '␌',
    0x64: '␍',
    0x65: '␊',
    0x66: '°',
    0x67: '±',
    0x68: '␤',
    0x69: '␋',
    0x6a: '┘',
    0x6b: '┐',
    0x6c: '┌',
    0x6d: '└',
    0x6e: '┼',
    0x6f: '⎺',
    0x70: '⎻',
    0x71: '─',
    0x72: '⎼',
    0x73: '⎽',
    0x74: '├',
    0x75: '┤',
    0x76: '┴',
    0x77: '┬',
    0x78: '│',
    0x79: '≤',
    0x7a: '≥',
    0x7b: 'π',
    0x7c: '≠',
    0x7d: '£',
    0x7e: '·',
}

@dataclass
class Attr:
    fg_color: int = 9
    bg_color: int = 9
    bold: bool = False
    inverse: bool = False

    def fg(self) -> int:
        if self.fg_color < 10:
            return self.fg_color + 30
        else:
            return self.fg_color + 80

    def bg(self) -> int:
        if self.bg_color < 10:
            return self.bg_color + 40
        else:
            return self.bg_color + 90

    def sgr(self) -> str:
        return ('0;' + ('7;' if self.inverse else '')
                     + ('1;' if self.bold else '')
                     + f'{self.fg()};' + f'{self.bg()}')

@dataclass
class Glyph:
    char: str = ' '
    attr: Attr = field(default_factory=Attr)

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.char == other
        elif isinstance(other, Glyph):
            return self.char == other.char and self.attr == other.attr
        else:
            return False


class Term:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, fifo: bool = True) -> None:
        self.width = 200
        self.height = 100
        self.glyphs: list[list[Glyph | None]] = [
            [None for x in range(self.width)] for y in range(self.height)
        ]
        self.charset = 'USASCII'
        self.show_cursor = True
        self.wrap = True
        self.attr = Attr()

        self.top = 1
        self.bottom = self.height - 1
        self.cursor = Point(1, 1)
        self.save_cursor: Point | None = None
        self.maxy = 0

        self.log = ''
        self.fifo = fifo
        self.stop = False

    def __enter__(self) -> Self:
        # pylint: disable=attribute-defined-outside-init
        self.idx = 0
        if self.fifo:
            self.fp = open(SCREEN_LOG_FIFO, 'r', encoding='utf8', newline='')
        else:
            self.fp = open(SCREEN_LOG_TXT, 'r', encoding='utf8', newline='')
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback) -> None:
        self.fp.close()

    def __getitem__(self, at: Point) -> None | Glyph:
        return self.glyphs[at.y][at.x]

    def __setitem__(self, at: Point, value: Glyph) -> None:
        self.glyphs[at.y][at.x] = value

    def at(self, x: int, y: int) -> None | Glyph:
        return self[Point(x, y)]

    def flush(self) -> None:
        if self.log:
            logging.info("String: '%s'", self.log)
            self.log = ''

    def print(self) -> None:
        if self.show_cursor:
            cur = self[self.cursor]
            if cur:
                cur.attr.inverse = True

        print(f'{ESC}[1;1H', end='') # Move cursor to the beginning
        for y, row in enumerate(self.glyphs):
            if y == 0:
                continue
            if y > self.maxy:
                break
            for x, c in enumerate(row):
                if x == 0:
                    continue
                if c:
                    print(CSI + c.attr.sgr() + 'm', end='')
                    print(c.char, end='')
                else:
                    print(CSI + '0m', end='')
                    print(' ', end='')
            print()

    def scroll(self, value: int = 1) -> None:
        if value > 0:
            for i in range(self.top, self.bottom, 1):
                self.glyphs[i] = self.glyphs[i + value]
            for i in range(self.bottom - value + 1, self.bottom + 1):
                self.glyphs[i] = [None for x in range(self.width)]
        else:
            for i in range(self.bottom, self.top, -1):
                self.glyphs[i] = self.glyphs[i + value]
            for i in range(self.top, self.top - value):
                self.glyphs[i] = [None for x in range(self.width)]

    def cursor_dx(self, dx: int) -> None:
        if dx > 0:
            for _ in range(dx):
                self.cursor.x += 1
                if self.cursor.x >= self.width:
                    if self.wrap:
                        self.cursor_dy(1)
                        self.cursor.x = 1
                    else:
                        self.cursor.x = self.width - 1
        else:
            for _ in range(-dx):
                self.cursor.x -= 1
                self.cursor.x = max(self.cursor.x, 1)

    def cursor_dy(self, dy: int) -> None:
        if dy > 0:
            for _ in range(dy):
                self.cursor.y += 1
                if self.cursor.y > self.bottom:
                    self.scroll(1)
                    self.cursor.y = self.bottom
        else:
            for _ in range(-dy):
                self.cursor.y -= 1
                if self.cursor.y < self.top:
                    self.scroll(-1)
                    self.cursor.y = self.top

    def handle_char(self, char: str) -> None:
        if self.charset == 'USASCII':
            if ord(char) in range(ord(' '), ord('~') + 1):
                self[self.cursor] = Glyph(char, copy.copy(self.attr))
                self.log += char
            else:
                self.flush()
                logging.info('ORD: %d %s', ord(char), char)
                match ord(char):
                    case 10: # Line Feed
                        self.cursor_dy(1)
                        self.cursor.x = 1
                    case 13: # Carriage Return
                        self.cursor.x = 1
                    case 8: # Backspace
                        self.cursor_dx(-1)
                    case _:
                        logging.error('Unknown ASCII: %d %s', ord(char), char)
                        # Read the char anyway
                        self[self.cursor] = Glyph(char, copy.copy(self.attr))
                        self.cursor_dx(1)
                return
        if self.charset == 'DEC':
            self.flush()
            self[self.cursor] = Glyph(
                DEC_CHARSET[ord(char)], copy.copy(self.attr)
            )
        self.cursor_dx(1)
        self.maxy = max(self.maxy, self.cursor.y)

    def clearFrom(self) -> None:
        x = self.cursor.x
        y = self.cursor.y
        while True:
            self.glyphs[y][x] = Glyph()
            x += 1
            if x >= self.width:
                x = 1
                y += 1
                if y >= self.height:
                    break

    def clearTo(self) -> None:
        x = 1
        y = 1
        while True:
            self.glyphs[y][x] = Glyph()
            x += 1
            if x > self.cursor.x and y == self.cursor.y:
                break
            if x >= self.width:
                x = 1
                y += 1

    # https://xtermjs.org/docs/api/vtfeatures/#csi
    def handle_csi(self, csi: str) -> None:
        match csi[-1]:
            case 'J':
                match getPs(csi, 0):
                    case 0:
                        self.clearFrom()
                    case 1:
                        self.clearTo()
                    case 2:
                        # pylint: disable=unnecessary-dunder-call
                        self.__init__(self.fifo) # type: ignore
                    case _:
                        logging.error('Unknown CSI: %s', ansitostr(csi))
            case 'H':
                self.cursor.y, self.cursor.x = getPm(csi, [1, 1])
            case 'r':
                self.top, self.bottom = getPm(csi, [1, self.height])
            case 'G':
                self.cursor.x = getPs(csi, 1)
            case 'd':
                self.cursor.y = getPs(csi, 1)
            case 'A':
                self.cursor_dy(-getPs(csi, 1))
            case 'B':
                self.cursor_dy(getPs(csi, 1))
            case 'C':
                self.cursor_dx(getPs(csi, 1))
            case 'D':
                self.cursor_dx(-getPs(csi, 1))
            case 'K':
                match getPs(csi, 0):
                    case 0:
                        for x in range(self.cursor.x, self.width):
                            self.glyphs[self.cursor.y][x] = Glyph()
                    case 1:
                        for x in range(0, self.cursor.x):
                            self.glyphs[self.cursor.y][x] = Glyph()
                    case 2:
                        for x in range(0, self.width):
                            self.glyphs[self.cursor.y][x] = Glyph()
            case 'T':
                self.scroll(-getPs(csi, 1))
            case 'S':
                self.scroll(getPs(csi, 1))
            case 'X':
                tx = self.cursor.x
                for _ in range(getPs(csi, 1)):
                    self.glyphs[self.cursor.y][tx] = Glyph()
                    tx += 1
            case 'm':
                if csi[2] == '>':
                    return # Set/reset key modifier options (XTMODKEYS), xterm.
                if not csi[2: -1]:
                    self.attr = Attr()
                    return
                for atc in csi[2: -1].split(';'):
                    try:
                        at = int(atc)
                    except ValueError:
                        logging.warning('Unsupported text attribute: %d %s',
                                        atc, ansitostr(csi))
                        continue
                    match at:
                        case 0:
                            self.attr = Attr()
                        case 7:
                            self.attr.inverse = not self.attr.inverse
                        case 1:
                            self.attr.bold = True
                        case at if at in range(30, 40):
                            self.attr.fg_color = int(at) - 30
                        case at if at in range(40, 50):
                            self.attr.bg_color = int(at) - 40
                        case at if at in range(90, 98):
                            self.attr.fg_color = int(at) - 80
                        case at if at in range(100, 108):
                            self.attr.bg_color = int(at) - 90
                        case _:
                            logging.warning('Unsupported text attribute: %d %s',
                                            at, ansitostr(csi))
            case 'l' | 'h':
                # Set various terminal attributes
                match csi[2: -1]:
                    case '?25':
                        self.show_cursor = csi[-1] == 'h'
                    case '?7':
                        self.wrap = csi[-1] == 'h'
                    case s if s in ['?12', '?1', '?1049', '4', '?1034', '?2004']:
                        logging.warning('Unsupported Terminal attribute: %s',
                                        ansitostr(csi))
                    case _:
                        logging.error('Unknown Terminal attribute: %s',
                                      ansitostr(csi))
            case 't':
                # IDK, this is some bullshit
                logging.warning('Unsupported CSI: %s', ansitostr(csi))
            case _:
                logging.error('Unknown CSI: %s', ansitostr(csi))

    def read(self) -> str:
        if self.fifo:
            while not (c := self.fp.read(1)):
                pass
            return c
        else:
            if not (c := self.fp.read(1)):
                self.stop = True
                return ESC
            return c

    def start(self) -> None:
        with self as x:
            x.run()

    def run(self) -> None:
        while not self.stop:
            s = self.read()
            if len(sys.argv) > 1 and self.idx > int(sys.argv[1]):
                self.print()
                sys.exit()
            if s != ESC:
                self.handle_char(s)
            else:
                self.flush()
                s += self.read()
                match s[-1]:
                    case '[': # CSI
                        s += self.read()
                        while s[-1] not in FINAL_BYTES:
                            s += self.read()

                        self.handle_csi(s)

                    case ']': # OSC
                        s += self.read()
                        while ord(s[-1]) != 7: # BEL
                            s += self.read()

                    case '(': # Charset
                        s += self.read()
                        match s[-1]:
                            case '0':
                                self.charset = 'DEC'
                            case 'B':
                                self.charset = 'USASCII'
                            case _:
                                logging.error('Charset: %s %s', s[-1],
                                              ansitostr(s))
                    case 'M': # Move up
                        self.cursor_dy(-1)
                    case '7': # Save cursor
                        self.save_cursor = self.cursor
                    case '8': # Restore cursor
                        self.cursor = self.save_cursor or self.cursor
                    case '=' | '>' | ']':
                        logging.warning('Unsupported ANSI: %s', ansitostr(s))
                    case _:
                        logging.error('Unknown ANSI: %s', ansitostr(s))

                logging.info('ANSI: %s', ansitostr(s))

def ansitostr(csi: str) -> str:
    return csi.replace(ESC, "ESC")

def getPm(csi: str, default: list[int]) -> Iterator[int]:
    if not csi[2: -1]:
        yield from default
    else:
        for x in csi[2: -1].split(';'):
            try:
                yield int(x)
            except ValueError:
                logging.error('Unsupported Ps: %s %s', x, ansitostr(csi))
                yield from default
                break

def getPs(csi: str, default: int) -> int:
    return next(getPm(csi, [default]))

def test() -> None:
    logging.basicConfig(
        filename='log.txt',
        filemode='w',
        level=logging.DEBUG
    )

    term = Term()
    # term.start()
    # term.print()

    t1 = threading.Thread(target=term.start, args=(), daemon=True)
    t1.start()

    print(f'{ESC}[2J')   # Clean screen
    while True:
        sleep(0.1)
        if not t1.is_alive():
            break
        term.print()


if __name__ == '__main__':
    test()
