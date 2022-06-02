from __future__ import annotations

class Hook:
    def __init__(self):
        self.callbacks = []

    def __call__(self, *args, **kwargs):
        for c in self.callbacks:
            c(*args, **kwargs)

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        self.callbacks.remove(callback)

class Runner:
    def __init__(self):
        self.start = Hook()
        self.stop = Hook()

