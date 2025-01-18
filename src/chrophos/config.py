from pathlib import Path
from typing import Any, List, Type, Union

import tomlkit
from pydantic import BaseModel


class ConfigFileError(ValueError):
    ...


class ConfigParameter(BaseModel):
    type: str
    name: str
    config_key: str
    read_only: bool = False
    initial_value: Union[str, float, None] = None
    target: Union[Any, None] = None


class DiscreteConfigParameter(ConfigParameter):
    valid_min: Union[str, float, None] = None
    valid_max: Union[str, float, None] = None
    valid_choices: Union[List[Union[float, str]], None] = None


class BooleanConfigParameter(ConfigParameter):
    true: Any
    false: Any


class RangeConfigParameter(ConfigParameter):
    valid_min: Union[str, float, None] = None
    valid_max: Union[str, float, None] = None


PARAMETER_MAP: dict[str, Type] = {
    "discrete": DiscreteConfigParameter,
    "range": RangeConfigParameter,
    "boolean": BooleanConfigParameter,
}


class CameraConfig(BaseModel):
    camera_model: str
    parameters: dict[str, ConfigParameter]

    @staticmethod
    def read(path: Path):
        config = parse_config(path)
        return CameraConfig(camera_model=config["camera_model"], parameters=config["parameters"])


def parse_config_raw(path: Path):
    """Simply parse the config file as TOML"""
    with open(path, "rb") as file:
        return tomlkit.load(file)


def _parse_config(config: Union[dict, tomlkit.TOMLDocument]):
    parameters: dict[str, ConfigParameter] = {}
    for parameter_name, parameter_config in config["parameters"].items():
        parameter_type = parameter_config["type"]
        parameter_class = PARAMETER_MAP[parameter_type]
        try:
            parameters[parameter_name] = parameter_class(name=parameter_name, **parameter_config)
        except TypeError as error:
            raise ConfigFileError(f"Invalid: {error}") from error
    return {"camera_model": config["camera_model"], "parameters": parameters}


def parse_config(path: Path):
    """Fully parse and validate the config file at `path`"""
    raw_config = parse_config_raw(path)
    validate_config(raw_config)
    return _parse_config(raw_config)


def validate_config(config: dict):
    for parameter_name, parameter_config in config["parameters"].items():
        try:
            parameter_type = parameter_config["type"]
        except KeyError as error:
            raise ConfigFileError(
                f"[parameter.{parameter_name}] does not contain `type`"
            ) from error

        try:
            PARAMETER_MAP[parameter_type]
        except KeyError as error:
            raise ConfigFileError(
                f"{parameter_type=} is invalid! Valid choices are: {PARAMETER_MAP}"
            ) from error
