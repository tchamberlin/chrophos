import logging
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Optional

import typer

import chrophos.auto_expose
import chrophos.bench
import chrophos.plan
import chrophos.query
import chrophos.seq
import chrophos.shell
import chrophos.timelapse
from chrophos.camera.backend import Gphoto2Backend
from chrophos.camera.camera import Camera
from chrophos.config import CameraConfig

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
    mode: Annotated[str, typer.Option("-m", "--mode")],
    output_dir: Annotated[Path, typer.Option("-o", "--output")] = Path("./raw_bench_images"),
):
    chrophos.bench.bench(
        trials=trials,
        mode=mode,
        shutters=shutters,
        camera=state["camera"],
        output_dir=output_dir,
    )


@app.command()
def auto_expose():
    chrophos.auto_expose.auto_expose(
        camera=state["camera"],
    )


@app.command()
def shell():
    chrophos.shell.shell(camera=state["camera"])


@app.command()
def timelapse(
    interval: int,
    mode: Annotated[str, typer.Option("-m", "--mode")],
    num_frames: Optional[int] = None,
    output_dir: Annotated[Path, typer.Option("-o", "--output")] = Path("./raw_timelapse_images"),
):
    chrophos.timelapse.timelapse(
        camera=state["camera"],
        mode=mode,
        num_frames=num_frames,
        interval=timedelta(seconds=interval),
        output_dir=output_dir,
        dry_run=state["dry_run"],
    )


@app.callback()
def main(
    config_path: Annotated[Path, typer.Option("--config", "-c")],
    verbosity: Annotated[int, typer.Option("-v")] = 1,
    dry_run: Annotated[bool, typer.Option("-D", "--dry-run")] = False,
):
    state["config"] = CameraConfig.read(config_path)
    state["backend"] = Gphoto2Backend(camera_name=state["config"].camera_model)
    state["camera"] = Camera(backend=state["backend"], config=state["config"])
    state["dry_run"] = dry_run
    init_logging(verbosity)


if __name__ == "__main__":
    app()
