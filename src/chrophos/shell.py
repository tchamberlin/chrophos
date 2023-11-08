import IPython

from chrophos.camera.backend import Backend
from chrophos.camera.camera import open_camera
from chrophos.config import CameraConfig


def shell(config: CameraConfig, backend: Backend):
    with open_camera(backend=backend, config=config):
        IPython.embed(header="HI")
