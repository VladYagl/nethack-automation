import logging
from threading import Thread
from pathlib import Path

import sokoban
from term import Term
from nethack import NetHack

import keyboard
from keyboard import Keyboard


def main() -> None:
    logger = logging.getLogger('term')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler(
        Path(__file__).parents[1] / 'tmp' / 'term_log.txt',
        mode='w'
    ))
    # logger.setLevel(logging.INFO)
    # logger.addHandler(logging.StreamHandler())

    term = Term(logger, fifo=True)
    kb = Keyboard()
    nh = NetHack(term, kb)

    t1 = Thread(target=term.start, args=(), daemon=True)
    t1.start()

    t2 = Thread(target=kb.start, args=(), daemon=True)
    t2.start()

    t3 = Thread(target=nh.follow, args=(), daemon=True)
    t3.start()

    while True:
        key, state = kb.next()
        match (key, state):
            case ('s', keyboard.Ctrl):
                if nh:
                    sokoban.solve(nh)
            case ('space', keyboard.Shift):
                if nh:
                    nh.start_explore()
            case ('Escape', keyboard.Ctrl):
                break

main()
