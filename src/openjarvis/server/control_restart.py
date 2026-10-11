"""Restart only after the owned server drains and exits; never force-kill it."""

import sys
import time

from openjarvis.core.utils import process_alive


def main():
    pid, host, port = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
    deadline = time.monotonic() + 45
    while process_alive(pid):
        if time.monotonic() >= deadline:
            raise SystemExit(
                "Restart blocked: previous server has not finished shutdown"
            )
        time.sleep(0.25)
    from openjarvis.cli import cli

    cli.main(args=["start", "--host", host, "--port", str(port)])


if __name__ == "__main__":
    main()
