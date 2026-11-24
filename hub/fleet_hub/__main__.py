"""Run the hub: ``python -m fleet_hub`` (settings from the environment, see deploy/.env.example).

On first start (no admin yet) it logs a one-time link that creates the admin
account. For local testing, sign in with any name instead:

    HUB_DEV_LOGIN=1 python -m fleet_hub

then open http://127.0.0.1:8100/ (the first name you use becomes admin).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

from .app import serve
from .config import Config


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("HUB_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve(Config.from_env()))


if __name__ == "__main__":
    main()
