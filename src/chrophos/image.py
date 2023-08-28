from pathlib import Path

import numpy as np
import rawpy


def load_raw_file(path: Path | str):
    raw: rawpy._rawpy.RawPy = rawpy.imread(str(path))
    rgb: np.ndarray = raw.postprocess()
    return rgb
