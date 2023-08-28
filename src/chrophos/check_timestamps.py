import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("-i", "--interval", type=int, required=True)
    return parser.parse_args()


def check_timestamps(path: Path, interval: int, threshold=0.1):
    creation_times = []
    for image_path in path.iterdir():
        create_date = Image.open(image_path).getxmp()["xmpmeta"]["RDF"]["Description"][0][
            "CreateDate"
        ]
        creation_times.append(datetime.fromisoformat(create_date))
    actual_intervals = np.diff(creation_times)
    # print(actual_intervals)
    diffs = np.absolute(timedelta(seconds=interval) - actual_intervals)
    num_intervals_over_threshold = np.count_nonzero(diffs > timedelta(threshold))
    print(f"Number of intervals over threshold ({threshold}s): {num_intervals_over_threshold}")


def main():
    args = parse_args()

    check_timestamps(args.path, args.interval)


if __name__ == "__main__":
    main()
