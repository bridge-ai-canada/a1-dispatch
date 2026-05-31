"""0002 — Performance indexes for hot query paths discovered via prod traffic patterns.

Compound indexes covering:
- customer search (company + name/phone)
- invoice/estimate list views (company + status + created_at desc)
- activity log scrolling (company + created_at desc)
- webhook delivery scrolling (company + created_at desc)
- timesheets by tech & day (clock-in/out queries)
"""


async def up(db) -> None:
    # Customers: fast list + search
    await db.customers.create_index([("company_id", 1), ("name", 1)])
    await db.customers.create_index([("company_id", 1), ("phone", 1)])
    await db.customers.create_index([("company_id", 1), ("email", 1)])

    # Invoices / estimates
    await db.invoices.create_index([("company_id", 1), ("status", 1), ("created_at", -1)])
    await db.invoices.create_index([("company_id", 1), ("customer_id", 1)])
    await db.estimates.create_index([("company_id", 1), ("status", 1), ("created_at", -1)])
    await db.estimates.create_index([("company_id", 1), ("customer_id", 1)])

    # Activity scrolling
    await db.activity.create_index([("company_id", 1), ("actor_id", 1), ("created_at", -1)])

    # Webhook log
    await db.webhook_deliveries.create_index([("company_id", 1), ("status", 1), ("created_at", -1)])

    # Timesheets
    await db.timesheets.create_index([("company_id", 1), ("user_id", 1), ("started_at", -1)])

    # Jobs by assigned tech
    await db.jobs.create_index([("company_id", 1), ("assigned_to", 1), ("scheduled_at", 1)])

    # Finance applications
    await db.finance_applications.create_index([("company_id", 1), ("status", 1), ("created_at", -1)])
    await db.finance_applications.create_index([("company_id", 1), ("customer_id", 1)])
