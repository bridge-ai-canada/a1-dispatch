# SOC2 Auditor Engagement Kit

This kit gives you everything you need to engage a SOC2 auditor and hit a
Type I attestation in **8–12 weeks**, followed by a Type II observation
period of **3–6 months**.

---

## 1. Pick an auditor (1 week)

The four most common SOC2 firms for SaaS companies at your stage. Get
quotes from at least two before signing.

| Firm | Best for | Type I quote (typical) | Notes |
|---|---|---|---|
| **A-LIGN** | Largest SaaS roster, fast turnaround | $15–25 k | Strongest if you also want HIPAA later. www.a-lign.com |
| **Schellman** | High-rigor, used by enterprise buyers | $20–35 k | Pricier but the most credible report for enterprise sales. www.schellman.com |
| **Prescient Assurance** | Startups + mid-market | $10–18 k | Fast, lighter-touch. www.prescientassurance.com |
| **Sensiba** | West Coast / SF/LA SaaS | $12–22 k | Friendly to early-stage companies. www.sensiba.com |

**Compliance-automation platforms** (you'll likely need one alongside the
auditor — they manage evidence collection):

| Platform | Price | Best for |
|---|---|---|
| **Vanta** | $9–18 k/yr | Most popular, deep AWS integrations |
| **Drata** | $7.5–15 k/yr | Slightly cheaper, growing fast |
| **Secureframe** | $7–14 k/yr | Good middle ground |
| **Tugboat Logic / OneTrust** | $5–10 k/yr | DIY-friendly, lighter UI |

> **Recommended for A1 Field Pro**: Vanta (compliance automation) + A-LIGN
> (audit). Combined ≈ $25–40 k for Type I year-one. Cheaper alternative:
> Drata + Prescient ≈ $18–28 k.

---

## 2. Kickoff email — copy & send

Send to `info@a-lign.com` (or equivalent) **after** you've reviewed
`docs/SOC2_CHECKLIST.md` so you can answer their first call confidently.

```
Subject: SOC2 Type I Audit Inquiry — A1 Field Pro (SaaS, ~5 person team)

Hi team,

I'm the founder of A1 Field Pro, a multi-tenant SaaS platform for field
service businesses (jobs, dispatch, invoicing, financing, integrations
with QuickBooks/Stripe/Twilio/etc.). We process customer PII and
financial data on behalf of our tenants.

We're targeting our first SOC2 Type I attestation in the next ~12 weeks
and a Type II observation window starting immediately after.

Quick context to scope a proposal:
  • Stack: AWS (ECS Fargate + ALB + Secrets Manager), MongoDB Atlas,
    React frontend served via CloudFront + ALB. All TLS 1.2+, MFA-enforced
    for admin access, encryption at rest via AWS KMS.
  • Team size: 5 (1 founder, 2 engineers, 1 designer, 1 CS).
  • Production launch: planned for [DATE].
  • Existing readiness work: internal SOC2 gap analysis, threat model,
    runbook, security policy, automated security workflows (CodeQL,
    Trivy, gitleaks) — happy to share these artifacts under NDA.

What we'd like from you:
  1. Type I scoped to CC1–CC9 + Availability + Confidentiality + Privacy.
  2. Estimated effort, fee, and timeline.
  3. Whether you partner with Vanta / Drata / Secureframe, and if so
     which integration you find best-supported.
  4. References from 2–3 SaaS companies similar to ours (multi-tenant,
     payments-adjacent, US-based, <50 employees).

Available for a 30-minute discovery call any time this week.

Best,
[Your name]
[Title]
[Phone]
```

---

## 3. What to send the auditor in the discovery call

Have these ready in a single shared Drive folder named
**A1 Field Pro — SOC2 Readiness Pack v1.0**:

| Document | Where it lives in the repo |
|---|---|
| Security policy | `docs/SECURITY.md` |
| SOC2 control matrix (status per control) | `docs/SOC2_CHECKLIST.md` |
| Architecture diagram | `docs/DEPLOYMENT.md` § Architecture |
| Runbook & incident response | `docs/RUNBOOK.md` |
| Threat model | `docs/SECURITY.md` § Threat model |
| CI/CD pipelines | `.github/workflows/{ci,security,deploy,backup}.yml` |
| Infrastructure-as-code | `infrastructure/terraform/` |
| Backup + restore procedure | `scripts/backup_mongo.sh`, `scripts/restore_mongo.sh` |
| Org chart | (to be created — see § 4) |
| Acceptable use policy | (to be created — see § 4) |
| Access review process | (to be created — see § 4) |
| Vendor inventory | (to be created — see § 4) |

