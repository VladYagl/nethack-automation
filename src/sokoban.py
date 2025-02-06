import logging
import string
import threading

from pathlib import Path
from dataclasses import dataclass

from nethack import NetHack
from term import Term
from point import Point

@dataclass
class Solution:
    sl_map: list[list[str]]
    sl_steps: list[str]

def read_solution(file_name: Path) -> list[Solution]:
    with open(file_name, 'r') as fp:
        s = fp.read().splitlines()

    map_len = 0
    for i, _ in enumerate(s):
        s[i] = s[i].replace('|', '#').replace('-', '#')
        map_len = max(map_len, s[i].rfind('#') + 1)

    line = 0
    solutions = []

    sl_map: list[list[str]] = []
    sl_steps: list[str] = []

    while line < len(s):
        if not s[line]:
            solutions.append(Solution(sl_map, sl_steps))
            sl_map = []
            sl_steps = []
            line += 1

        sl_map.append(list(s[line][0:map_len]))
        if s[line][map_len + 1:]:
            sl_steps.append(s[line][map_len + 1:].strip())
        line += 1

    solutions.append(Solution(sl_map, sl_steps))
    return solutions

def match_map(solution: list[Solution], nh: NetHack) -> Point | None:
    sl_map = solution[0].sl_map
    start = None

    for y, row in enumerate(sl_map):
        for x, cell in enumerate(row):
            if cell == '@':
                start = nh.pos - Point(x, y)

    if not start:
        raise ValueError('This cannot be!')

    for y, row in enumerate(sl_map):
        for x, cell in enumerate(row):
            point = Point(x, y) + start
            if cell == '#':
                if not nh.is_wall(point):
                    print(start, x, y, nh.at(point), cell)
                    return None
            elif cell == '<':
                if nh.at(point) != nh.STAIRS:
                    print(start, x, y, nh.at(point), cell)
                    return None
            elif cell in string.ascii_uppercase:
                if nh.at(point) != nh.BOULDER:
                    print(start, x, y, nh.at(point), cell)
                    return None

    return start


def run_solution(solutions: list[Solution], nh: NetHack, start: Point) -> None:
    # pylint: disable=too-many-locals

    for solution in solutions:
        sl_map = solution.sl_map
        print('>>>>>>>>>>>>>>>>>>>>>>>>>')
        print(solution.sl_steps)
        for boulder in solution.sl_steps:
            char = boulder[0]
            moves = boulder[2:]

            b_pos: Point | None = None

            for y, row in enumerate(sl_map):
                for x, cell in enumerate(row):
                    if cell == char:
                        b_pos = Point(x, y)
                        break

            if not b_pos:
                raise ValueError(f"Can't find boulder {char}")

            for i, move in enumerate(moves):
                if move == ' ':
                    continue

                dr = nh.DIRECTIONS[move]
                to = b_pos + dr[1] * (-1)

                print(f'boulder={char} nh.pos={nh.pos} start={start}')
                print(f'to={to}, b_pos={b_pos}', dr)
                for s in sl_map:
                    print(''.join(s))

                if not nh.go_to(to + start):
                    break # boulder is finished manually or destroyed
                nh.press(nh.DIRECTIONS[move][0])
                nh.pos += nh.DIRECTIONS[move][1]
                sl_map[b_pos.y][b_pos.x] = '.'
                b_pos += nh.DIRECTIONS[move][1]
                sl_map[b_pos.y][b_pos.x] = char
                if not nh.check("Boulder didn't move?"):
                    break # boulder is finished manually or destroyed

                if (i + 1) < len(moves) and moves[i + 1] == '*':
                    nh.check("Boulder didn't fill the hole?", b_pos + start, nh.EMPTY)
                    sl_map[b_pos.y][b_pos.x] = '.'
                    break
                if not nh.check("Boulder didn't move?", b_pos + start, nh.BOULDER):
                    break # boulder is finished manually or destroyed


def solve(nh: NetHack) -> None:
    nh.read_pos()
    print(nh.symbol)

    solutions = (Path(__file__).parents[1] / 'res' / 'sokoban').glob("solution_*.txt")
    good = False
    for file in solutions:
        print(f'Checking solution: {file}')
        solution = read_solution(file)
        if start := match_map(solution, nh):
            print("Start:", start)
            nh.set_option('runmode', 't')
            nh.set_option('pile_limit', '2\n')

            run_solution(solution, nh, start)
            good = True

            nh.set_option('runmode', 'w')
            nh.set_option('pile_limit', '0\n')
            break

    if not good:
        print("Sorry, I couldn't match any solutions")


def test() -> None:
    logging.getLogger().addHandler(logging.NullHandler())

    term = Term(fifo=True)
    t1 = threading.Thread(target=term.start, args=(), daemon=True)
    t1.start()

    nh = NetHack(term)

    input('Waiting...')

    solve(nh)
    nh.print()
    print(nh.pos)

    input('Done!')

test()
