import logging
from contextlib import contextmanager
from pathlib import Path
from time import sleep

from chrophos.camera.backend import Backend
from chrophos.camera.parameter import ValidationError
from chrophos.config import Config
from chrophos.exposure import exposure_value

logger = logging.getLogger(__name__)


class CameraError(ValueError):
    ...


def check_is_number_or_fraction(fraction: str):
    try:
        int(fraction)
    except Exception:
        try:
            numerator, denominator = fraction.split("/")
            _ = int(numerator), int(denominator)
        except Exception:
            return False

    return True


def parse_shutter(shutter: str):
    if shutter == "auto":
        return None
    try:
        return float(shutter)
    except ValueError:
        pass

    try:
        numerator, denominator = shutter.split("/")
        return float(numerator) / float(denominator)
    except (ValueError, IndexError) as error:
        raise ValidationError(f"Invalid shutter value {shutter!r}") from error


def parse_aperture(aperture: str):
    try:
        return float(aperture)
    except ValueError:
        pass

    try:
        return float(aperture.split("/")[1])
    except IndexError as error:
        raise CameraError(f"Invalid aperture: {aperture!r}") from error


class Camera:
    def __init__(
        self,
        backend: Backend,
        config: Config,
    ):
        self.backend = backend
        # TODO: This is only needed for nikon
        # self.config.set_value("imagequality", "NEF (Raw)")

        # Shortcuts
        self.light_meter = getattr(self.backend, "light_meter", None)
        self.iso = self.backend.iso
        self.aperture = self.backend.aperture
        self.shutter = self.backend.shutter

    def exposure_value(self):
        iso = int(self.iso.value)
        aperture = parse_aperture(self.aperture.value)
        shutter = parse_shutter(self.shutter.value)
        return exposure_value(aperture=aperture, iso=iso, shutter=shutter)

    def step_exposure(self, step: int):
        # self.backend.pull_config()
        parameter_order = [self.shutter, self.aperture, self.iso]
        for parameter in parameter_order:
            try:
                parameter.step_value(step)
            except IndexError:
                print(f"Can't step value for {parameter}; moving on to next parameter")
            else:
                # self.backend.push_config()
                return True
        return False

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
        return self.backend.summary()
        # return (
        #     f"Shutter: {self.shutter.value}; Aperture: {self.aperture.value}; ISO:"
        #     f" {self.iso.value}; EV: {self.exposure_value():.1f}"
        # )


@contextmanager
def open_camera(backend: Backend, config: Config):
    try:
        camera = Camera(backend, config)
        yield camera
    except Exception:
        raise
    else:
        camera.backend.exit()
