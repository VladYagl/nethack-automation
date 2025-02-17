import logging
import subprocess
import re
import string

from threading import Condition

from point import Point
from term import Term, Glyph, DEC_CHARSET
import keyboard
from keyboard import Keyboard

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

        'ul': ('y', Point( -1,  -1)),
        'ur': ('u', Point( 1, -1)),
        'dl': ('n', Point(-1,  1)),
        'dr': ('b', Point( 1,  1)),
    }

    def __init__(self, term: Term, kb: Keyboard) -> None:
        self.pos: Point
        self.symbol: Glyph
        self.finished_init = False
        self.term = term
        self.keyboard = kb
        self.condition = Condition()
        self.skip = False
        self.dlvl = -1
        self.visited: dict[int, list[Point]] = {}

        def handle_keys(key: str, state: keyboard.State) -> None:
            match (key, state):
                case ('Return', keyboard.Ctrl):
                    with self.condition:
                        self.condition.notify_all()
                case ('Return', keyboard.Alt):
                    with self.condition:
                        self.skip = True
                        self.condition.notify_all()

        self.keyboard.add_callback(handle_keys)

    def read_pos(self) -> bool:
        glyph = self.term[self.term.cursor]
        if (not glyph) or (self.finished_init and glyph != self.symbol):
            return False

        self.pos = self.term.cursor - self.START
        self.symbol = glyph
        self.finished_init = True

        if dlvl := re.search(r'Dlvl:(\d*)', self.term.line(3)):
            self.dlvl = int(dlvl.group(1))

        print(self.pos, self.symbol, self.dlvl)

        return True

    def at(self, point: Point) -> Glyph | None:
        if point.x >= self.WIDTH:
            return None
        if point.y >= self.HEIGHT:
            return None
        return self.term[point + self.START]

    def is_unknown(self, point: Point) -> bool:
        glyph = self.at(point)
        if not glyph or glyph.char == ' ':
            return True
        return False

    def is_wall(self, point: Point) -> bool:
        glyph = self.at(point)
        for (code, symbol) in DEC_CHARSET.items():
            if glyph and glyph.char == symbol:
                return code in range(0x6a, 0x79)
        return False

    def is_covered(self) -> bool:
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                p = Point(x, y)
                if self.is_wall(p) and (glyph := self.at(p)):
                    if glyph.attr.fg_color == 5:
                        return True
        return False

    def print(self) -> None:
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if glyph := self.at(Point(x, y)):
                    print(glyph, end='')
                else:
                    print('#', end='')
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

    def wait(self) -> bool:
        with self.condition:
            self.skip = False
            self.condition.wait()
            return not self.skip

    def check(self, msg: str, pos: Point | None = None, symbol: Glyph | None = None) -> bool:
        if not pos:
            pos = self.pos
        if not symbol:
            symbol = self.symbol

        cnt = 0
        while self.at(pos) != symbol:
            cnt += 1
            self.term.do_yield()
            if cnt > 500:
                print(f'{msg}\n{pos}: {self.at(pos)} != {symbol}')
                if not self.wait():
                    return False
                return self.check(msg, pos, symbol)

        if enemy := self.has_enemies():
            print(f'Map has enemies "{enemy}"!')
            self.wait()
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

        if not self.check('Failed travel', to_point):
            return False

        while not self.read_pos():
            self.term.do_yield()

        return self.pos == to_point

    def set_option(self, option: str, value: str) -> None:
        self.press('O')
        page = 1

        while True:
            while not (last := re.search(fr'\(Page {page} of (\d*)\)',
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

    def follow(self) -> None:
        while True:
            with self.term.redraw:
                self.term.redraw.wait()

                if self.is_covered() or (not self.read_pos()) or (not self.finished_init):
                    continue

                if self.dlvl not in self.visited:
                    self.visited[self.dlvl] = []
                self.visited[self.dlvl].append(self.pos)


    def start_explore(self) -> None:
        self.press('-')
        self.press('x')
        self.press('.')
        # while self.explore():
            # pass

    # def explore(self) -> bool:
    #     checked = set([self.pos])
    #     queue = [self.pos]
    #     while queue:
    #         p = queue.pop(0)

    #         for (_, d) in self.DIRECTIONS.items():
    #             if self.is_unknown(p + d[1]) and (p not in self.visited[self.dlvl]):
    #                 if not self.go_to(p):
    #                     print('Skipping', p)
    #                     self.visited[self.dlvl].append(p)
    #                 return True

    #             if ((p + d[1]) not in checked
    #                     and not self.is_unknown(p + d[1])
    #                     and not self.is_wall((p + d[1]))):
    #                 checked.add(p + d[1])
    #                 queue.append(p + d[1])

    #     print('Nowhere to go!')
    #     return False

def test() -> None:
    logging.basicConfig(
        filename='log.txt',
        filemode='w',
        level=logging.DEBUG
    )

    term = Term(fifo=False)
    term.start()
    kb = Keyboard()

    nh = NetHack(term, kb)
    nh.print()



if __name__ == '__main__':
    test()
