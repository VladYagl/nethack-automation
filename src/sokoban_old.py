import os
import subprocess
import unicodedata
import string
import glob

from pprint import pp

from time import sleep

ENEMIES = list(string.ascii_letters) + ['\'', '&', ':']
HARDCOPY = f'screen -x -S "nethack" -X hardcopy {os.getcwd()}/hardcopy.txt'
def PRESS(c):
    return f'screen -x -S "nethack" -X stuff "{c}"'

def run(command, *argv, **kwargs):
    subprocess.run([command], shell=True, check=True, *argv, **kwargs)

    print(command)
    sleep(0.03)

def press(c):
    run(PRESS(c))

class Point:
    def __init__(self, i, j):
        self.i = i
        self.j = j

    def __add__(self, other):
        return Point(self.i + other.i, self.j + other.j)

    def __sub__(self, other):
        return Point(self.i - other.i, self.j - other.j)

    def __mul__(self, k):
        return Point(self.i * k, self.j * k)

    def __repr__(self):
        return f'({self.i}; {self.j})'

class NetHack:
    def __init__(self):
        self.map = []
        self.log = []
        self.simple = None
        self.pos = None
        self.symbol = None


    def read(self):
        self.map = []
        self.log = []

        has_enemies = False

        run(HARDCOPY)

        with open('./hardcopy.txt', 'r') as fp:
            s = fp.readlines()

        line = 5
        while s[line][2] == ' ':
            self.map.append(s[line][1:81])
            line += 1

        for i, _ in enumerate(self.map):
            for j, _ in enumerate(_):
                if 'BOX DRAWINGS' in unicodedata.name(self.map[i][j]):
                    self.map[i] = self.map[i].replace(self.map[i][j], '#')
                if (self.pos and self.map[i][j] in ENEMIES
                             and (self.pos.i != i or self.pos.j != j)):
                    has_enemies = True

        line += 2

        while line < len(s) and any(x != ' ' for x in s[line][1:81]):
            self.log.append(s[line][1:81])
            line += 1

        self.make_simple()

        if has_enemies:
            input('Map has enemies!')


    def make_simple(self):
        minc = 3000
        maxc = 0
        for line in self.map:
            maxc = max(maxc, line.rfind('#') + 1)
            if line.find('#') > 0:
                minc = min(minc, line.find('#'))

        self.simple = [line[minc:maxc] for line in self.map
                    if any(c != ' ' for c in line)]


    def print(self):
        print('\n'.join(self.map))
        print('LOG:')
        print('\n'.join(self.log))


    def at(self, point):
        if point.i >= len(self.simple):
            return None
        if point.j >= len(self.simple[point.i]):
            return None
        return self.simple[point.i][point.j]

    def check(self, pos=None, symbol=None, deep=0):
        if not pos:
            pos = self.pos
        if not symbol:
            symbol = self.symbol

        self.read()
        if self.at(self.pos) != self.symbol:
            if deep < 10:
                sleep(0.15)
                return self.check(pos, symbol, deep + 1)
            else:
                print(f'{pos}: {self.at(self.pos)} != {symbol}')
                if input() == 'skip':
                    return False
                return self.check(pos, symbol, 0)

        return True

def read_solution(file_name):
    with open(file_name, 'r') as fp:
        s = fp.read().splitlines()

    map_len = 0
    for i, _ in enumerate(s):
        s[i] = s[i].replace('|', '#').replace('-', '#')
        map_len = max(map_len, s[i].rfind('#') + 1)

    line = 0
    solutions = []

    sl_map = []
    sl_steps = []

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


def match_map(solution, nh, step=0):
    sl_map = solution[step][0]

    for i, _ in enumerate(sl_map):
        for j, _ in enumerate(_):
            point = Point(i, j)
            if sl_map[i][j] in ['#', '<']: # '^',
                if nh.at(point) != sl_map[i][j]:
                    print(i, j, nh.at(point), sl_map[i][j])
                    return None
            if sl_map[i][j] in string.ascii_uppercase:
                if nh.at(point) != '0':
                    print(i, j, nh.at(point), sl_map[i][j])
                    return None
            if step == 0:
                if sl_map[i][j] == '@':
                    nh.pos = Point(i, j)
                    nh.symbol = nh.at(point)
    return True

DIRECTIONS = {
    'd': ('j', Point( 1,  0)),
    'u': ('k', Point(-1,  0)),
    'l': ('h', Point( 0, -1)),
    'r': ('l', Point( 0,  1)),
}

def nh_move_cursor(from_point, to_point):
    diff = to_point - from_point

    while diff.i != 0:
        if diff.i > 0:
            d = 'd'
        else:
            d = 'u'
        press(DIRECTIONS[d][0])
        diff += DIRECTIONS[d][1] * (-1)

    while diff.j != 0:
        if diff.j > 0:
            d = 'r'
        else:
            d = 'l'
        press(DIRECTIONS[d][0])
        diff += DIRECTIONS[d][1] * (-1)

def go_to(from_point, to_point, nh):
    press('-')
    press('@')
    nh_move_cursor(from_point, to_point)
    press('.')

    nh.pos = to_point
    return nh.check()

def run_solution(solution, nh, step=0):
    sl_map = solution[step][0]
    sl = solution[step][1]
    print('>>>>>>>>>>>>>>>>>>>>>>>>>')
    print(sl)
    for boulder in sl:
        char = boulder[0]
        moves = boulder[2:]

        b_pos = None

        for i, _ in enumerate(sl_map):
            for j, _ in enumerate(_):
                if sl_map[i][j] == char:
                    b_pos = Point(i, j)

        for i, move in enumerate(moves):
            if move == ' ':
                continue

            dr = DIRECTIONS[move]
            to = b_pos + dr[1] * (-1)

            print(f'boulder={char} nh.pos={nh.pos}')
            print(f'to={to}, b_pos={b_pos}', dr)
            for s in sl_map:
                print(''.join(s))

            if not go_to(nh.pos, to, nh):
                break # boulder is finished manually or destroyed
            press(DIRECTIONS[move][0])
            nh.pos += DIRECTIONS[move][1]
            sl_map[b_pos.i][b_pos.j] = '.'
            b_pos += DIRECTIONS[move][1]
            sl_map[b_pos.i][b_pos.j] = char
            if not nh.check():
                break # boulder is finished manually or destroyed

            if (i + 1) < len(moves) and moves[i + 1] == '*':
                nh.check(b_pos, '·')
                break
            if not nh.check(b_pos, '0'):
                break # boulder is finished manually or destroyed

    step += 1
    if step < len(solution):
        run_solution(solution, nh, step)

def main():
    nh = NetHack()
    nh.read()

    solutions = glob.glob("./solution_*.txt")
    good = False
    for file in solutions:
        print(f'Checking solution: {file}')
        solution = read_solution(file)
        if match_map(solution, nh):
            run_solution(solution, nh)
            good = True
            break

    if not good:
        print("Sorry, I couldn't match any solutions")

    # print_nh(nh_map, nh_log)
    # pp(solution)


main()
