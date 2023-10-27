import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Union

import gphoto2 as gp

from ..config import Complex
from ..utilities.benchmark import Benchmark
from .parameter import DiscreteParameter, Parameter, ReadonlyParameter, ValidationError

logger = logging.getLogger(__name__)


class Aperture(DiscreteParameter):
    def parse(self, aperture: str):
        try:
            return float(aperture)
        except ValueError:
            pass

        try:
            return float(aperture.split("/")[1])
        except IndexError as error:
            raise ValidationError(f"Invalid aperture: {aperture!r}") from error


class Shutter(DiscreteParameter):
    def parse(self, shutter: str):
        try:
            return float(shutter)
        except ValueError:
            pass

        try:
            numerator, denominator = shutter.split("/")
            return float(numerator) / float(denominator)
        except (ValueError, IndexError) as error:
            raise ValidationError(f"Invalid shutter value {shutter!r}") from error


class ISO(DiscreteParameter):
    def parse(self, value: str):
        try:
            return int(value)
        except ValueError as error:
            raise ValidationError(f"Invalid iso value {value!r}") from error


class BackendError(ValueError):
    """Indicates an error in the camera itself."""


class Backend(ABC):
    """An abstraction of a physical camera."""

    aperture: Aperture
    iso: ISO
    shutter: Shutter
    light_meter: Union[ReadonlyParameter, None]

    @abstractmethod
    def __init__(self, config_map: dict[str, str]):
        ...

    @abstractmethod
    def capture_and_download(self, output_dir: Path, stem: str) -> tuple[Path, datetime]:
        ...

    @abstractmethod
    def exit(self):
        ...

    @abstractmethod
    def empty_event_queue(camera):
        ...


