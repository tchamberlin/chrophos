from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import os
from time import sleep

import gphoto2 as gp

from chrophos.parameter import DiscreteParameter, ReadonlyParameter


def check_is_number_or_fraction(fraction: str):
    try:
        int(fraction)
    except Exception:
        try:
            numerator, denominator = fraction.split("/")
            int(numerator), int(denominator)
        except Exception:
            return False

    return True


def parse_aperture(aperture: str):
    try:
        return float(aperture)
    except ValueError:
        pass

    try:
        return float(aperture.split("/")[1])
    except IndexError:
        raise IndexError(f"Invalid aperture: {aperture!r}")


class CameraManager:
    def __init__(
        self,
        camera: gp.Camera,
        config_map: dict[str, str],
        shutter_range=None,
        aperture_range=None,
        iso_range=None,
    ):
        self._camera = camera
        camera_config = self._camera.get_config()

        shutter = camera_config.get_child_by_name(config_map["shutter"])
        self.parameters = {}
        self.shutter = DiscreteParameter(
            "shutter",
            config_map["shutter"],
            valid_values=[
                c for c in shutter.get_choices() if check_is_number_or_fraction(c)
            ],
            initial_value=shutter.get_value(),
        )
        self.parameters["shutter"] = self.shutter

        aperture = camera_config.get_child_by_name(config_map["aperture"])
        self.aperture = DiscreteParameter(
            "aperture",
            config_map["aperture"],
            valid_values=[
                c
                for c in aperture.get_choices()
                if aperture_range
                and (aperture_range[0] <= parse_aperture(c) <= aperture_range[1])
            ],
            initial_value=aperture.get_value(),
        )
        self.parameters["aperture"] = self.aperture

        iso = camera_config.get_child_by_name("iso")
        self.iso = DiscreteParameter(
            "iso",
            config_map["iso"],
            valid_values=[
                v
                for v in iso.get_choices()
                if v.isnumeric()
                and iso_range
                and (iso_range[0] <= int(v) <= iso_range[1])
            ],
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
        self.pull_config()

    @property
    def config(self):
        return {p.name: p.value for p in self.parameters.values()}

    def set_value(self, key, value):
        config = self._camera.get_config()
        config.get_child_by_name(key).set_value(value)
        self._camera.set_config(config)

    def pull_config(self):
        camera_config = self._camera.get_config()
        for p in self.parameters.values():
            p.value = camera_config.get_child_by_name(p.field).get_value()
        print("Pulled config from camera")

    def push_config(self):
        camera_config = self._camera.get_config()
        for p in self.parameters.values():
            camera_config.get_child_by_name(p.field).set_value(p.value)
        self._camera.set_config(camera_config)
        print("Pushed config to camera")


class FancyCamera:
    def __init__(
        self,
        config_map: dict[str, str],
        aperture_range: tuple[int, int],
        iso_range: tuple[int, int] = (100, 1600),
    ):
        self._camera = gp.Camera()

        self.config = CameraManager(
            camera=self._camera,
            config_map=config_map,
            aperture_range=aperture_range,
            iso_range=iso_range,
        )
        # TODO: This is only needed for nikon
        # self.config.set_value("imagequality", "NEF (Raw)")
        self.light_meter = self.config.light_meter
        self.iso = self.config.iso
        self.aperture = self.config.aperture
        self.shutter = self.config.shutter

    def step_exposure(self, step: int):
        self.config.pull_config()
        parameter_order = [self.shutter, self.aperture, self.iso]
        for parameter in parameter_order:
            try:
                parameter.step_value(step)
            except IndexError:
                print(f"Can't step value for {parameter}; moving on to next parameter")
            else:
                self.config.push_config()
                return True
        return False

    def auto_expose(self, target_bounds=(-5, 5)):
        # FIRST DO SHUTTER
        print(f"auto exposing! initial {self.light_meter.value=}")
        lower_exposure_bound, upper_exposure_bound = target_bounds
        if self.light_meter.value < lower_exposure_bound:
            step = 1
        elif self.light_meter.value > upper_exposure_bound:
            step = -1
        else:
            print("DOING NOTHING; ALREADY EXPOSED PROPERLY")
            return self.light_meter.value
        while True:
            # print(f"CONT: {lower_exposure_bound} > {light_meter=} > {upper_exposure_bound}")
            if lower_exposure_bound <= self.light_meter.value <= upper_exposure_bound:
                # print(f"DONE: {lower_exposure_bound} <= {light_meter=} <= {upper_exposure_bound}")
                break
            print(
                f"Shutter speed: {self.shutter.value} | Aperture:"
                f" {self.aperture.value} | ISO: {self.iso.value} |"
                f" Exposure: {self.light_meter.value}"
            )
            try:
                self.step_exposure(step=step)
            except ValueError:
                raise ValueError("Can't adjust exposure anymore!")

            sleep(0.05)
        return self.light_meter.value

    def list_files(self, path="/"):
        result = []
        # get files
        for name, value in self._camera.folder_list_files(path):
            result.append(os.path.join(path, name))
        # read folders
        folders = []
        for name, value in self._camera.folder_list_folders(path):
            folders.append(name)
        # recurse over subfolders
        for name in folders:
            result.extend(self.list_files(os.path.join(path, name)))
        return result

    def capture_and_export(self, output_dir: Path, stem: str):
        _path = self._camera.capture(gp.GP_CAPTURE_IMAGE)
        path_on_camera = Path(_path.folder + _path.name)
        print(f"Captured to {path_on_camera}")
        camera_file = self._camera.file_get(
            _path.folder, _path.name, gp.GP_FILE_TYPE_NORMAL
        )
        capture_dt = datetime.fromtimestamp(camera_file.get_mtime())
        output_path = output_dir / f"{stem}{path_on_camera.suffix}"
        camera_file.save(str(output_path))
        return capture_dt, output_path

    def exit(self):
        return self._camera.exit()


@contextmanager
def open_camera(config_map: dict[str, str], *args, **kwargs):
    try:
        camera = FancyCamera(config_map, *args, **kwargs)
        yield camera
    except Exception:
        raise
    else:
        camera.exit()
