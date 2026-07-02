#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import asyncio
import os
import sys

import asyncpg


async def main() -> None:
    dsn = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    for _ in range(30):
        try:
            conn = await asyncpg.connect(dsn)
        except (OSError, asyncpg.PostgresError):
            await asyncio.sleep(1)
        else:
            await conn.close()
            return
    sys.exit("database not reachable after 30s")


asyncio.run(main())
PY
