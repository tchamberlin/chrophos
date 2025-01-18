from chrophos.camera.camera import Camera


def auto_expose(camera: Camera):
    camera.auto_expose_via_light_meter()
