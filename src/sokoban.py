import logging
import string
import threading

from pathlib import Path

from nethack import NetHack
from term import Term
from point import Point

def read_solution(file_name: Path) -> list[tuple[list[list[str]], list[str]]]:
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
            solutions.append((sl_map, sl_steps))
            sl_map = []
            sl_steps = []
            line += 1

        sl_map.append(list(s[line][0:map_len]))
        if s[line][map_len + 1:]:
            sl_steps.append(s[line][map_len + 1:].strip())
        line += 1

    solutions.append((sl_map, sl_steps))
    return solutions

def match_map(solution, nh: NetHack) -> Point | None:
    sl_map = solution[0][0]
    start = None

    for y, _ in enumerate(sl_map):
        for x, _ in enumerate(_):
            if sl_map[y][x] == '@':
                start = nh.pos - Point(x, y)

    if not start:
        return None # can't be?

    for y, _ in enumerate(sl_map):
        for x, _ in enumerate(_):
            point = Point(x, y) + start
            if sl_map[y][x] == '#':
                if not nh.is_wall(point):
                    print(start, x, y, nh.at(point), sl_map[y][x])
                    return None
            if sl_map[y][x] == '<':
                if nh.at(point) != nh.STAIRS:
                    print(start, x, y, nh.at(point), sl_map[y][x])
                    return None
            if sl_map[y][x] in string.ascii_uppercase:
                if nh.at(point) != nh.BOULDER:
                    print(start, x, y, nh.at(point), sl_map[y][x])
                    return None

    return start


def run_solution(solution, nh: NetHack, step: int, start: Point) -> None:
    sl_map = solution[step][0]
    sl = solution[step][1]
    print('>>>>>>>>>>>>>>>>>>>>>>>>>')
    print(sl)
    for boulder in sl:
        char = boulder[0]
        moves = boulder[2:]

        b_pos = Point(-1, -1)

        for y, _ in enumerate(sl_map):
            for x, _ in enumerate(_):
                if sl_map[y][x] == char:
                    b_pos = Point(x, y)

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
            if not nh.check():
                break # boulder is finished manually or destroyed

            if (i + 1) < len(moves) and moves[i + 1] == '*':
                nh.check(b_pos + start, nh.EMPTY)
                sl_map[b_pos.y][b_pos.x] = '.'
                break
            if not nh.check(b_pos + start, nh.BOULDER):
                break # boulder is finished manually or destroyed

    step += 1
    if step < len(solution):
        run_solution(solution, nh, step, start)


def solve(nh: NetHack) -> None:
    solutions = (Path(__file__).parents[1] /
                 Path('res/sokoban/.txt')).glob("solution_*.txt")
    good = False
    for file in solutions:
        print(f'Checking solution: {file}')
        solution = read_solution(file)
        if (start := match_map(solution, nh)):
            print("Start:", start)
            run_solution(solution, nh, 0, start)
            good = True
            break

    if not good:
        print("Sorry, I couldn't match any solutions")

def test() -> None:
    logging.basicConfig(
        filename='log.txt',
        filemode='w',
        level=logging.DEBUG
    )

    # term = Term(fifo=False)
    # term.start()

    term = Term(fifo=True)
    t1 = threading.Thread(target=term.start, args=(), daemon=True)
    t1.start()

    nh = NetHack(term)

    input('Waiting...')

    nh.read_pos()
    solve(nh)
    nh.print()
    print(nh.pos)


test()
