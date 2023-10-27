from datetime import timedelta

import typer

app = typer.Typer()


def format_timedelta(td: timedelta, threshold=timedelta(seconds=60)):
    if td < threshold:
        return f"{td.total_seconds():,}s"

    rounded = timedelta(seconds=int(round(td.total_seconds())))
    return f"{rounded} ({int(rounded.total_seconds()):,} seconds)"


@app.command()
def summary(input_frames: int = 1000, input_interval: float = 5, output_fps: float = 30.0):
    """If I take 100 pictures at a 5-second interval, that means it covers 100 * 5 seconds.

    If I play those 100 images back at 30fps, it will take 100 / 30 seconds

    The total speedup will be (100 * 5) / (100 / 30)
    """
    input_interval_td = timedelta(seconds=input_interval)
    input_timespan = input_frames * input_interval
    print(
        f"{input_frames:,} input frames captured at {input_interval_td.total_seconds()}-second"
        f" interval cover an input timespan of {format_timedelta(timedelta(seconds=input_timespan))}"
    )

    output_timespan = timedelta(seconds=input_frames / output_fps)
    speedup = input_timespan / output_timespan.total_seconds()
    print(
        f"When played back at {output_fps} fps, they will span {format_timedelta(output_timespan)},"
        f" a {speedup:.1f}x speedup"
    )
    one_second = timedelta(seconds=1)
    one_minute = timedelta(minutes=1)
    one_hour = timedelta(hours=1)
    one_day = timedelta(days=1)
    print(f"  One second of real time will play back in {format_timedelta(one_second/speedup)}")
    print(f"  One minute of real time will play back in {format_timedelta(one_minute/speedup)}")
    print(f"  One hour of real time will play back in {format_timedelta(one_hour/speedup)}")
    print(f"  One day of real time will play back in {format_timedelta(one_day/speedup)}")


def output_summary(input_span: timedelta, output_span: timedelta, output_fps: float):
    input_frames = output_span.total_seconds() * output_fps
    input_interval = timedelta(seconds=input_span.total_seconds() / input_frames)
    speedup = input_span.total_seconds() / output_span.total_seconds()
    print(
        f"Input span {format_timedelta(input_span)}, with output span of"
        f" {format_timedelta(output_span)}, played back at {output_fps:,} fps, then you need to"
        f" capture {input_frames:,} frames at {format_timedelta(input_interval)}. Your speedup will"
        f" be {speedup:,}x"
    )


if __name__ == "__main__":
    typer.run(summary)
