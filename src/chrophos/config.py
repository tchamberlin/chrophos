from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Union

import tomlkit


class Aperture(float):
    pass


class Shutter(str):
    pass


class ISO(int):
    pass


@dataclass
class Complex:
    key: str
    values: dict[str, Any]


@dataclass
class Config:
    target_iso: ISO
    target_shutter: Shutter
    target_aperture: Aperture
    aperture_min: Aperture
    aperture_max: Aperture
    iso_min: ISO
    iso_max: ISO
    config_map: dict[str, Union[str, Complex]]
    dark_time: timedelta


def parse_config_raw(path: Path):
    with open(path, "rb") as file:
        return tomlkit.load(file)


def parse_param(param: Union[str, dict[str, Any]]):
    if isinstance(param, str):
        return param

    return Complex(key=param["key"], values=param["values"])


def parse_config(path: Path):
    config = parse_config_raw(path)
    return Config(
        target_iso=config["target_iso"],
        target_shutter=config["target_shutter"],
        target_aperture=config["target_aperture"],
        aperture_min=config["aperture_min"],
        aperture_max=config["aperture_max"],
        iso_min=config["iso_min"],
        iso_max=config["iso_max"],
        config_map={k: parse_param(v) for k, v in config["config_map"].items()},
        dark_time=timedelta(seconds=config["dark_time"]),
    )
