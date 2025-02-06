import logging
import threading

from pathlib import Path

import sokoban
from term import Term
from nethack import NetHack

def main() -> None:
    logger = logging.getLogger('term')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler(
        Path(__file__).parents[1] / 'tmp' / 'term_log.txt',
        mode='w'
    ))

    term = Term(logger, fifo=True)
    t1 = threading.Thread(target=term.start, args=(), daemon=True)
    t1.start()

    nh = NetHack(term)
    sokoban.solve(nh)

main()
