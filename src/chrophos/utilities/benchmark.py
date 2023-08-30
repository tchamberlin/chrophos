import time


class Benchmark:
    def __init__(self, description=None, logger=None):
        self._initial_time = time.perf_counter()
        self._logger = logger if logger else print
        self.description = "Did stuff" if description is None else description

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        _end = time.perf_counter()
        total_time = _end - self._initial_time
        self._logger(f"{self.description} in {total_time:.3f} seconds ")
