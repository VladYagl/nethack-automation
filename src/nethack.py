import logging
import subprocess
import re
import string

from point import Point
from term import Term, Glyph, DEC_CHARSET

class NetHack:
    WIDTH = 80
    HEIGHT = 21
    START = Point(2, 6)

    BOULDER = Glyph('0')
    STAIRS = Glyph('<')
    EMPTY = Glyph('·')

    ENEMIES = list(string.ascii_letters) + ['\'', '&', ':']

    DIRECTIONS = {
        'd': ('j', Point( 0,  1)),
        'u': ('k', Point( 0, -1)),
        'l': ('h', Point(-1,  0)),
        'r': ('l', Point( 1,  0)),
    }

    def __init__(self, term: Term) -> None:
        self.pos: Point
        self.symbol: Glyph
        self.term = term
        self.read_pos()

    def read_pos(self) -> None:
        self.term.do_yield()
        self.pos = self.term.cursor - self.START
        if glyph := self.term[self.term.cursor]:
            self.symbol = glyph

    def at(self, point: Point) -> Glyph | None:
        if point.x >= self.WIDTH:
            return None
        if point.y >= self.HEIGHT:
            return None
        return self.term[point + self.START]

    def is_wall(self, point: Point) -> bool:
        glyph = self.at(point)
        for (code, symbol) in DEC_CHARSET.items():
            if glyph and glyph.char == symbol:
                return code in range(0x6a, 0x79)
        return False

    def print(self) -> None:
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if glyph := self.at(Point(x, y)):
                    print(glyph, end='')
                else:
                    print(' ', end='')
            print()

    def has_enemies(self) -> Glyph | None:
        self.term.do_yield()
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if Point(x, y) != self.pos:
                    glyph = self.at(Point(x, y))
                    if glyph and glyph.char in self.ENEMIES:
                        return glyph
        return None

    def check(self, msg: str, pos: Point | None = None, symbol: Glyph | None = None) -> bool:
        if not pos:
            pos = self.pos
        if not symbol:
            symbol = self.symbol

        cnt = 0
        while self.at(self.pos) != self.symbol:
            cnt += 1
            self.term.do_yield()
            if cnt > 2000:
                print(f'{msg}\n{pos}: {self.at(self.pos)} != {symbol}')
                if input() == 'skip':
                    return False
                return self.check(msg, pos, symbol)

        if enemy := self.has_enemies():
            input(f'Map has enemies "{enemy}"!')
            return self.check(msg, pos, symbol)

        return True

    def PRESS(self, c: str) -> str:
        return f'screen -x -S "nethack" -X stuff "{c}"'

    def run(self, command: str) -> None:
        subprocess.run([command], shell=True, check=True)

    def press(self, c: str) -> None:
        self.run(self.PRESS(c))

    def move_cursor(self, from_point: Point, to_point: Point) -> None:
        diff = to_point - from_point

        while diff.y != 0:
            if diff.y > 0:
                d = 'd'
            else:
                d = 'u'
            self.press(self.DIRECTIONS[d][0])
            diff += self.DIRECTIONS[d][1] * (-1)

        while diff.x != 0:
            if diff.x > 0:
                d = 'r'
            else:
                d = 'l'
            self.press(self.DIRECTIONS[d][0])
            diff += self.DIRECTIONS[d][1] * (-1)

    def go_to(self, to_point: Point) -> bool:
        self.press('-')
        self.press('@')
        self.move_cursor(self.pos, to_point)
        self.press('.')

        self.pos = to_point
        return self.check('Failed travel')

    def set_option(self, option: str, value: str) -> None:
        self.press('O')
        page = 1

        while True:
            while not (last := re.search(fr'\(Page {page} of (\d)\)',
                                         self.term.line(self.term.maxy - 1))):
                self.term.do_yield()

            for line in self.term.lines():
                if m := re.search(fr'([a-zA-Z])\) {option} ', line):
                    self.press(m.group(1))

            self.press(' ')
            if int(last.group(1)) == page:
                break
            page += 1

        self.press(value)

def test() -> None:
    logging.basicConfig(
        filename='log.txt',
        filemode='w',
        level=logging.DEBUG
    )

    term = Term(fifo=False)
    term.start()

    nh = NetHack(term)
    nh.print()



if __name__ == '__main__':
    test()
