import logging
import statistics
import time
from pathlib import Path

import typer

from chrophos.camera.backend import Backend
from chrophos.camera.camera import open_camera
from chrophos.config import CameraConfig

logger = logging.getLogger(__name__)

app = typer.Typer()


def print_stats(prefix: str, dark_times: list[float]):
    min_dark_time = min(dark_times)
    max_dark_time = max(dark_times)
    avg_dark_time = statistics.mean(dark_times)
    print(prefix)
    print(f"  Min:  {min_dark_time:.2f}")
    print(f"  Mean: {avg_dark_time:.2f}")
    print(f"  Max:  {max_dark_time:.2f}")


def bench_dark_time_for_shutter_speed(
    trials: int,
    shutter: str,
    backend: Backend,
    config: CameraConfig,
    output_dir: Path,
):
    """Benchmark the dark time at a given shutter speed

    Dark time: the time required between the end of a capture and the start of the next
    """

    dark_times = []
    with open_camera(backend=backend, config=config) as camera:
        logger.debug(f"Setting shutter to {shutter}")
        camera.shutter.value = shutter
        camera.backend.push_config()
        camera.backend.pull_config()
        logger.debug(f"Verify shutter: {camera.shutter.value}")
        for i in range(1, trials + 1):
            start_time = time.perf_counter()
            output_path, actual_capture_time = camera.capture_and_download(output_dir, stem="bench")
            end_time = time.perf_counter()
            total_time = end_time - start_time
            logger.debug(
                f"It took {total_time:.2f}s to capture and download (with shutter {camera.shutter.value})"
            )
            dark_time = total_time - camera.shutter.actual_value
            print(f"Trial #{i} dark time: {dark_time}")
            dark_times.append(dark_time)

    return dark_times


def bench_sustained_capture_rate(
    trials: int, shutter: str, backend: Backend, config: CameraConfig, output_dir: Path
):
    """Capture images as quickly as possible; see how long it takes

    Capture will end after ONE OF:

    1. Camera error
    2. Sustained rate slow down past given delta TODO
    3. Requested number of captures has been satisfied
    """


def bench(
    trials: int,
    shutters: list[str],
    backend: Backend,
    config: CameraConfig,
    output_dir: Path,
):
    dark_times_per_shutter: dict[str, list[float]] = {}
    for shutter in shutters:
        dark_times_per_shutter[shutter] = bench_dark_time_for_shutter_speed(
            trials=trials,
            shutter=shutter,
            backend=backend,
            config=config,
            output_dir=output_dir,
        )

    for shutter, dark_times in dark_times_per_shutter.items():
        print_stats(f"Shutter {shutter} mean dark time across {trials} trials:", dark_times)
    all_dark_times = [
        t for dts_for_shutter in dark_times_per_shutter.values() for t in dts_for_shutter
    ]
    print_stats("Overall dark time across all shutter speeds:", all_dark_times)
