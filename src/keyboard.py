# mypy: disable-error-code="misc"

import threading
import queue

from typing import Callable
from dataclasses import dataclass

from Xlib import X, XK, display
from Xlib.ext import record
from Xlib.protocol import rq


@dataclass(frozen=True)
class State:
    state: int = 0

    @property
    def shift(self) -> bool:
        return bool(self.state & 1)

    @property
    def ctrl(self) -> bool:
        return bool(self.state & 4)

    @property
    def alt(self) -> bool:
        return bool(self.state & 8)

    def __or__(self, other: 'State') -> 'State':
        return State(self.state | other.state)

Shift: State = State(1)
Ctrl: State = State(4)
Alt: State = State(8)

class Keyboard:

    def __init__(self) -> None:
        self.local_dpy = display.Display()
        self.record_dpy = display.Display()
        self.callbacks: list[Callable[[str, State]]] = []
        self.events: dict[tuple[str, State], threading.Event] = {}
        self.queue: queue.Queue[tuple[str, State]] = queue.Queue()

        # Check if the extension is present
        if not self.record_dpy.has_extension('RECORD'):
            raise ValueError('RECORD extension not found')

        # Create a recording context; we only want key and mouse events
        self.context = self.record_dpy.record_create_context(
                0,
                [record.AllClients],
                [{
                        'core_requests': (0, 0),
                        'core_replies': (0, 0),
                        'ext_requests': (0, 0, 0, 0),
                        'ext_replies': (0, 0, 0, 0),
                        'delivered_events': (0, 0),
                        'device_events': (X.KeyPress, X.KeyPress),
                        'errors': (0, 0),
                        'client_started': False,
                        'client_died': False,
                }])

    def add_callback(self, callback: Callable[[str, State], None]) -> None:
        self.callbacks.append(callback)

    def remove_callback(self, callback: Callable[[str, State], None]) -> None:
        self.callbacks.remove(callback)

    def lookup_keysym(self, keysym: int) -> str:
        for name in dir(XK):
            if name[:3] == 'XK_' and getattr(XK, name) == keysym:
                return name[3:]
        return f'[{keysym}]'

    def record_callback(self, reply: rq.DictWrapper) -> None:
        if reply.category != record.FromServer:
            return
        if reply.client_swapped:
            # received swapped protocol data, cowardly ignored
            return
        if not reply.data or reply.data[0] < 2:
            # not an event
            return

        data = reply.data
        while len(data):
            event, data = rq.EventField('').parse_binary_value(
                data, self.record_dpy.display, None, None)

            if event.type in [X.KeyPress, X.KeyRelease]:
                keysym = self.local_dpy.keycode_to_keysym(event.detail, 0)
                if not keysym:
                    continue

                key = self.lookup_keysym(keysym)
                state = State(event.state)
                for callback in self.callbacks:
                    callback(key, state)
                if ev := self.events.get((key, state)):
                    ev.set()
                self.queue.put_nowait((key, state))

    def start(self) -> None:
        # Enable the context; this only returns after a call to
        # record_disable_context, while calling the callback function in the
        # meantime
        self.record_dpy.record_enable_context(self.context, self.record_callback)

        # Finally free the context
        self.record_dpy.record_free_context(self.context)

    def wait(self, key: str, state: State = State()) -> None:
        event = threading.Event()
        self.events[(key, state)] = event
        event.wait()
        self.events.pop((key, state))

    def next(self) -> tuple[str, State]:
        return self.queue.get(block = True)

if __name__ == '__main__':
    kb = Keyboard()
    kb.add_callback(print)

    t1 = threading.Thread(target=kb.start, args=(), daemon=True)
    t1.start()

    print('hi')
    kb.wait('Escape', Ctrl | Alt)
    print('bye')
