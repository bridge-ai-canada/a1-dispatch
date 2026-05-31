"""0001 — Consolidate inline migrations + ensure baseline indexes.

This migration is idempotent. It consolidates the ad-hoc `update_many` calls
that previously lived in server.py startup, and creates indexes that may have
been missed when collections were added incrementally.
"""


async def up(db) -> None:
    # Legacy job status normalization
    await db.jobs.update_many(
        {"status": "scheduled"},
        {"$set": {"status": "scheduled_installation"}},
    )

    # Default subscription block for legacy companies created before billing existed
    await db.companies.update_many(
        {"subscription": {"$exists": False}},
        {"$set": {"subscription": {"plan": "basic", "status": "active"}}},
    )

    # Defensive baseline indexes (no-op if already present)
    await db.users.create_index("email", unique=True)
    await db.users.create_index("company_id")
    await db.jobs.create_index([("company_id", 1), ("status", 1)])
    await db.jobs.create_index([("company_id", 1), ("scheduled_at", 1)])
    await db.activity.create_index([("company_id", 1), ("created_at", -1)])
    await db.sessions.create_index("user_id")
    await db.integrations.create_index([("company_id", 1), ("provider", 1)], unique=True)
    await db.webhook_subscriptions.create_index([("company_id", 1), ("active", 1)])
