import random
from threading import Timer


# https://stackoverflow.com/a/56169014
class ResettableTimer:
    def __init__(self, function, interval_lb=1500, interval_ub=1750):
        self.interval = (interval_lb, interval_ub)
        self.function = function
        self.timer = Timer(self._interval(), self.function)

    def _interval(self):
        # in millis
        self.gen_time = random.randint(*self.interval) / 1000
        return self.gen_time

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.cancel()

    def reset(self):
        self.timer.cancel()
        self.timer = Timer(self._interval(), self.function)
        self.timer.start()
