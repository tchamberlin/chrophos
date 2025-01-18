"""Take a sequence of captures with given settings"""
import logging
from pathlib import Path
from time import sleep

from chrophos.camera.backend import Backend
from chrophos.camera.camera import Camera, open_camera
from chrophos.camera.parameter import ValidationError
from chrophos.config import CameraConfig

logger = logging.getLogger(__name__)


def gen_configs(base_config: CameraConfig, action: str):
    if action == "aperture_ramp":
        ...
    else:
        raise NotImplementedError(f"Unsupported action {action} given")


def capture_aperture_ramp(
    camera: Camera,
    initial_aperture: str,
    output_dir: Path,
    delay=1,
    step_by=1,
    iso=1000,
):
    camera.set_aperture_priority_mode()
    camera.aperture = initial_aperture
    camera.iso = iso
    camera.backend.push_config()
    while True:
        # TODO: stem should be serialized config options
        path, _ = camera.capture_and_download(
            output_dir=output_dir,
            stem=f"{{capture_dt}}_aperture_{camera.aperture.value}",
        )
        logger.info(f"Captured image at aperture {camera.aperture.value} to {path}")
        try:
            camera.step_aperture(step_by)
        except ValidationError:
            logger.info(f"Cannot step by {step_by}; test complete")
            return
        else:
            camera.backend.push_config()
            sleep(delay)


def capture_focus_ramp(
    camera: Camera,
    output_dir: Path,
    delay=0.1,
    step_by=1,
    iso=100,
):
    camera.set_aperture_priority_mode()
    camera.iso = iso
    camera.backend.push_config()
    while True:
        # TODO: stem should be serialized config options
        path, _ = camera.capture_and_download(
            output_dir=output_dir,
            stem="{{capture_dt}}_focus",
        )
        logger.info(f"Captured image at aperture {camera.aperture.value} to {path}")
        try:
            camera.step_focus(step_by)
        except ValidationError:
            logger.info(f"Cannot step by {step_by}; test complete")
            return
        else:
            camera.backend.push_config()
            sleep(delay)


# configs: list[CameraConfig]
def capture_sequence(
    backend: Backend,
    base_config: CameraConfig,
    action: str,
    output_dir: Path,
    step_by: int = 1,
    iso=100,
):
    """Trigger the given `captures` at the given `interval`"""

    with open_camera(backend=backend, config=base_config) as camera:
        if action == "aperture_ramp":
            capture_aperture_ramp(
                camera=camera,
                initial_aperture=base_config.aperture_min,
                output_dir=output_dir,
                step_by=step_by,
                iso=iso,
            )
        elif action == "focus_ramp":
            capture_focus_ramp(
                camera=camera,
                output_dir=output_dir,
                step_by=step_by,
                iso=iso,
            )
        else:
            raise NotImplementedError(f"Unsupported action {action:r} given")
