class SignalRegistry:
    def __init__(self):
        self._registry = {}

    def register(self, name, func):
        self._registry[name] = func

    def get_registered_signals(self):
        return self._registry
