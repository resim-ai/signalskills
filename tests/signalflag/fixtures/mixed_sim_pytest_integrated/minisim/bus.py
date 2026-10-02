from collections import defaultdict

class Bus:
    """In-process pub/sub. Keeps every message so tests can inspect them."""
    def __init__(self):
        self.messages = defaultdict(list)   # topic -> [(stamp_ns, msg)]
        self._subs = []

    def subscribe(self, fn):
        """fn(topic, stamp_ns, msg) for every message on every topic."""
        self._subs.append(fn)

    def publish(self, topic: str, stamp_ns: int, msg: dict) -> None:
        self.messages[topic].append((stamp_ns, msg))
        for fn in self._subs:
            fn(topic, stamp_ns, msg)
