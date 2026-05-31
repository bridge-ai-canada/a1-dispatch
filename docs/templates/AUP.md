# Acceptable Use Policy — A1 Field Pro

**Version:** 1.0  **Effective:** [DATE]  **Owner:** [Founder name]

## 1. Purpose
This Acceptable Use Policy ("AUP") governs how employees, contractors,
and authorized third parties may use A1 Field Pro systems, data, and
customer information.

## 2. Scope
Applies to anyone with access to:
- Production AWS account or any subset of resources
- MongoDB Atlas (production cluster or staging)
- GitHub repositories (private)
- Customer data in any form (laptop downloads, exports, screenshots)

## 3. Acceptable use
You **may**:
- Use systems for activities directly related to your role
- Access customer data only when required for support or bug triage
- Install software from approved sources (yarn, pip, official OS packages)
- Use VPN when accessing production from public networks

## 4. Prohibited use
You **may not**:
- Share access credentials with anyone, ever (including teammates)
- Use personal devices for production access without MDM enrollment
- Download bulk customer data to local machines without written approval
- Run penetration / load tests against production without scheduling
- Install unapproved software on company-issued laptops
- Mine cryptocurrency or run unrelated workloads on company infrastructure
- Bypass logging, monitoring, or audit controls

## 5. Authentication
- Every production-access account must enable MFA (TOTP or hardware key)
- Passwords must be ≥ 12 chars and managed via 1Password / Bitwarden
- Shared secrets are never exchanged via email, Slack, or SMS — use
  the team password manager's secure-share feature.

## 6. Data handling
- Customer PII may not be copied to personal cloud storage (Dropbox,
  personal Google Drive, etc.)
- Screenshots containing customer data must be deleted within 24 h
- Production database dumps must remain in AWS S3 (KMS-encrypted)
- Logs containing customer data are retained for 30 days then purged

## 7. Reporting
Report security incidents within **30 minutes** to:
- Slack: `#sec-incidents`
- Email: `security@a1fieldpro.com`
- PagerDuty: file P0 incident

## 8. Consequences
Violations may result in:
- Verbal warning (minor first offense)
- Written warning + retraining (repeat or moderate)
- Access revocation + termination (severe or willful)

## 9. Annual acknowledgment
Each person with production access must re-acknowledge this AUP every
12 months. Tracked via Vanta / Drata.

---

## Acknowledgment

I have read and agree to abide by this AUP.

| Name | Role | Signature | Date |
|---|---|---|---|
| | | | |
