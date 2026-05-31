"""0003 — Rename legacy subscription plan keys to new pricing taxonomy.

Old → New mapping:
- starter → basic     ($120 → $49 / 3 seats → 1 seat)
- lite    → team      ($220 → $149 / 6 seats → 5 seats)
- pro     → business  ($360 → $299 / 10 seats → 15 seats)
- enterprise → enterprise (unchanged key, custom pricing now)
- (new)   → pro       ($499 / 50 seats)

This migration ONLY normalizes the plan KEY so existing tenants keep working
under the renamed tiers. The customer-facing price update is automatic via
the new PLANS catalog in whitelabel_service.py.
"""


async def up(db) -> None:
    # Map legacy plan keys to new ones
    mapping = {"starter": "basic", "lite": "team", "pro": "business"}
    for old, new in mapping.items():
        await db.companies.update_many(
            {"subscription.plan": old},
            {"$set": {"subscription.plan": new, "subscription.migrated_from": old}},
        )

    # Catch-all: any company without subscription.plan gets default 'basic'
    await db.companies.update_many(
        {"subscription.plan": {"$exists": False}},
        {"$set": {"subscription": {"plan": "basic", "status": "active"}}},
    )