---

## 4. Gap items you must close BEFORE the audit starts

From `docs/SOC2_CHECKLIST.md`, these are the 🔴 items I cannot generate
for you — they require organizational decisions:

| Gap | Owner | Action |
|---|---|---|
| Background checks for prod-access staff | HR / founder | Use Checkr ($30 per check) before granting prod IAM |
| Acceptable Use Policy | Founder | Use Vanta's template OR `docs/templates/AUP.md` (see below) |
| Annual security training | Founder | Use KnowBe4 (~$15/seat/yr) — assign within 30 days of hire |
| Background-check process documented | HR | 1-page SOP |
| Annual risk register | Founder | Vanta auto-generates this; review quarterly |
| Vendor risk reviews (Atlas, Stripe, Twilio, etc.) | Founder | Vanta tracks; renew yearly with each vendor's SOC2 report |
| Insurance (cyber liability) | Founder | Get quote from Coalition or At-Bay (~$2–5 k/yr at this scale) |
| Quarterly access reviews | Engineering | 30-min review every quarter — Vanta automates |
| SLA commitments (99.9% uptime) | Founder | Publish on status page + add to MSA |
| Customer marketing consent opt-in | Engineering | Add checkbox to booking widget (1 PR) |
| S3 lifecycle for backups (Glacier > 30d) | DevOps | Add to Terraform (`aws_s3_bucket_lifecycle_configuration`) |

---

## 5. Timeline expectation

```
Week 1   ── Sign auditor + compliance-automation platform
Week 2-3 ── Close all 🔴 gap items from §4
Week 4-5 ── Auditor walkthrough + evidence collection
Week 6-8 ── Auditor fieldwork + report drafting
Week 9   ── Type I report issued ✅
Week 10  ── Type II observation period begins (3-6 months)
Month 7  ── Type II audit fieldwork
Month 9  ── Type II report issued ✅ (publish to customers)
```

---

## 6. Cost summary (year one)

| Item | Cost |
|---|---|
| Compliance-automation platform (Vanta) | $9-18 k |
| Type I audit (A-LIGN) | $15-25 k |
| Type II audit (same auditor, year-one) | $15-30 k |
| Background checks (5 people) | $150 |
| Security training (KnowBe4, 5 seats) | $75 |
| Cyber liability insurance | $2-5 k |
| Penetration test (annual, required for Type II) | $8-15 k |
| **Total Year 1** | **$50-95 k** |

After year one, recurring cost drops to roughly $30-50 k/yr (audit renewal,
platform, training, insurance).

---

## 7. What to publish on your site after Type I

```html
<!-- Add to footer of marketing site -->
<a href="/security" class="text-xs">
  🛡 SOC 2 Type I attested · Report available under NDA
</a>
```

And a public `/security` page summarizing controls (DO NOT publish the
full report — it's NDA-only).

---

## 8. Common auditor questions you'll be asked

Be ready with these in the first call:

1. **"How many production access IAM roles do you have, and who's in each?"** —
   Have the list from AWS IAM ready.
2. **"How do you onboard / offboard employees?"** — Write a 1-page SOP.
3. **"What's your incident response time SLA?"** — Document in
   `docs/RUNBOOK.md` (currently P0 = 15 min triage, P1 = 1 hr).
4. **"Do you store PHI / PCI data?"** — No PHI; PCI is delegated to Stripe
   (we never touch raw card numbers).
5. **"What's your tenant-isolation strategy?"** — Logical isolation via
   `company_id` scoping enforced at every router. Show them
   `docs/SECURITY.md` § Threat Model.
6. **"How do you test for it?"** — Run them through
   `tests/test_iteration_26_integrations.py` — tenant-isolation tests.
7. **"How do you handle customer data deletion (GDPR)?"** —
   `DELETE /api/super/tenants/{id}?purge=true` with 30-day retention.

---

Good luck. Once Type I is in hand, enterprise sales cycles drop by ~30%
because security questionnaires get answered with the report instead of
a 200-question RFI.
