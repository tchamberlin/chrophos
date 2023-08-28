from datetime import timedelta


def format_timedelta(td: timedelta):
    return f"{td} ({td.total_seconds():,} seconds)"


def summary(input_frames: int, input_interval: timedelta, output_fps: float):
    """If I take 100 pictures at a 5-second interval, that means it covers 100 * 5 seconds.

    If I play those 100 images back at 30fps, it will take 100 / 30 seconds

    The total speedup will be (100 * 5) / (100 / 30)


    :return:
    """
    input_timespan = input_frames * input_interval
    print(
        f"{input_frames:,} input frames captured at {input_interval.total_seconds()}-second"
        f" interval cover an input timespan of {format_timedelta(input_timespan)} seconds)"
    )

    output_timespan = timedelta(seconds=input_frames / output_fps)
    speedup = input_timespan.total_seconds() / output_timespan.total_seconds()
    print(
        f"When played back at {output_fps} fps, they will span {format_timedelta(output_timespan)},"
        f" a {speedup:.1f}x speedup"
    )


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
