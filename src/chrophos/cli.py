from datetime import timedelta

import typer

from chrophos.plan import summary

app = typer.Typer()


@app.command()
def plan(input_frames: int, input_seconds: float, output_fps: float):
    summary(
        input_frames=input_frames,
        input_interval=timedelta(seconds=input_seconds),
        output_fps=output_fps,
    )


def main():
    app()


if __name__ == "__main__":
    main()
