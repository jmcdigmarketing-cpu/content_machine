class SignalRegistry:
    def __init__(self):
        self._registry = {}

    def register(self, name, func):
        self._registry[name] = func

    def unregister(self, name):
        """Remove a signal. Returns True if it was registered.

        Used for retirement (decisions §19): the provider module stays on disk for
        revival, but the signal never runs. Explicit so a retirement is a visible
        call rather than a mutation of the registry's internals.
        """
        return self._registry.pop(name, None) is not None

    def get_registered_signals(self):
        return self._registry
