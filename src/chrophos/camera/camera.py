import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import sleep

from chrophos.camera.backend import Backend
from chrophos.camera.parameter import ValidationError
from chrophos.config import Config
from chrophos.exposure import exposure_value

logger = logging.getLogger(__name__)


class CameraError(ValueError):
    ...


@dataclass
class ExposureTriangle:
    shutter: float
    aperture: float
    iso: int

    @property
    def exposure_value(self):
        return exposure_value(shutter=self.shutter, aperture=self.aperture, iso=self.iso)

    ev = exposure_value

    def description(self):
        return (
            f"Shutter {self.shutter}, Aperture {self.aperture}, ISO {self.iso}, EV"
            f" {self.exposure_value:.1f}"
        )


class Camera:
    @dataclass
    class MODE:
        PROGRAM = "program"
        APERTURE_PRIORITY = "APERTURE_PRIORITY"
        SHUTTER_PRIORITY = "SHUTTER_PRIORITY"
        MANUAL = "MANUAL"

    def __init__(
        self,
        backend: Backend,
        config: Config,
    ):
        self.backend = backend
        self.config = config
        # TODO: This is only needed for nikon
        # self.config.set_value("imagequality", "NEF (Raw)")

        # Shortcuts
        self.light_meter = getattr(self.backend, "light_meter", None)
        self.iso = self.backend.iso
        self.aperture = self.backend.aperture
        self.shutter = self.backend.shutter

    @property
    def exposure(self):
        iso = self.iso.actual_value
        aperture = self.aperture.actual_value
        shutter = self.shutter.actual_value
        return ExposureTriangle(aperture=aperture, iso=iso, shutter=shutter)

    # TODO: Step size is configurable in camera; need to make sure these are synced up
    # TODO: This really needs to be a feedback loop where it checks the results along the way
    def step_exposure(self, stop: int, step_size=1 / 3):
        if step_size < 0:
            raise ValueError("Doesn't work like that; must always be positive step size")
        if stop == 0:
            raise ValueError("Can't step by 0, dumbass")
        total_steps = int(stop // step_size)
        logger.warning(
            f"Stepping exposure by {stop:.1f} stops (in {total_steps} steps of {step_size})"
        )
        parameter_order = [self.shutter, self.aperture, self.iso]
        steps_remaining = total_steps
        if stop < 0:
            parameter_order = reversed(parameter_order)
        for parameter in parameter_order:
            for i in range(steps_remaining):
                logger.info(f"Step {i}, param {parameter.name}")
                previous_value = parameter.actual_value
                try:
                    parameter.step_value(-1 if stop < 0 else 1)
                except ValidationError:
                    logger.info(f"Can't step value for {parameter}; moving on to next parameter")
                    break
                else:
                    steps_remaining -= 1
                    self.backend.push_config([parameter])
                    logger.warning(
                        f"Stepped {parameter.name} from {previous_value} to"
                        f" {parameter.actual_value}. EV: {self.exposure.ev:.1f}; {steps_remaining=}"
                    )
                    if steps_remaining == 0:
                        return True
        raise ValueError("Failed to step exposure!")

    def determine_good_exposure(self, mode=MODE.PROGRAM):
        inv = {v: k for k, v in self.config.config_map["auto_exposure_mode"].values.items()}
        original_mode = inv[self.backend.auto_exposure_mode.value]
        self.switch_mode(mode)
        with self.backend.half_press_shutter_during():
            exposure_triangle = ExposureTriangle(
                iso=self.iso.parse(self.backend.get_config_value(self.iso.field)),
                aperture=self.aperture.parse(self.backend.get_config_value(self.aperture.field)),
                shutter=self.shutter.parse(self.backend.get_config_value(self.shutter.field)),
            )

        self.switch_mode(original_mode)
        logger.debug(exposure_triangle.description())
        return exposure_triangle

    # def auto_expose(self):
    #     original_values = self.get_exposure_triangle()
    #     new_values = self.get_exposure_triangle()
    #

    def set_program_mode(self):
        self.switch_mode(self.MODE.PROGRAM)

    def set_aperture_priority_mode(self):
        return self.switch_mode(self.MODE.APERTURE_PRIORITY)

    def set_shutter_priority_mode(self):
        return self.switch_mode(self.MODE.SHUTTER_PRIORITY)

    def set_manual_mode(self):
        return self.switch_mode(self.MODE.MANUAL)

    def switch_mode(self, mode: MODE):
        logger.debug(f"Command: switch mode to {mode}")
        aem = self.config.config_map["auto_exposure_mode"]
        if isinstance(aem, str):
            raise ValueError("config issue")
        self.backend.auto_exposure_mode.value = aem.values[mode]
        self.backend.push_config(params=[self.backend.auto_exposure_mode], bulk=False)

    def auto_expose_via_light_meter(self, target_bounds=(-5, 5), delay=0.05):
        if not self.light_meter:
            raise ValueError(f"Unsupported auto-exposure method; {self} has no light meter!")
        logger.debug(f"auto exposing! initial {self.light_meter.value=}")
        lower_exposure_bound, upper_exposure_bound = target_bounds
        if self.light_meter.value < lower_exposure_bound:
            step = 1
        elif self.light_meter.value > upper_exposure_bound:
            step = -1
        else:
            logger.debug("DOING NOTHING; ALREADY EXPOSED PROPERLY")
            return self.light_meter.value
        while True:
            logger.debug(
                f"CONT: {lower_exposure_bound} > {self.light_meter=} > {upper_exposure_bound}"
            )
            if lower_exposure_bound <= self.light_meter.value <= upper_exposure_bound:
                logger.debug(
                    f"DONE: {lower_exposure_bound} <= {self.light_meter=} <= {upper_exposure_bound}"
                )
                break
            logger.debug(
                f"Shutter speed: {self.shutter.value} | Aperture:"
                f" {self.aperture.value} | ISO: {self.iso.value} |"
                f" Exposure: {self.light_meter.value}"
            )
            try:
                self.step_exposure(step=step)
            except ValueError as error:
                raise ValueError("Can't adjust exposure anymore!") from error

            sleep(delay)
        return self.light_meter.value

    def capture_and_download(self, output_dir: Path, stem: str):
        return self.backend.capture_and_download(output_dir, stem)

    def summary(self):
        return self.exposure.description()


@contextmanager
def open_camera(backend: Backend, config: Config):
    try:
        camera = Camera(backend, config)
        yield camera
    except Exception:
        raise
    else:
        camera.backend.exit()
