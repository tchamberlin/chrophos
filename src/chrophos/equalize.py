import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rawpy
from skimage import exposure
from skimage.color import rgb2gray
from skimage.util import img_as_float
from skimage.morphology import disk
from skimage.morphology import ball
from skimage.filters import rank

from chrophos.exposure import equalize


def get_exposure_compensation(mean_intensity: float, target_intensity=0.5):
    steps_ev_compensation = math.log2(mean_intensity / target_intensity)
    return steps_ev_compensation


def get_average_intensity(image):
    mean = image.mean()
    if not (0 <= mean <= 1):
        raise AssertionError(f"Expected average intensity to be between 0 and 1; got {mean}")
    return mean


def auto_exposure(raw, target_mean=128):
    # Calculate the mean brightness of the raw image
    current_mean = np.mean(raw)
    print(f"{current_mean=}")
    # Calculate the required exposure compensation factor
    exposure_compensation = np.log2(current_mean / target_mean)

    return exposure_compensation


def foo(path: Path):
    for p in sorted(path.glob("*.NEF")):
        raw: rawpy._rawpy.RawPy = rawpy.imread(str(p))
        rgb: np.ndarray = raw.postprocess()
        r, g, b = rgb.T
        mean_luma = 0.299 * r + 0.587 * g + 0.144 * b
        breakpoint()
        gray = rgb2gray(rgb)
        original_mean_intensity = get_average_intensity(gray)
        equalized_image = equalize(gray)
        equalized_mean_intensity = equalized_image.mean()

        direction = "under" if equalized_mean_intensity > original_mean_intensity else "over"
        print(
            f"{p.name}:"
            f" {equalized_mean_intensity - original_mean_intensity=:.2f} ({direction}-exposed) "
        )


def plot_image_and_hist(ax_image, ax_hist, image, hist):
    # Display image
    ax_image.imshow(image)

    ax_hist.hist(mean_luma.ravel(), bins=256, histtype="step")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    paths = sorted(args.path.glob("*.NEF"))[::2]

    fig: plt.Figure = plt.figure(figsize=(8, 8))
    axes = fig.subplots(len(paths), 4, sharey=False)

    for i, p in enumerate(paths):
        raw: rawpy._rawpy.RawPy = rawpy.imread(str(p))
        rgb: np.ndarray = raw.postprocess(use_camera_wb=True, half_size=True, no_auto_bright=True)
        r, g, b = rgb.T
        gray = rgb2gray(rgb)
        luma = 0.299 * r + 0.587 * g + 0.144 * b
        original_mean_intensity = gray.mean()

        # Histogram Equalization
        equalized_image = equalize(rgb)

        # Contrast Stretching
        # p2, p98 = np.percentile(rgb, (2, 98))
        # equalized_image = exposure.rescale_intensity(rgb, in_range=(p2, p98))

        # Adaptive Histogram Equalization
        # equalized_image = exposure.equalize_adapthist(rgb, clip_limit=0.03)

        # neighborhood = ball(1)
        # equalized_image = rank.equalize(rgb, footprint=neighborhood)

        equalized_mean_intensity = equalized_image.mean()
        original_luma_mean = luma.mean()
        eq_r, eq_g, eq_b = equalized_image.T
        eq_luma = (0.299 * eq_r + 0.587 * eq_g + 0.144 * eq_b) * 256

        # PLOT 1
        ax_image = axes[i, 1]
        ax_image.set_xlabel(f"{p.name}")
        ax_image.set_axis_off()
        ax_image.imshow(img_as_float(rgb))

        # PLOT 2
        ax_hist = axes[i, 0]
        ax_hist.hist(r.ravel(), bins=256, histtype="step", color="red")
        ax_hist.hist(g.ravel(), bins=256, histtype="step", color="green")
        ax_hist.hist(b.ravel(), bins=256, histtype="step", color="blue")
        ax_hist.hist(luma.ravel(), bins=256, histtype="step")
        ax_hist.set_xlim(0, 256)

        # PLOT 3
        ax_eq_hist = axes[i, 3]
        ax_eq_hist.hist(eq_r.ravel() * 256, bins=256, histtype="step", color="red")
        ax_eq_hist.hist(eq_g.ravel() * 256, bins=256, histtype="step", color="green")
        ax_eq_hist.hist(eq_b.ravel() * 256, bins=256, histtype="step", color="blue")
        ax_eq_hist.hist(eq_luma.ravel(), bins=256, histtype="step")
        ax_eq_hist.set_xlim(0, 256)

        # PLOT 4
        ax_eq_image = axes[i, 2]
        ax_eq_image.set_xlabel(f"{p.name}")
        ax_eq_image.set_axis_off()
        ax_eq_image.imshow(img_as_float(equalized_image))
        print(
            f"{p.name}: {equalized_mean_intensity=:.2f}; {original_mean_intensity=:.2f}\n"
            f"  {np.log2(equalized_mean_intensity / original_mean_intensity)=:.2f} stops\n"
            f"  {np.log2(eq_r.mean()*256 / r.mean())=:.2f} stops\n"
            f"  {np.log2(eq_g.mean()*256 / g.mean())=:.2f} stops\n"
            f"  {np.log2(eq_b.mean()*256 / b.mean())=:.2f} stops"
        )
    plt.tight_layout()
    plt.show()
