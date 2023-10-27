# Chrophos: Timelapse Utilities

A command-line application for planning and managing timelapse photography sequences of infinite length, using commodity hardware and free, open source software.

Features:

- [Plan timelapses](examples.md#plan) (e.g. determine length of final timelapse given number of input frames, capture rate, and playback rate)
- [Benchmark camera capture rate](examples.md#benchmark-dark-time) (e.g. determine length of final timelapse given number of input frames, capture rate, and playback rate)

## Overview

Chrophos is best understood in the context of its creation: a long-term, fully automated timelapse project. In this context, it exists as part of a larger system:

PHYSICAL

``` mermaid
graph TD
    ac_power["A/C Power"]:::power
    subgraph Timelapse Capture Box
        computer[Computer]:::software
        camera[/Camera/]
        storage[(Storage)]:::storage
        battery((Battery)):::power
    end

    ac_power-.->|"USB (power)"|battery
    computer<-->|"USB (data)"|storage
    computer<-->|"USB (data)"|camera
    battery-.->|"USB (power)"|camera
    battery-.->|"USB (power)"|computer


    classDef storage fill:#cce6ff,stroke:#004d99,stroke-width:1px;
    classDef power fill:#ffcccc,stroke:#ff0000,stroke-width:1px;
    classDef software fill:#d6f5d6,stroke:#1f7a1f,stroke-width:1px;
```

``` mermaid
graph TD
    ac_power["A/C Power"]:::power
    subgraph Timelapse Capture Box
        subgraph Computer
            chrophos[Chrophos]:::software
        end
        camera[/Camera/]
        storage[(Storage)]:::storage
        battery((Battery)):::power
    end

    subgraph Timelapse Processing Host
        giant_hard_drive[(Giant Hard Drive)]:::storage
    end

    ac_power-.->|power|battery
    camera-->|transfer image via USB|chrophos
    chrophos-->|transfer images via USB|storage
    chrophos-->|control|camera
    battery-.->|power|camera
    battery-.->|power|Computer

    chrophos-->|transfer images via network|giant_hard_drive

    classDef storage fill:#cce6ff,stroke:#004d99,stroke-width:1px;
    classDef power fill:#ffcccc,stroke:#ff0000,stroke-width:1px;
    classDef software fill:#d6f5d6,stroke:#1f7a1f,stroke-width:1px;
```

The Chrophos control software is in green. It has two responsibilities:

1. Control the camera (via `gphoto2`)
    - Trigger captures at a precise interval
    - Adjust exposure and ISO settings
2. Download images from the camera (via `gphoto2`)






## Trivia

"Chrophos" derives from the Greek prefix "chro" (time) and "phos" (light)
