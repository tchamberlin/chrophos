import logging
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Optional

import typer

import chrophos.bench
import chrophos.plan
import chrophos.query
import chrophos.shell
import chrophos.timelapse
from chrophos.camera.backend import Canon5DII
from chrophos.config import Config, parse_config

app = typer.Typer()

logger = logging.getLogger(__name__)

state = {"config": None, "dry_run": False}


def init_logging(verbosity: int):
    if verbosity == 0:
        log_level = logging.WARNING
    elif verbosity == 1:
        log_level = logging.INFO
    elif verbosity == 2:
        log_level = logging.DEBUG
    else:
        raise ValueError(f"Invalid verbosity level: {verbosity}")

    module_logger = logging.getLogger("chrophos")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = logging.Formatter(
        "[%(asctime)s - %(module)s.%(funcName)s - %(levelname)s] %(message)s"
    )
    console_handler.setFormatter(formatter)
    module_logger.addHandler(console_handler)
    module_logger.setLevel(log_level)


@app.command()
def plan(
    input_frames: Annotated[int, typer.Option("-f", "--frames")] = 1000,
    input_interval: Annotated[float, typer.Option("-i", "--capture-interval")] = 20,
    output_fps: Annotated[int, typer.Option("-o", "--output-fps")] = 30,
):
    chrophos.plan.summary(
        input_frames=input_frames, input_interval=input_interval, output_fps=output_fps
    )


@app.command()
def query():
    chrophos.query.main()


@app.command()
def bench(
    trials: int,
    shutters: list[str],
    output_dir: Annotated[Path, typer.Option("-o", "--output")] = Path("./raw_bench_images"),
):
    config: Config = state["config"]
    chrophos.bench.bench(
        trials=trials,
        shutters=shutters,
        backend=Canon5DII(
            config_map=config.config_map,
            target_aperture=config.target_aperture,
            target_iso=config.target_iso,
            target_shutter=config.target_shutter,
        ),
        output_dir=output_dir,
        config=config,
    )


@app.command()
def shell():
    config = state["config"]
    chrophos.shell.shell(
        config=config,
        backend=Canon5DII(
            config_map=config.config_map,
            target_aperture=config.target_aperture,
            target_iso=config.target_iso,
            target_shutter=config.target_shutter,
        ),
    )


@app.command()
def timelapse(
    interval: int,
    mode: Annotated[str, typer.Option("-m", "--mode")],
    num_frames: Optional[int] = None,
    output_dir: Annotated[Path, typer.Option("-o", "--output")] = Path("./raw_timelapse_images"),
):
    config: Config = state["config"]
    dry_run = state["dry_run"]
    chrophos.timelapse.timelapse(
        backend=Canon5DII(
            config_map=config.config_map,
            target_aperture=config.target_aperture,
            target_iso=config.target_iso,
            target_shutter=config.target_shutter,
        ),
        mode=mode,
        config=config,
        num_frames=num_frames,
        interval=timedelta(seconds=interval),
        output_dir=output_dir,
        dry_run=dry_run,
    )


@app.callback()
def main(
    config_path: Annotated[Path, typer.Option("--config", "-c")],
    verbosity: Annotated[int, typer.Option("-v")] = 1,
    dry_run: Annotated[bool, typer.Option("-D", "--dry-run")] = False,
):
    state["config"] = parse_config(config_path)
    state["dry_run"] = dry_run
    init_logging(verbosity)


if __name__ == "__main__":
    app()
