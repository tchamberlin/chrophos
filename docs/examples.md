# Examples

## Plan

```txt
$ chrophos plan --capture-interval 20 --frames 1000 --output-fps 60
1,000 input frames captured at 20.0-second interval cover an input
timespan of 5:33:20 (20,000 seconds)
When played back at 60 fps, they will span 16.666667s, a 1200.0x speedup
  One second of real time will play back in 0.000833s
  One minute of real time will play back in 0.05s
  One hour of real time will play back in 3.0s
  One day of real time will play back in 0:01:12 (72 seconds)
```


## Benchmark Dark Time


Dark time is the minimum amount of time between the end of a capture and the start of the next capture. It is primarily comprised of
```txt
$ chrophos -c ./config/canon5dii.toml bench 3 1/8000 1 10.3 30
Shutter 1/8000 mean dark time across 3 trials
    Min:  2.73
    Mean: 2.87
    Max:  2.94
Shutter 1 mean dark time across 3 trials
    Min:  3.01
    Mean: 3.08
    Max:  3.17
Shutter 10.3 mean dark time across 3 trials
    Min:  3.34
    Mean: 3.36
    Max:  3.38
Shutter 30 mean dark time across 3 trials
    Min:  5.21
    Mean: 5.25
    Max:  5.32
Overall dark time
    Min:  2.73
    Mean: 3.64
    Max:  5.32
```
