from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import rawpy
from skimage import exposure, img_as_float
from skimage.util import img_as_ubyte

EQUALIZATION_METHODS: dict[str, Callable[[Any], Any]] = {"global": exposure.equalize_hist}


# return math.log2(aperture)


def plot_img_and_hist(image, axes, bins=256):
    """Plot an image along with its histogram and cumulative histogram."""
    image = img_as_float(image)
    ax_img, ax_hist = axes
    ax_cdf = ax_hist.twinx()

    # Display image
    ax_img.imshow(image, cmap=plt.cm.gray)
    ax_img.set_axis_off()

    # Display histogram
    ax_hist.hist(image.ravel(), bins=bins, histtype="step", color="black")
    ax_hist.ticklabel_format(axis="y", style="scientific", scilimits=(0, 0))
    ax_hist.set_xlabel("Pixel intensity")
    ax_hist.set_xlim(0, 1)
    ax_hist.set_yticks([])

    # Display cumulative distribution
    img_cdf, bins = exposure.cumulative_distribution(image, bins)
    ax_cdf.plot(bins, img_cdf, "r")
    ax_cdf.set_yticks([])

    return ax_img, ax_hist, ax_cdf


def auto_exposure2(raw, target_mean):
    raw_data = raw.raw_image_visible.astype(np.float64)

    # Calculate the mean brightness of the raw image
    current_mean = np.mean(raw_data)

    # Calculate the required exposure compensation factor
    exposure_compensation = np.log2(target_mean / current_mean)

    return exposure_compensation


def auto_exposure(image: rawpy._rawpy.RawPy):
    linear_image = image.postprocess(use_camera_wb=True, half_size=True, no_auto_bright=True)

    # Convert the image to grayscale
    gray_image = np.mean(linear_image, axis=2)

    # Calculate the average brightness
    average_brightness = np.mean(gray_image)

    return average_brightness


def equalize(image, method="global"):
    try:
        equalizer = EQUALIZATION_METHODS[method]
    except IndexError as error:
        raise ValueError(f"Invalid equalization method give: {method!r}") from error

    return equalizer(img_as_ubyte(image))


def compare_equalization_methods(
    image,
):
    img = img_as_ubyte(image)

    # Contrast stretching
    p2, p98 = np.percentile(img, (2, 98))
    img_rescale = exposure.rescale_intensity(img, in_range=(p2, p98))

    # Equalization
    img_eq = exposure.equalize_hist(img)

    # Adaptive Equalization
    img_adapteq = exposure.equalize_adapthist(img, clip_limit=0.03)

    print(f"Raw mean: {image.mean()}")
    print(f"Contrast Stretching mean pixel intensity: {img_rescale.mean()}")
    print(f"Histogram Equalization mean pixel intensity: {img_eq.mean()}")
    print(f"Histogram Adaptive Equalization mean pixel intensity: {img_adapteq.mean()}")
    # Display results
    fig = plt.figure(figsize=(12, 4))
    axes = np.zeros((2, 4), dtype=object)
    axes[0, 0] = fig.add_subplot(2, 4, 1)
    for i in range(1, 4):
        axes[0, i] = fig.add_subplot(2, 4, 1 + i, sharex=axes[0, 0], sharey=axes[0, 0])
    for i in range(0, 4):
        axes[1, i] = fig.add_subplot(2, 4, 5 + i)

    ax_img, ax_hist, ax_cdf = plot_img_and_hist(img, axes[:, 0])
    ax_img.set_title("Low contrast image")

    y_min, y_max = ax_hist.get_ylim()
    ax_hist.set_ylabel("Number of pixels")
    ax_hist.set_yticks(np.linspace(0, y_max, 5))

    ax_img, ax_hist, ax_cdf = plot_img_and_hist(img_rescale, axes[:, 1])
    ax_img.set_title("Contrast stretching")

    ax_img, ax_hist, ax_cdf = plot_img_and_hist(img_eq, axes[:, 2])
    ax_img.set_title("Histogram equalization")

    ax_img, ax_hist, ax_cdf = plot_img_and_hist(img_adapteq, axes[:, 3])
    ax_img.set_title("Adaptive equalization")

    ax_cdf.set_ylabel("Fraction of total intensity")
    ax_cdf.set_yticks(np.linspace(0, 1, 5))

    # prevent overlap of y-axis labels
    fig.tight_layout()
    return fig
