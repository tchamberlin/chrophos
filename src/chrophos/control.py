import argparse
from time import sleep
from datetime import timedelta, datetime
from pathlib import Path


from chrophos.camera import open_camera


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("-i", "--interval", type=int, required=True)
    parser.add_argument("-n", "--num-images", type=int, required=True)
    return parser.parse_args()


def timelapse(
    num_frames: int, interval: int, output_dir: Path, sleep_interval=0.01, auto_expose=False
):
    output_dir.mkdir(exist_ok=True, parents=True)
    template = "TL{}.nef"
    start = datetime.now() + timedelta(seconds=1)
    times = (start + timedelta(seconds=interval * i) for i in range(num_frames))
    paths_written = []
    with open_camera(aperture_range=(1, 16), iso_range=(100, 1600)) as camera:
        for i, commanded_capture_time in enumerate(times, 1):
            output_path = str(output_dir / template.format(i))
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
            actual_capture_time = camera.capture_and_export(output_path)
            paths_written.append(output_path)
            print(
                f"Saved #{i} to PC at {output_path}. Delta:"
                f" {actual_capture_time - commanded_capture_time}"
            )


def main():
    args = parse_args()

    timelapse(num_frames=args.num_images, interval=args.interval, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
