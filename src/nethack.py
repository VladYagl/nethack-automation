import threading
import logging
import subprocess
import string

from point import Point
from term import Term, Glyph, DEC_CHARSET

from time import sleep

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

    def __init__(self, term) -> None:
        self.term: Term = term
        self.read_pos()

    def read_pos(self) -> None:
        self.pos = self.term.cursor - self.START
        self.symbol = self.term[self.term.cursor]

    def at(self, point) -> Glyph | None:
        if point.x >= self.WIDTH:
            return None
        if point.y >= self.HEIGHT:
            return None
        return self.term[point + self.START]

    def is_wall(self, point) -> bool:
        glyph = self.at(point)
        for (code, symbol) in DEC_CHARSET.items():
            if glyph and glyph.char == symbol:
                return code in range(0x6a, 0x79)
        return False

    def print(self):
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if self.at(Point(x, y)):
                    print(self.at(Point(x, y)).char, end='')
                else:
                    print(' ', end='')
            print()

    def has_enemies_impl(self) -> bool:
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if Point(x, y) != self.pos:
                    glyph = self.at(Point(x, y))
                    if glyph and glyph.char in self.ENEMIES:
                        return True
        return False

    def has_enemies(self) -> bool:
        if self.has_enemies_impl():
            sleep(0.02)
            return self.has_enemies_impl()
        return False

    def check(self, pos=None, symbol=None):
        if not pos:
            pos = self.pos
        if not symbol:
            symbol = self.symbol

        cnt = 0
        while self.at(self.pos) != self.symbol:
            cnt += 1
            sleep(0.001)
            if cnt > 5000:
                print(f'{pos}: {self.at(self.pos)} != {symbol}')
                if input() == 'skip':
                    return False
                return self.check(pos, symbol)

        if self.has_enemies():
            input('Map has enemies!')
            return self.check(pos, symbol)

        return True

    def PRESS(self, c):
        return f'screen -x -S "nethack" -X stuff "{c}"'

    def run(self, command, *argv, **kwargs):
        subprocess.run([command], shell=True, check=True, *argv, **kwargs)
        # print(command)

    def press(self, c):
        self.run(self.PRESS(c))

    def move_cursor(self, from_point, to_point):
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

    def go_to(self, to_point):
        self.press('-')
        self.press('@')
        self.move_cursor(self.pos, to_point)
        self.press('.')

        self.pos = to_point
        return self.check()

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
