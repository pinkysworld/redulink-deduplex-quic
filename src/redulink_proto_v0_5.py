#!/usr/bin/env python3
"""Backward-compatible entrypoint for the ReduLink artifact model."""

from redulink_model import *  # noqa: F401,F403
from redulink_model import main


if __name__ == "__main__":
    main()
