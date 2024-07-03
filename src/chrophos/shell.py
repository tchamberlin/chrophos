import IPython

from chrophos.camera.camera import Camera


def shell(camera: Camera):
    IPython.embed(header="HI")
