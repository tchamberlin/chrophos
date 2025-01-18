import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any, Union

import gphoto2 as gp

from chrophos.config import ConfigParameter, parse_config_raw

from ..utilities.benchmark import Benchmark
from .parameter import (
    Aperture,
    DiscreteParameter,
    EvStep,
    Iso,
    Parameter,
    RangeParameter,
    Shutter,
)

logger = logging.getLogger("chrophos")


class BackendError(ValueError):
    """Indicates an error in the camera itself."""


class Backend(ABC):
    """An abstraction of a physical camera."""

    @abstractmethod
    def capture_and_download(
        self, output_dir: Union[Path, None] = None, stem: Union[str, None] = None
    ) -> tuple[Path, datetime]:
        ...

    @abstractmethod
    def exit(self):
        ...

    @abstractmethod
    def push_config(self, params: Union[list[Parameter], None] = None, **kwargs):
        ...

    @abstractmethod
    def pull_config(self, params: Union[list[Parameter], None] = None, **kwargs):
        ...

    @abstractmethod
    def get_config_value(self, key: str, **kwargs) -> Any:
        ...

    @abstractmethod
    def set_config_value(self, key: str, value, **kwargs):
        ...


class Gphoto2Backend(Backend):
    def __init__(
        self,
        reset_camera_config_on_exit=False,
    ):
        try:
            self._camera = gp.Camera()
        except gp.GPhoto2Error as error:
            raise BackendError(
                "Failed to initialize camera. Are you sure it's plugged in and turned on?"
            ) from error

    @property
    def config(self):
        return {p.name: p.value for p in self.parameters.values()}

    def get_config(self):
        return self._camera.get_config()

    def pre_init_camera(self):
        pass

    def post_init_camera(self):
        pass

    def gen_parameter(self, config_param: ConfigParameter):
        """Given a ConfigParameter, generate a Parameter (which knows how to talk to this backend)"""
        backend_config_item = self.get_config_item(config_param.config_key)
        current_value = backend_config_item.get_value()
        if config_param.type == "discrete":
            possible_choices = list(backend_config_item.get_choices())
            if config_param.name == "shutter":
                parameter_class = Shutter
            elif config_param.name == "aperture":
                parameter_class = Aperture
            elif config_param.name == "iso":
                parameter_class = Iso
            elif config_param.name == "ev_step_size":
                parameter_class = EvStep
            else:
                parameter_class = DiscreteParameter

            parameter = parameter_class(
                name=config_param.name,
                field=config_param.config_key,
                initial_value=config_param.initial_value or current_value,
                valid_min=config_param.valid_min,
                valid_max=config_param.valid_max,
                choices=possible_choices,
                setter=self.push_config,
            )
        elif config_param.type == "boolean":
            possible_choices = list(backend_config_item.get_choices())
            parameter = DiscreteParameter(
                name=config_param.name,
                field=config_param.config_key,
                initial_value=config_param.initial_value or current_value,
                choices=possible_choices,
                setter=self.push_config,
            )
        elif config_param.type == "range":
            lower, upper, step = backend_config_item.get_range()  # ?
            parameter = RangeParameter(
                name=config_param.name,
                field=config_param.config_key,
                initial_value=config_param.initial_value or current_value,
                valid_range=(lower, upper),
                setter=self.push_config,
            )
        else:
            raise ValueError(f"Invalid type: {config_param.type}")

        return parameter

    def get_config_value(self, key, attempts=2):
        item = self.get_config_item(key, attempts=attempts)
        if not item:
            raise ValueError("hmmm")
        return item.get_value()

    def get_config_item(self, key, attempts=2):
        for i in range(1, attempts + 1):
            logger.debug(f"Attempt #{i} to get {key}")
            try:
                config = self._camera.get_config()
                return config.get_child_by_name(key)
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
            logger.debug(f"Set {p.name} to {p.value}")
        logger.debug("Pulled config from camera")

    def push_config(
        self,
        params: Union[list[Parameter], None] = None,
        attempts=2,
        bulk=False,
    ):
        if params is None:
            params = self.parameters.values()
        else:
            logger.debug(f"Pushing only {[p.name for p in params]}")
        for p in params:
            logger.debug(f"Attempting to set {p.field} to {p.value}")
            if bulk:
                camera_config = self._camera.get_config()
                camera_config.get_child_by_name(p.field).set_value(p.value)
            else:
                self.set_config_value(p.field, p.value)
                logger.debug(f"Successfully set {p.field} to {p.value}")
        if bulk:
            for i in range(attempts + 1, 1):
                try:
                    camera_config = self._camera.get_config()
                    self._camera.set_config(camera_config)
                except gp.GPhoto2Error as error:
                    if i == attempts:
                        raise
                    else:
                        logger.debug(f"{error}; trying again")
        logger.debug("Pushed config to camera")

    def capture_and_download(
        self,
        output_dir: Union[Path, None] = None,
        stem: Union[str, None] = None,
        timeout=3_000,
        method="wait_for_event",
    ):
        logger.debug("Start capture")
        with Benchmark("Captured image", logger=logger.debug):
            # This method seems slightly faster than the capture() method
            if method == "direct_capture":
                event_data = self._camera.capture(gp.GP_CAPTURE_IMAGE)
            if method == "wait_for_event":
                self._camera.trigger_capture()
                while True:
                    event_type, event_data = self._camera.wait_for_event(timeout)
                    if event_type == gp.GP_EVENT_FILE_ADDED:
                        break
            else:
                raise ValueError(f"Unsupported capture method {method}")
        path_on_camera = Path(event_data.folder + event_data.name)
        logger.info(f"Captured to camera path {path_on_camera}")
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            with Benchmark("Downloaded image from camera", logger=logger.debug):
                camera_file = self._camera.file_get(
                    event_data.folder, event_data.name, gp.GP_FILE_TYPE_NORMAL
                )
            capture_dt = datetime.fromtimestamp(camera_file.get_mtime())
            if stem:
                stem = stem.format(capture_dt=capture_dt.isoformat())
            else:
                stem = path_on_camera.name
            output_path = output_dir / f"{stem}{path_on_camera.suffix}"
            with Benchmark(f"Saved image from camera to {output_path}", logger=logger.debug):
                camera_file.save(str(output_path))
            logger.info(f"Capture to {output_path} completed at {capture_dt}")
        else:
            logger.info("Capture completed")
            output_path = None
            capture_dt = None
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
    def __init__(self, config_path: Path):
        self.config = parse_config_raw(config_path)

    # def gen_parameter()

    def capture_and_download(
        self, output_dir: Union[Path, None] = None, stem: Union[str, None] = None
    ) -> tuple[Path, datetime]:
        return (Path("dummy"), datetime.now())

    def exit(self):
        ...

    def pull_config(self, params: Union[list[Parameter], None] = None, **kwargs):
        ...

    def push_config(self, params: Union[list[Parameter], None] = None, **kwargs):
        ...

    def get_config_item(self, key: str, **kwargs):
        return self.config["config"][key]["value"]

    def get_config_value(self, key: str, **kwargs):
        return self.get_config_item(key)["value"]

    def set_config_value(self, key: str, value, **kwargs):
        self.config["config"][key] = value
        logger.info(f"Set {key} to {value}")