class Gphoto2Backend(Backend):
    def __init__(
        self,
        config_map: dict[str, Union[str, Complex]],
        target_shutter: float,
        target_aperture: float,
        target_iso: int,
        reset_camera_config_on_exit=False,
        half_press_on_init=False,
    ):
        try:
            self._camera = gp.Camera()
        except gp.GPhoto2Error as error:
            raise BackendError(
                "Failed to initialize camera. Are you sure it's plugged in and turned on?"
            ) from error

        self.target_shutter = target_shutter

        self.target_aperture = target_aperture
        self.target_iso = target_iso
        self.pre_init_camera()
        camera_config = self._camera.get_config()

        self.initial_camera_config = camera_config
        self.reset_camera_config_on_exit = reset_camera_config_on_exit

        shutter = camera_config.get_child_by_name(config_map["shutter"])
        self.parameters = {}
        self.shutter = Shutter(
            "shutter",
            config_map["shutter"],
            choices=list(shutter.get_choices()),
            initial_value=shutter.get_value(),
        )
        self.parameters["shutter"] = self.shutter

        aperture = camera_config.get_child_by_name(config_map["aperture"])
        self.aperture = Aperture(
            "aperture",
            config_map["aperture"],
            choices=list(aperture.get_choices()),
            initial_value=aperture.get_value(),
        )
        self.parameters["aperture"] = self.aperture

        iso = camera_config.get_child_by_name("iso")
        self.iso = ISO(
            "iso",
            config_map["iso"],
            # TODO: Don't reverse this; need to properly sort!
            choices=list(iso.get_choices()),
            initial_value=iso.get_value(),
        )
        self.parameters["iso"] = self.iso
        if "light_meter" in config_map:
            light_meter = camera_config.get_child_by_name("lightmeter")
            self.light_meter = ReadonlyParameter(
                "light_meter", "lightmeter", initial_value=light_meter.get_value()
            )
            self.parameters["light_meter"] = self.light_meter
        else:
            self.light_meter = None

        shutter_release = camera_config.get_child_by_name(config_map["shutter_release"].key)
        self.shutter_release = DiscreteParameter(
            "shutter_release",
            config_map["shutter_release"].key,
            choices=list(shutter_release.get_choices()),
            initial_value=shutter_release.get_value(),
        )
        self.parameters["shutter_release"] = self.shutter_release

        auto_exposure_mode = camera_config.get_child_by_name(config_map["auto_exposure_mode"].key)
        self.auto_exposure_mode = DiscreteParameter(
            "auto_exposure_mode",
            config_map["auto_exposure_mode"].key,
            choices=list(auto_exposure_mode.get_choices()),
            initial_value=auto_exposure_mode.get_value(),
        )
        self.parameters["auto_exposure_mode"] = self.auto_exposure_mode
        # Push config to camera
        self.push_config()
        # Perform any post-init tasks that need to be performed
        self.post_init_camera()
        # Pull the config from the camera, in case things changed as a result of post_init_camera
        self.pull_config()

    @property
    def config(self):
        return {p.name: p.value for p in self.parameters.values()}

    def get_config(self):
        return self._camera.get_config()

    def pre_init_camera(self):
        pass

    def post_init_camera(self):
        pass

    def get_config_value(self, key, attempts=2):
        for i in range(1, attempts + 1):
            logger.debug(f"Attempt #{i} to get {key}")
            try:
                config = self._camera.get_config()
                return config.get_child_by_name(key).get_value()
            except gp.GPhoto2Error as error:
                if i == attempts:
                    raise
                else:
                    logger.debug(f"{error}; trying again")

    def set_config_value(self, key, value, attempts=2):
        for i in range(1, attempts + 1):
            logger.debug(f"Attempt #{i} to set {key} to {value}")
            try:
                config = self._camera.get_config()
                config.get_child_by_name(key).set_value(value)
                return self._camera.set_config(config)
            except gp.GPhoto2Error as error:
                if i == attempts:
                    raise
                else:
                    logger.debug(f"{error}; trying again")

    def pull_config(self):
        camera_config = self._camera.get_config()
        for p in self.parameters.values():
            p.value = camera_config.get_child_by_name(p.field).get_value()
        logger.debug("Pulled config from camera")

    def push_config(self, bulk=False, params: Union[list[Parameter], None] = None, attempts=2):
        camera_config = self._camera.get_config()
        if params is None:
            params = self.parameters.values()
        else:
            logger.debug(f"Pushing only {[p.name for p in params]}")
        for p in params:
            logger.debug(f"Attempting to set {p.field} to {p.value}")
            if bulk:
                camera_config.get_child_by_name(p.field).set_value(p.value)
            else:
                self.set_config_value(p.field, p.value)
                logger.debug(f"Successfully set {p.field} to {p.value}")
        if bulk:
            for i in range(attempts + 1, 1):
                try:
                    self._camera.set_config(camera_config)
                except gp.GPhoto2Error as error:
                    if i == attempts:
                        raise
                    else:
                        logger.debug(f"{error}; trying again")
        logger.debug("Pushed config to camera")

    def capture_and_download(self, output_dir: Path, stem: str):
        logger.debug(f"Attempting to capture to {output_dir!s} with stem {stem!r}")
        output_dir.mkdir(parents=True, exist_ok=True)
        with Benchmark("Captured image", logger=logger.debug):
            _path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
        path_on_camera = Path(_path.folder + _path.name)
        logger.info(f"Captured to camera path {path_on_camera}")
        camera_file = self._camera.file_get(_path.folder, _path.name, gp.GP_FILE_TYPE_NORMAL)
        capture_dt = datetime.fromtimestamp(camera_file.get_mtime())

        output_path = output_dir / f"{stem}{path_on_camera.suffix}"
        with Benchmark(f"Downloaded image from camera to {output_path}", logger=logger.debug):
            camera_file.save(str(output_path))
        logger.info(f"Capture to {output_path} completed at {capture_dt}")
        return output_path, capture_dt

    def exit(self):
        if self.reset_camera_config_on_exit:
            logger.info("Resetting camera config to original state")
            self._camera.set_config(self.initial_camera_config)
        self._camera.exit()

    def summary(self):
        self.pull_config()
        return (
            f"Shutter: {self.shutter.value}; Aperture: {self.aperture.value}; ISO: {self.iso.value}"
        )

    def empty_event_queue(self, timeout=10):
        while True:
            type_, data = self.wait_for_event(timeout)
            if type_ == gp.GP_EVENT_TIMEOUT:
                return
            if type_ == gp.GP_EVENT_FILE_ADDED:
                # get a second image if camera is set to raw + jpeg
                logger.info("Unexpected new file", data.folder + data.name)


