import argparse
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep

import typer

from chrophos.camera.backend import Backend
from chrophos.camera.camera import Camera, ExposureTriangle, open_camera
from chrophos.config import Config
from chrophos.plan import format_timedelta

logger = logging.getLogger(__name__)

app = typer.Typer()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=Path)
    parser.add_argument("-s")
    parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        type=Path,
        default=Path("./raw_timelapse_images"),
    )
    parser.add_argument("-i", "--interval", type=int, required=True)
    parser.add_argument("-n", "--num-images", type=int, required=True)
    parser.add_argument("-v", "--verbosity", type=int, choices=[0, 1, 2], default=1)
    return parser.parse_args()


ZERO_DELTA = timedelta(0)


def sleep_until(dt: datetime, precision=0.01):
    logger.debug(f"Sleeping until {dt}")
    while True:
        now = datetime.now()
        delta = dt - now
        if delta <= ZERO_DELTA:
            logger.debug(
                f"Done sleeping at {now} (missed target {dt} by"
                f" {timedelta(seconds=abs(delta.total_seconds()))})"
            )
            return delta
        else:
            sleep(precision)


def get_nearest_shutter_under(camera: Camera, value):
    valid_values = sorted(
        (vv for vv in camera.shutter.choices),
        key=lambda v: v.actual_value,
    )
    prev = valid_values.pop(0)
    for vv in valid_values:
        if camera.shutter.parse(vv) > value:
            return prev
        prev = vv
    raise ValueError("fuck")


def gen_times(interval: timedelta, num_frames: int | None = None, start: datetime | None = None):
    if start is None:
        start = datetime.now()
    if num_frames is None:
        while True:
            start += interval
            yield start
    else:
        for i in range(num_frames):
            yield start + interval * i


def timelapse(
    backend: Backend,
    config: Config,
    num_frames: int | None,
    interval: timedelta,
    output_dir: Path,
    dark_time=timedelta(seconds=1),
    start_delay=timedelta(seconds=0),
    window_size=5,
    dry_run=False,
    ev_diff_threshold_steps=1.0,
):
    if interval < dark_time:
        raise ValueError(
            f"Requested interval of {interval} is longer than expected dark time of {dark_time}"
        )
    logger.debug(f"{backend=}")
    output_dir.mkdir(exist_ok=True, parents=True)
    start = datetime.now() + start_delay
    times = gen_times(interval, num_frames, start)
    template = "TL{i}"
    previous_exposures: list[ExposureTriangle] = []
    ev_at_last_intervention: float | None = None
    camera: Camera
    with open_camera(backend=backend, config=config) as camera:
        for i, commanded_capture_time in enumerate(times, 1):
            camera.backend.pull_config()
            if camera.backend.auto_exposure_mode.value != "Manual":
                raise AssertionError("Uh oh")
            logger.debug(camera.summary())
            shutter_speed = timedelta(seconds=camera.shutter.actual_value)
            total_shot_time = shutter_speed + dark_time
            buffer = interval - total_shot_time
            current_exposure = camera.determine_good_exposure()
            if ev_at_last_intervention is None:
                ev_at_last_intervention = current_exposure.ev
            previous_exposures = [current_exposure, *previous_exposures[: window_size - 1]]
            logger.info(f"{[e.ev for e in previous_exposures]}")
            mean_ev = sum(e.ev for e in previous_exposures) / len(previous_exposures)
            logger.info(current_exposure.description())
            diff_between_commanded_ev_and_avg_detected_ev = camera.exposure.ev - mean_ev
            logger.info(f"Current Commanded Exposure: {camera.summary()}")
            # logger.info(
            #     f"Current EV {current_exposure.ev:.1f} | Rolling Avg. EV: {mean_ev:.1f} |"
            #     f" {diff_between_commanded_ev_and_avg_detected_ev=:.1f} |
            #     {ev_diff_threshold_steps=:.1f} |"
            #     f" {ev_at_last_intervention=:.1f}"
            # )
            if abs(abs(mean_ev) - abs(camera.exposure.ev)) >= ev_diff_threshold_steps:
                logger.info(
                    f"Stepping exposure by {diff_between_commanded_ev_and_avg_detected_ev} stops;"
                    " stepping exposure"
                )
                camera.step_exposure(diff_between_commanded_ev_and_avg_detected_ev)
                previous_exposures = [camera.exposure] * window_size
                ev_at_last_intervention = camera.exposure.ev
            logger.debug(
                f"Required shot time: {format_timedelta(shutter_speed)} +"
                f" {format_timedelta(dark_time)} = {format_timedelta(total_shot_time)}. This"
                f" is {format_timedelta(buffer)} less than the interval"
            )

            now = datetime.now()
            if commanded_capture_time < now:
                raise ValueError(f"Missed capture window #{i} by {now - commanded_capture_time}")
            sleep_until(commanded_capture_time)
            if not dry_run:
                start_time = time.perf_counter()
                output_path, actual_capture_time = camera.capture_and_download(
                    output_dir, stem=template.format(i=i)
                )
                print(
                    f"Saved #{i} to PC at {output_path}. Delta:"
                    f" {actual_capture_time - commanded_capture_time}"
                )
                end_time = time.perf_counter()
                logger.debug(
                    "Actual dark time:"
                    f" {end_time - start_time - shutter_speed.total_seconds():.2f}s (vs. estimated"
                    f" dark time {dark_time}"
                )
