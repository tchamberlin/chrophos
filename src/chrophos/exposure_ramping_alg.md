# Exposure ramping algorithm

Goals:
- shoot in M mode
- handle day/night transitions during timelapse
- avoid sudden changes in exposure
- provide adjustable smoothing factor (that determines how large a jump in exposure can be based on previous values)


Limitations:
- no light meter is directly available to read
- camera is quite bad at auto-exposing (e.g. in P mode) at night/low light conditions
- can't reliable autofocus

Outline:
0. Initial setup
    1. Manually focus camera; set lens to M focus
    2. Put in box
    3. Set up framing using live view (via Entangle, for now)
    4. Set rectangle that defines a "sky region" to use for luminance calcs
1. Initialize camera (switch control over to chrophos)
2. Set camera to A mode: f/4 ISO 100
3. Read shutter speed (during half press)
4. Capture image
5. Calculate average luminance in sky region
6. Switch to M mode using shutter speed derived previously, keeping f/4 and ISO 100
7. Init timelapse loop
    1. Capture image
    2. Compare average luminance in sky region to previous value
    3. If delta is greater than allowable, do ONE OF:
        - If possible, lengthen shutter speed
        - If can't lengthen shutter, lower aperture



Initial parameters that need to be sent to camera:
- Interval
- Max expected dark time (derived earlier via benchmarking script)
- Sky region boundaries (in pixels?)
- Luminance delta (i.e. value at which exposure settings need to change)