class Canon5DII(Gphoto2Backend):
    @contextmanager
    def half_release_shutter_during(self):
        camera_config = self._camera.get_config()
        self.half_release_shutter(camera_config)
        try:
            yield
        finally:
            self.half_press_shutter(camera_config)

    @contextmanager
    def half_press_shutter_during(self):
        camera_config = self._camera.get_config()
        self.half_press_shutter(camera_config)
        try:
            yield
        finally:
            self.half_release_shutter(camera_config)

    def half_press_shutter(self, camera_config=None, delay=0.2):
        if camera_config is None:
            camera_config = self._camera.get_config()
        shutter_release = camera_config.get_child_by_name("eosremoterelease")
        shutter_release.set_value("Press Half")
        self._camera.set_config(camera_config)
        logger.debug("Half-pressed shutter")
        sleep(delay)

    def half_release_shutter(self, camera_config=None, delay=0.2):
        if camera_config is None:
            camera_config = self._camera.get_config()
        shutter_release = camera_config.get_child_by_name("eosremoterelease")
        shutter_release.set_value("Release Half")
        logger.debug("Half-released shutter")
        self._camera.set_config(camera_config)
        sleep(delay)

    def half_toggle_shutter(self):
        camera_config = self._camera.get_config()
        self.half_press_shutter(camera_config)
        self.half_release_shutter(camera_config)

    def pre_init_camera(self):
        logger.info(
            "Setting camera to 'Manual' mode (so that available exposure settings can be read)"
        )
        self.set_config_value("autoexposuremode", "Manual")
        self.set_config_value("meteringmode", "Evaluative")


class DummyBackend(Backend):
    def __init__(
        self,
        config_map: dict[str, Union[str, Complex]],
        target_shutter: float,
        target_aperture: float,
        target_iso: int,
    ):
        self.target_shutter = target_shutter

        self.target_aperture = target_aperture
        self.target_iso = target_iso
        self.pre_init_camera()

        self.parameters = {}
        self.shutter = Shutter(
            "shutter",
            config_map["shutter"],
            choices=["1/8000", "1/100", "1"],
            initial_value="1/100",
        )
        self.parameters["shutter"] = self.shutter

        self.aperture = Aperture(
            "aperture",
            config_map["aperture"],
            choices=["2", "2.8", "4", "11"],
            initial_value="2",
        )
        self.parameters["aperture"] = self.aperture

        self.iso = ISO(
            "iso",
            config_map["iso"],
            choices=["100", "1000", "12800"],
            initial_value="100",
        )
        self.parameters["iso"] = self.iso

        self.auto_exposure_mode = DiscreteParameter(
            "auto_exposure_mode",
            config_map["auto_exposure_mode"].key,
            choices=["M", "P", "A", "S"],
            initial_value="M",
        )
        self.parameters["auto_exposure_mode"] = self.auto_exposure_mode
        # Push config to camera
        self.push_config()
        # Perform any post-init tasks that need to be performed
        self.post_init_camera()
        # Pull the config from the camera, in case things changed as a result of post_init_camera
        self.pull_config()

    def capture_and_download(self, output_dir: Path, stem: str) -> tuple[Path, datetime]:
        ...

    def exit(self):
        ...

    def empty_event_queue(camera):
        ...
