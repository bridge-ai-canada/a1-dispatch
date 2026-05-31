"""Lightweight Mongo migration framework.

Migrations are async functions in `migrations/NNNN_name.py` exporting `async def up(db)`.
A `schema_migrations` collection tracks which have run. The runner is idempotent
and can be called manually (`python -m migrations.runner`) or from startup
via `await migrations.runner.run_pending()`.
"""
