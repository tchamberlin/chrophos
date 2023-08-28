import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from time import sleep

import gphoto2 as gp

from .parameter import DiscreteParameter, ReadonlyParameter
from ..config import Complex

logger = logging.getLogger(__name__)


class BackendError(ValueError):
    """Indicates an error in the camera itself"""


class Backend(ABC):
    """An abstraction of a physical camera"""

    aperture: DiscreteParameter
    iso: DiscreteParameter
    shutter: DiscreteParameter
    light_meter: ReadonlyParameter | None

    @abstractmethod
    def __init__(self, config_map: dict[str, str]):
        ...

    @abstractmethod
    def capture_and_download(self, output_dir: Path, stem: str) -> tuple[Path, datetime]:
        ...

    @abstractmethod
    def exit(self):
        ...


# class DummyBackend(Backend):
#     def __init__(self, config_map: dict[str, str]):
#         self.parameters = {}
#         self.shutter = DiscreteParameter(
#             "shutter",
#             config_map.get("shutter", "shutter"),
#             valid_values=["30", "10", "6", "4", "2", "1", "1/4", "1/10", "1/25", "1/100", "1/1000"],
#             initial_value="1/1000",
#         )
#         self.parameters["shutter"] = self.shutter
#
#         self.aperture = DiscreteParameter(
#             "aperture",
#             config_map.get("aperture", "aperture"),
#             valid_values=["2", "2.8", "4", "5.6", "8", "11", "16", "22"],
#             initial_value="8",
#         )
#         self.parameters["aperture"] = self.aperture
#
#         self.iso = DiscreteParameter(
#             "iso",
#             config_map.get("iso", "iso"),
#             valid_values=["100", "200", "400", "1000", "1600", "3200", "6400", "12800"],
#             initial_value="100",
#         )
#         self.parameters["iso"] = self.iso
#
#     def capture_and_download(self, output_dir: Path, stem: str) -> Path:
#         ...
#
#     def exit(self):
#         ...


class Gphoto2Backend(Backend):
    def __init__(
        self,
        config_map: dict[str, str | Complex],
        target_shutter: str,
        target_aperture: str,
        target_iso: str,
        reset_camera_config_on_exit=False,
        half_press_on_init=False,
    ):
        try:
            self._camera = gp.Camera()
        except gp.GPhoto2Error as error:
            raise BackendError(
                "Failed to initialize camera. Are you sure it's plugged in and turned on?"
            ) from error

        self.pre_init_camera()
        camera_config = self._camera.get_config()

        self.initial_camera_config = camera_config
        self.reset_camera_config_on_exit = reset_camera_config_on_exit

        shutter = camera_config.get_child_by_name(config_map["shutter"])
        self.parameters = {}
        self.shutter = DiscreteParameter(
            "shutter",
            config_map["shutter"],
            valid_values=[*shutter.get_choices(), "auto"],
            initial_value=target_shutter,
        )
        self.parameters["shutter"] = self.shutter

        shutter_release = camera_config.get_child_by_name(config_map["shutter_release"].key)
        self.shutter_release = DiscreteParameter(
            "shutter_release",
            config_map["shutter_release"].key,
            valid_values=list(shutter_release.get_choices()),
            initial_value=shutter_release.get_value(),
        )
        self.parameters["shutter_release"] = self.shutter_release

        aperture = camera_config.get_child_by_name(config_map["aperture"])
        self.aperture = DiscreteParameter(
            "aperture",
            config_map["aperture"],
            valid_values=[*aperture.get_choices(), "implicit auto"],
            initial_value=target_aperture,
        )
        self.parameters["aperture"] = self.aperture

        iso = camera_config.get_child_by_name("iso")
        self.iso = DiscreteParameter(
            "iso",
            config_map["iso"],
            valid_values=[*iso.get_choices(), "Auto"],
            initial_value=target_iso,
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

    def get_config_value(self, key):
        config = self._camera.get_config()
        return config.get_child_by_name(key).get_value()

    def set_config_value(self, key, value):
        config = self._camera.get_config()
        config.get_child_by_name(key).set_value(value)
        self._camera.set_config(config)

    def pull_config(self):
        camera_config = self._camera.get_config()
        for p in self.parameters.values():
            p.value = camera_config.get_child_by_name(p.field).get_value()
        logger.debug("Pulled config from camera")

    def push_config(self, bulk=True, params=None):
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
            self._camera.set_config(camera_config)
        logger.debug("Pushed config to camera")

    def capture_and_download(self, output_dir: Path, stem: str):
        output_dir.mkdir(parents=True, exist_ok=True)
        _path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
        path_on_camera = Path(_path.folder + _path.name)
        logger.info(f"Captured to camera path {path_on_camera}")
        camera_file = self._camera.file_get(_path.folder, _path.name, gp.GP_FILE_TYPE_NORMAL)
        capture_dt = datetime.fromtimestamp(camera_file.get_mtime())

        output_path = output_dir / f"{stem}{path_on_camera.suffix}"
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
        logger.debug("PRESS")
        try:
            logger.debug("YIELD")
            yield
        finally:
            self.half_release_shutter(camera_config)

    def half_press_shutter(self, camera_config=None, delay=0.2):
        if camera_config is None:
            camera_config = self._camera.get_config()
        shutter_release = camera_config.get_child_by_name("eosremoterelease")
        logger.debug("Half-pressing shutter")
        shutter_release.set_value("Press Half")
        self._camera.set_config(camera_config)
        sleep(delay)

    def half_release_shutter(self, camera_config=None, delay=0.2):
        if camera_config is None:
            camera_config = self._camera.get_config()
            logger.debug("Half-releasing shutter")
        shutter_release = camera_config.get_child_by_name("eosremoterelease")
        shutter_release.set_value("Release Half")
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

    def post_init_camera(self):
        logger.info(
            "Setting camera to 'P' mode (so that the camera can control its own exposure settings)"
        )
        self.set_config_value("autoexposuremode", "P")

    def push_config(self, bulk=False):
        if self.get_config_value("autoexposuremode") == "AV":
            super().push_config(params=[self.aperture], bulk=bulk)
        elif self.get_config_value("autoexposuremode") == "TV":
            super().push_config(params=[self.shutter], bulk=bulk)
        else:
            super().push_config(bulk=bulk)
