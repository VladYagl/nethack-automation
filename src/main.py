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

    term = Term(logger, fifo=True)
    kb = Keyboard()

    t1 = Thread(target=term.start, args=(), daemon=True)
    t1.start()

    t2 = Thread(target=kb.start, args=(), daemon=True)
    t2.start()

    nh = NetHack(term, kb)

    def handle_keys(key: str, state: keyboard.State) -> None:
        # mypy: disable-error-code="misc"
        match (key, state):
            case ('s', keyboard.Ctrl):
                if nh:
                    nhl = [nh]
                    Thread(target=sokoban.solve, args=nhl, daemon=True).start()

    kb.add_callback(handle_keys)

    kb.wait('Escape', keyboard.Ctrl)
    # kb.start()

main()
