import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import Union

import typer

from chrophos.camera.backend import Backend
from chrophos.camera.camera import Camera, open_camera
from chrophos.config import CameraConfig
from chrophos.plan import format_timedelta

logger = logging.getLogger(__name__)

app = typer.Typer()


ZERO_DELTA = timedelta(0)


def sleep_until(dt: datetime, precision=0.01):
    logger.debug(f"Sleeping until {dt}")
    while True:
        now = datetime.now()
        delta = dt - now
        if delta <= ZERO_DELTA:
            logger.debug(
                "Done sleeping. Missed target by"
                f" {format_timedelta(timedelta(seconds=abs(delta.total_seconds())))}"
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


def gen_times(
    interval: timedelta,
    num_frames: Union[int, None] = None,
    start: Union[datetime, None] = None,
):
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
    config: CameraConfig,
    num_frames: Union[int, None],
    interval: timedelta,
    output_dir: Path,
    mode: str = "P",
    dark_time: Union[timedelta, None] = None,
    start_delay=timedelta(seconds=1),
    dry_run=False,
):
    if dark_time is None:
        dark_time = config.dark_time

    if dark_time is None:
        raise AssertionError("shit")

    if interval < dark_time:
        raise ValueError(
            f"Requested interval of {interval} is longer than expected dark time of {dark_time}"
        )
    logger.debug(f"{backend=}")
    output_dir.mkdir(exist_ok=True, parents=True)
    start = datetime.now() + start_delay
    times = gen_times(interval, num_frames, start)
    template = "TL{i}"
    camera: Camera
    with open_camera(backend=backend, config=config) as camera:
        camera.backend.set_config_value("autoexposuremode", mode)
        # with camera.backend.half_press_shutter_during():
        #     summary = camera.summary()
        #     sleep(0.5)
        # logger.info(f"Current camera exposure state: {summary}")
        for i, commanded_capture_time in enumerate(times, 1):
            camera.empty_event_queue()
            with camera.backend.half_press_shutter_during():
                shutter_speed = timedelta(seconds=camera.shutter.actual_value)
            total_shot_time = shutter_speed + dark_time
            buffer = total_shot_time - interval
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
                logger.info(
                    f"Saved #{i} to PC at {output_path}. Delta:"
                    f" {actual_capture_time - commanded_capture_time}"
                )
                end_time = time.perf_counter()
                actual_dark_time = timedelta(
                    seconds=end_time - start_time - shutter_speed.total_seconds()
                )
                logger.debug(
                    f"Actual dark time: {actual_dark_time} (vs. estimated dark time {dark_time})"
                )
