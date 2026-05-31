# SOC2 Readiness Checklist — A1 Field Pro

> Maps each SOC2 Trust Services Criterion to a concrete implementation in this
> codebase / infra. A green ✅ means the control is in place TODAY. 🟡 means
> partial / requires customer action. 🔴 means missing — must be addressed before
> attestation.

## CC1 — Control Environment

| # | Control | Status | Implementation |
|---|---|---|---|
| 1.1 | Documented org chart & RACI | 🟡 | `docs/RUNBOOK.md` § on-call rotation; expand |
| 1.2 | Background checks for staff with prod access | 🔴 | manual HR process |
| 1.3 | Acceptable use & code of conduct | 🔴 | template needed |
| 1.4 | Annual security training | 🔴 | schedule annually |

## CC2 — Communication & Information

| 2.1 | Internal sec policies published | ✅ | `docs/SECURITY.md` |
| 2.2 | Customer-facing privacy policy | 🟡 | live on marketing site — must reflect SOC2 commitments |
| 2.3 | Incident communication template | ✅ | `docs/RUNBOOK.md` § alerts |

## CC3 — Risk Assessment

| 3.1 | Annual risk register | 🔴 | document new threat surfaces yearly |
| 3.2 | Threat model per major feature | 🟡 | `docs/SECURITY.md` threat model — keep current |
| 3.3 | Vendor risk review (Atlas, Stripe, etc.) | 🟡 | track in spreadsheet, renew yearly |

## CC4 — Monitoring Activities

| 4.1 | Continuous logging | ✅ | CloudWatch + 30-day retention |
| 4.2 | Alerts on suspicious events | ✅ | failed-login spikes via activity log + CloudWatch insights |
| 4.3 | Tamper-evident audit log | ✅ | `activity` collection; write-only via API |
| 4.4 | Annual SOC2 readiness review | 🟡 | this doc — review quarterly |

## CC5 — Control Activities

| 5.1 | Change management via PR + review | ✅ | GitHub branch protection + required CI |
| 5.2 | Separation of duties (deploy ≠ author) | 🟡 | enforce via `CODEOWNERS` + protected branch |
| 5.3 | Production access only via approved roles | ✅ | AWS SSO + role-based IAM |

## CC6 — Logical & Physical Access

| 6.1 | MFA on all admin accounts | ✅ | AWS SSO MFA required + app `mfa_enabled` for owner/super_admin |
| 6.2 | Least privilege IAM | ✅ | task roles scoped to specific Secrets/S3 keys |
| 6.3 | Encryption at rest | ✅ | Atlas KMS + S3 SSE-KMS + Fernet on integration creds |
| 6.4 | Encryption in transit | ✅ | TLS 1.2+ enforced at ALB |
| 6.5 | Secrets management (no secrets in code) | ✅ | AWS Secrets Manager; `gitleaks` in CI |
| 6.6 | Access reviews quarterly | 🟡 | document review |
| 6.7 | Physical security | ✅ | AWS handles datacenter security (SOC2-attested) |

## CC7 — System Operations

| 7.1 | Documented baseline configurations | ✅ | `infrastructure/terraform/` |
| 7.2 | Automated vulnerability scans | ✅ | `.github/workflows/security.yml` weekly |
| 7.3 | Patch management | ✅ | Dependabot + monthly base-image rebuild |
| 7.4 | Incident response playbook | ✅ | `docs/RUNBOOK.md` + `docs/SECURITY.md` § IR |
| 7.5 | Capacity monitoring | ✅ | Container Insights + ECS autoscaling |

## CC8 — Change Management

| 8.1 | Change request tracking | ✅ | GitHub PRs + linked issues |
| 8.2 | Pre-deploy testing | ✅ | CI gates (pytest, lint, image build) before merge |
| 8.3 | Rollback capability | ✅ | ECS circuit breaker + previous task definition |

## CC9 — Risk Mitigation

| 9.1 | Business continuity plan | 🟡 | RTO 1 h / RPO 24 h documented in `DEPLOYMENT.md` — drill quarterly |
| 9.2 | Insurance (cyber liability) | 🔴 | engage broker |

## Availability (A1)

| A1.1 | SLA commitments | 🟡 | publish 99.9 % monthly uptime SLA |
| A1.2 | Redundancy | ✅ | 2 AZ ECS + Atlas replica set |
| A1.3 | Backup & recovery | ✅ | nightly mongodump + restore drill |

## Confidentiality (C1)

| C1.1 | Customer data segregation | ✅ | strict `company_id` scoping; tested in iteration 26 |
| C1.2 | DLP — no sensitive data in logs | ✅ | redaction in `store.py::redact()` + activity meta cap |
| C1.3 | Secure data destruction | 🟡 | implement S3 lifecycle for old backups |

## Privacy (P1)

| P1.1 | Notice of data collection | ✅ | privacy policy linked at signup |
| P1.2 | Customer consent for marketing | 🟡 | ensure opt-in checkbox on booking widget |
| P1.3 | Right to erasure (GDPR) | ✅ | `DELETE /api/super/tenants/{id}?purge=true` |
| P1.4 | Data export (GDPR) | ✅ | existing exports router covers it |

---

## Target attestation timeline

- **Q1 2026**: implement all 🔴 items; engage SOC2 auditor
- **Q2 2026**: Type I audit (point-in-time)
- **Q3 2026 → Q1 2027**: Type II observation period (6 months)
- **Q2 2027**: Type II report published
