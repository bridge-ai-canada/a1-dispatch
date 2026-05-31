"""Migration runner — discovers `NNNN_*.py` modules and applies pending ones."""
import asyncio
import importlib
import pkgutil
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure backend/ is on sys.path when invoked via `python -m migrations.runner`
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from deps import db, logger  # noqa: E402


async def _ensure_collection():
    await db.schema_migrations.create_index("name", unique=True)


def _list_migrations() -> list[str]:
    names = []
    for mod in pkgutil.iter_modules([str(_HERE)]):
        if mod.name == "runner" or mod.name.startswith("_"):
            continue
        names.append(mod.name)
    return sorted(names)


async def run_pending() -> dict:
    """Run all migrations not yet recorded. Returns summary {ran:[...], skipped:[...]}."""
    await _ensure_collection()
    ran, skipped = [], []
    for name in _list_migrations():
        existing = await db.schema_migrations.find_one({"name": name}, {"_id": 0})
        if existing:
            skipped.append(name)
            continue
        module = importlib.import_module(f"migrations.{name}")
        if not hasattr(module, "up"):
            logger.warning(f"migrations: {name} has no `up()` function — skipped")
            continue
        logger.info(f"migrations: running {name}")
        await module.up(db)
        await db.schema_migrations.insert_one({
            "name": name,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        })
        ran.append(name)
    logger.info(f"migrations: ran={ran} skipped={len(skipped)}")
    return {"ran": ran, "skipped": skipped}


if __name__ == "__main__":
    summary = asyncio.run(run_pending())
    print(summary)
