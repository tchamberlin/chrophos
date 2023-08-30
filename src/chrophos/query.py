import argparse
import json
from pathlib import Path
from queue import Queue

import gphoto2 as gp
import typer

app = typer.Typer()


def bfs(start_node):
    visited = dict()
    queue = Queue()
    queue.put(start_node)

    while not queue.empty():
        current_node = queue.get()
        for next_node in current_node.get_children():
            if next_node not in visited:
                queue.put(next_node)

                visited[next_node.get_name()] = next_node

    return visited


def parse_config(config):
    t = dict(sorted(bfs(config).items()))
    parsed = {}
    for key, node in t.items():
        try:
            value = node.get_value()
        except gp.GPhoto2Error:
            value = None
        if key in parsed:
            raise AssertionError("shit")

        try:
            choices = list(node.get_choices())
        except gp.GPhoto2Error:
            choices = []
        parsed[key] = {"current": value, "choices": choices}

    return parsed


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    return parser.parse_args()


@app.command()
def main():
    args = parse_args()
    camera = gp.Camera()
    raw_config = camera.get_config()
    parsed_config = parse_config(raw_config)
    with open(args.output, "w") as file:
        json.dump(parsed_config, file)


if __name__ == "__main__":
    main()
