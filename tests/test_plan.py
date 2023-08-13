from datetime import timedelta

from chrophos.plan import summary, output_summary


def test_summary():
    summary(input_frames=100, input_interval=timedelta(seconds=5), output_fps=30)


def test_output_summary():
    output_summary(input_span=timedelta(days=30), output_span=timedelta(seconds=60), output_fps=30)
