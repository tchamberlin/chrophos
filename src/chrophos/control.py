import argparse
from time import sleep
from datetime import timedelta, datetime
from pathlib import Path


from chrophos.camera import open_camera


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("camera_type", choices=["z6", "5dii"])
    parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        type=Path,
        default=Path("./raw_timelapse_images"),
    )
    parser.add_argument("-i", "--interval", type=int, required=True)
    parser.add_argument("-n", "--num-images", type=int, required=True)
    return parser.parse_args()


def timelapse(
    config_map: dict[str, str],
    num_frames: int,
    interval: int,
    output_dir: Path,
    sleep_interval=0.01,
    auto_expose=False,
):
    output_dir.mkdir(exist_ok=True, parents=True)
    template = "TL{num}"
    start = datetime.now() + timedelta(seconds=1)
    times = (start + timedelta(seconds=interval * i) for i in range(num_frames))
    paths_written = []
    with open_camera(
        config_map, aperture_range=(1, 16), iso_range=(100, 1600)
    ) as camera:
        for i, commanded_capture_time in enumerate(times, 1):
            stem = template.format(num=i)
            print(
                f"Waiting {commanded_capture_time - datetime.now()} until"
                f" {commanded_capture_time} for capture #{i}"
            )
            while True:
                if commanded_capture_time - datetime.now() <= timedelta(0):
                    print(f"Done waiting for {i}")
                    break
                else:
                    sleep(sleep_interval)
            if auto_expose:
                light_meter = camera.auto_expose()
                print(f"Adjusted exposure; light meter is now {light_meter}")
            actual_capture_time, output_path = camera.capture_and_export(
                output_dir, stem
            )
            paths_written.append(output_path)
            print(
                f"Saved #{i} to PC at {output_path}. Delta:"
                f" {actual_capture_time - commanded_capture_time}"
            )


def main():
    args = parse_args()
    if args.camera_type == "5dii":
        config_map = {
            "shutter": "shutterspeed",
            "aperture": "aperture",
            "iso": "iso",
        }
    elif args.camera_type == "z6":
        config_map = {
            "shutter": "shutterspeed2",
            "aperture": "f-number",
            "iso": "iso",
            "light_meter": "lightmeter",
        }
    else:
        raise ValueError(f"Unsupported camera {args.camera_type}")
    timelapse(
        config_map=config_map,
        num_frames=args.num_images,
        interval=args.interval,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
