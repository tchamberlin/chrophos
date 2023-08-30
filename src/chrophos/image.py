from pathlib import Path
from typing import Union

import numpy as np
import rawpy


def load_raw_file(path: Union[Path, str]):
    raw: rawpy._rawpy.RawPy = rawpy.imread(str(path))
    rgb: np.ndarray = raw.postprocess()
    return rgb
