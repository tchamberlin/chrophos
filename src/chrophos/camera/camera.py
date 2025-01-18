import logging
import math
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from chrophos.camera.backend import Backend
from chrophos.camera.parameter import (
    Aperture,
    EvStep,
    Iso,
    Shutter,
)
from chrophos.config import CameraConfig

logger = logging.getLogger(__name__)


class CameraError(ValueError):
    ...


def exposure_value(aperture: float, iso: int, shutter: float):
    return


@dataclass
class ExposureTriangle:
    shutter: float
    aperture: float
    iso: int

    @property
    def exposure_value(self):
        return math.log2((100 * self.aperture**2) / (self.iso * self.shutter))

    ev = exposure_value

    def description(self):
        return (
            f"Shutter {self.shutter}, Aperture {self.aperture}, ISO {self.iso}, EV"
            f" {self.exposure_value:.1f}"
        )


class Camera:
    shutter: Shutter
    aperture: Aperture
    iso: Iso
    ev_step_size: EvStep

    def __init__(
        self,
        config: Union[CameraConfig, Path],
        backend: Backend,
    ):
        if not isinstance(config, CameraConfig):
            if not isinstance(config, Path):
                logger.debug(
                    f"Treating non-Path {config} of type {type(config)} as a path!"
                )
            config = CameraConfig.read(config)
        self.backend = backend
        self.config = config

        self.parameters = {}
        breakpoint()
        # TODO: This doesn't belong here
        for config_param in config.parameters.values():
            # camera_config_item = self.config.parameters[config_param.name]
            # backend_config_item = backend.get_config_item(config_param.config_key)
            parameter = backend.gen_parameter(config_param=config_param)
            if config_param.initial_value:
                logger.debug(
                    f"Setting initial value for {config_param.name} ({config_param.config_key}) to {config_param.initial_value}"
                )
                self.backend.set_config_value(
                    config_param.config_key, config_param.initial_value
                )
            setattr(self, parameter.name, parameter)
            # logger.debug(f"Init self.{key}")
            self.parameters[parameter.name] = parameter

    # TODO: This really needs to be a feedback loop where it checks the results along the way (?)
    def step_exposure(self, num_stops: float):
        step_size = self.ev_step_size.actual_value
        if num_stops == 0:
            raise CameraError("Can't step by 0, dumbass")
        total_steps = abs(int(num_stops // step_size))
        logger.info(
            f"Stepping exposure by {num_stops:.1f} stops (in {total_steps} steps of {self.ev_step_size.value} stops)"
        )
        parameter_order = [self.shutter, self.aperture, self.iso]
        steps_remaining = total_steps
        if num_stops < 0:
            parameter_order = reversed(parameter_order)
        flip = 1 if num_stops > 0 else -1
        direction_verb = "increase" if num_stops > 0 else "decrease"
        for parameter in parameter_order:
            direction_to_step_towards = parameter.direction * flip
            # We are increasing, so our maximum number of steps is determined by the delta between
            # the current parameter index and its maximum (length)
            if direction_to_step_towards > 0:
                num_steps_we_can_change_this_param_by = (
                    len(parameter.choices)
                    - parameter.choices.index(parameter.value)
                    - 1
                )
            # We are decreasing, so our maximum number of steps is just the current index
            else:
                num_steps_we_can_change_this_param_by = parameter.choices.index(
                    parameter.value
                )
            if num_steps_we_can_change_this_param_by == 0:
                logger.info(f"We cannot {direction_verb} {parameter.name} any more!")
                continue

            # If we cannot completely satisfy the step request within this parameter, do what we can here, then
            # continue on
            if num_steps_we_can_change_this_param_by <= steps_remaining:
                parameter.step_value(flip * num_steps_we_can_change_this_param_by)
                steps_remaining -= num_steps_we_can_change_this_param_by
                logger.info(
                    f"Parameter {parameter.name} {direction_verb} by {num_steps_we_can_change_this_param_by}; now {parameter.value}. "
                    f"Remaining: {steps_remaining}/{total_steps}. Light meter now: {self.light_meter.value}"
                )
            # Otherwise complete the request and return
            else:
                parameter.step_value(flip * steps_remaining)
                steps_remaining -= steps_remaining
                logger.info(
                    f"Parameter {parameter.name} {direction_verb} by {num_steps_we_can_change_this_param_by}; now {parameter.value}. "
                    f"Remaining: {steps_remaining}/{total_steps}. Light meter now: {self.light_meter.value} DONE"
                )
                return True
        raise CameraError(f"Failed to step by requested {total_steps}! ")

    def auto_expose_via_light_meter(self):
        # TODO: Put this in a config file!
        METER_DELTA_PER_STOP = 6
        stops = -(self.light_meter.value / METER_DELTA_PER_STOP)
        logger.info(
            f"Current light meter is {self.light_meter.value}. Requesting step of {stops} stops"
        )
        self.step_exposure(stops)

    def capture(
        self, output_dir: Union[Path, None] = None, stem: Union[str, None] = None
    ):
        """Capture an image and save to to `output_dir` using `stem` as the basis for its name"""

        return self.backend.capture_and_download(output_dir=output_dir, stem=stem)

    def set_config_value(self, key: str, value, **kwargs):
        return self.backend.set_config_value(key=key, value=value, **kwargs)


# TODO: Should this exist?
@contextmanager
def open_camera(backend: Backend, config: CameraConfig):
    try:
        camera = Camera(backend=backend, config=config)
        yield camera
    except Exception:
        raise
    else:
        camera.backend.exit()
