import argparse
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep

from chrophos.camera.backend import Backend, Canon5DII
from chrophos.camera.camera import open_camera, parse_shutter
from chrophos.camera.parameter import DiscreteParameter, ValidationError
from chrophos.config import Config, parse_config

logger = logging.getLogger(__name__)


def init_logging(verbosity: int):
    if verbosity == 0:
        log_level = logging.WARNING
    elif verbosity == 1:
        log_level = logging.INFO
    elif verbosity == 2:
        log_level = logging.DEBUG
    else:
        raise ValueError(f"Invalid verbosity level: {verbosity}")

    module_logger = logging.getLogger("chrophos")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = logging.Formatter("[%(asctime)s - %(module)s - %(levelname)s] %(message)s")
    console_handler.setFormatter(formatter)
    module_logger.addHandler(console_handler)
    module_logger.setLevel(log_level)


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


def auto_adjust_exposure(
    camera, interval: timedelta, dark_time: timedelta, auto_exposure_mode: str, delay=0.1
):
    total_shot_time = interval + dark_time
    while total_shot_time > interval:
        sleep(delay)
        try:
            param: DiscreteParameter
            if auto_exposure_mode == "P":
                param = camera.aperture
                step = -1
            elif auto_exposure_mode == "TV":
                param = camera.shutter
                step = 1
            else:
                raise AssertionError(f"Unexpected {auto_exposure_mode=}")
            param.step_value(step)
        except ValidationError as error:
            logger.info(f"Ran out of {param.name} stops: {error}")
            if auto_exposure_mode == "aperture_priority":
                logger.info("Switching to shutter priority")
                req_shutter = camera.shutter.value
                camera.backend.half_release_shutter()
                camera.backend.set_config_value("autoexposuremode", "TV")
                camera.backend.set_config_value("shutterspeed", req_shutter)
                camera.backend.half_press_shutter()
                auto_exposure_mode = "shutter_priority"
            else:
                logger.warning("out of stops in both aperture and shutter")
        else:
            camera.backend.half_release_shutter()
            camera.backend.push_config()
            camera.backend.half_press_shutter()

            camera.backend.pull_config()
            logger.debug(camera.summary())
            shutter_speed = timedelta(seconds=parse_shutter(camera.shutter.value))
            total_shot_time = shutter_speed + dark_time
            logger.debug(f"{total_shot_time=}")
    return auto_exposure_mode


def get_nearest_shutter_under(camera, value):
    valid_values = sorted(
        (vv for vv in camera.shutter.valid_values if vv.lower() != "auto"),
        key=lambda v: parse_shutter(v),
    )
    prev = valid_values.pop(0)
    for vv in valid_values:
        if parse_shutter(vv) > value:
            return prev
        prev = vv
    raise ValueError("fuck")


def timelapse(
    backend: Backend,
    config: Config,
    num_frames: int,
    interval: int,
    output_dir: Path,
    dark_time=timedelta(seconds=5),
):
    logger.debug(f"{backend=}")
    output_dir.mkdir(exist_ok=True, parents=True)
    start = datetime.now() + timedelta(seconds=10)
    times = (start + timedelta(seconds=interval * i) for i in range(num_frames))
    auto_exposure_mode = "P"
    template = "TL{i}"
    with open_camera(backend=backend, config=config) as camera:
        logger.info(f"Setting auto-exposure mode to {auto_exposure_mode}")
        camera.backend.set_config_value("autoexposuremode", auto_exposure_mode)
        camera.backend.half_press_shutter()
        for i, commanded_capture_time in enumerate(times, 1):
            camera.backend.pull_config()
            logger.debug(camera.summary())
            shutter_speed = timedelta(seconds=parse_shutter(camera.shutter.value))
            total_shot_time = shutter_speed + dark_time
            buffer = interval - total_shot_time.total_seconds()
            if buffer < 0:
                if auto_exposure_mode != "Manual":
                    # TODO: Once ISO starts dropping, switch back to P mode
                    logger.info(
                        "Not enough time for capture! Switching to manual mode with"
                        " longest-possible shutter"
                    )
                    auto_exposure_mode = "Manual"
                    camera.backend.half_release_shutter()
                    camera.backend.set_config_value("autoexposuremode", auto_exposure_mode)
                    camera.iso.value = "Auto"
                    longest_valid_shutter = get_nearest_shutter_under(
                        camera, interval - dark_time.total_seconds()
                    )
                    camera.shutter.value = longest_valid_shutter
                    camera.aperture.value = camera.aperture.valid_values[0]
                    camera.backend.push_config()
                    camera.backend.pull_config()
                    logger.info(
                        f"Set auto-exposure mode to {auto_exposure_mode}, shutter to"
                        f" {camera.shutter.value}, aperture to"
                        f" {camera.aperture.value} and ISO to {camera.iso.value}"
                    )
                    sleep(0.1)
                    camera.summary()
                    camera.backend.half_press_shutter()
                    camera.summary()
                    shutter_speed = timedelta(seconds=parse_shutter(camera.shutter.value))
                    total_shot_time = shutter_speed + dark_time
                    buffer = interval - total_shot_time.total_seconds()
                else:
                    raise ValueError("fuck!")

            logger.debug(
                f"Required shot time: {shutter_speed.total_seconds():.2f}s +"
                f" {dark_time.total_seconds():.2f}s = {total_shot_time.total_seconds():.2f}. This"
                f" is {buffer:.2f} less than the interval"
            )

            stem = template.format(i=i)

            now = datetime.now()
            if commanded_capture_time < now:
                raise ValueError(f"Missed capture window #{i} by {now - commanded_capture_time}")
            sleep_until(commanded_capture_time)
            start_time = time.perf_counter()
            output_path, actual_capture_time = camera.capture_and_download(output_dir, stem)
            print(
                f"Saved #{i} to PC at {output_path}. Delta:"
                f" {actual_capture_time - commanded_capture_time}"
            )
            end_time = time.perf_counter()
            logger.debug(f"Dark time: {end_time - start_time - shutter_speed.total_seconds():.2f}s")
        camera.backend.half_release_shutter()


def main():
    args = parse_args()

    init_logging(verbosity=args.verbosity)
    if not args.config:
        raise NotImplementedError("Default config map not implemented yet; must specify --config")

    config = parse_config(args.config)
    timelapse(
        backend=Canon5DII(
            config_map=config.config_map,
            target_aperture=config.target_aperture,
            target_iso=config.target_iso,
            target_shutter=config.target_shutter,
        ),
        config=config,
        num_frames=args.num_images,
        interval=args.interval,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
