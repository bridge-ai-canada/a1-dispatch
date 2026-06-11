# Privacy Policy — A1 Field Pro

**Last updated:** [DATE]
**Effective:** [DATE]
**Operator:** A1 Field Pro, Inc. ("A1 Field Pro", "we", "us", "our")
**Contact:** privacy@a1fieldpro.com

---

## 1. What this policy covers

This Privacy Policy describes how A1 Field Pro collects, uses, and shares
personal information when you use our web application, mobile app
(Android / iOS), browser extensions, APIs, and other services
(collectively, the "Service").

A1 Field Pro is a **multi-tenant SaaS** platform. When a field-service
business ("Tenant") subscribes to A1 Field Pro, that Tenant becomes the
**data controller** for their customer data; A1 Field Pro acts as a
**data processor**. End customers of a Tenant should contact that
Tenant directly with privacy questions about their own data.

---

## 2. Information we collect

### 2.1 From Tenant users (operators, technicians, dispatchers)
- Account information: name, email, phone, role, profile photo
- Authentication credentials (hashed bcrypt; never stored plaintext)
- Multi-factor authentication secrets (encrypted)
- Device + browser metadata (IP, user agent, OS)
- Usage telemetry (pages viewed, features used)
- Geolocation (only when location is required for routing / dispatch
  and only with your explicit permission)
- Photos captured for job documentation (uploaded to S3-backed storage)

### 2.2 From Tenant customers (end consumers of services)
- Name, address, phone, email
- Job history, invoice history, financing application data
- Soft-credit application data (submitted to and processed by our
  financing partner; we receive only decisioning metadata)

### 2.3 From integrations you connect
- OAuth tokens for connected services (Google, Microsoft, Zoom,
  QuickBooks). Tokens are encrypted at rest (AES-128 via Fernet)
  and may be revoked at any time from Integrations → Disconnect.

### 2.4 Cookies & similar technologies
- Strictly necessary session cookies (httpOnly, Secure, SameSite=None)
- Analytics cookies (only if enabled by Tenant)

---

## 3. How we use information

- Provide the Service
- Process payments (via Stripe, Helcim — we never see raw card numbers)
- Send transactional emails (account, billing, password reset)
- Send SMS (only to your customers if you initiate it; Twilio is processor)
- Show job locations on maps (Mapbox / Google Maps)
- Improve performance + diagnose bugs (anonymized telemetry)
- Detect & prevent abuse
- Comply with legal obligations

We do NOT:
- Sell your data
- Use your data to train AI models without explicit opt-in
- Profile end-consumers for advertising

---

## 4. Who we share with

| Recipient | Purpose | Data shared |
|---|---|---|
| AWS | Hosting | All Service data, encrypted |
| MongoDB Atlas | Database | All Service data, encrypted |
| Stripe | Payment processing | Customer email, payment intent |
| Helcim | Alternative payment processing | Optional, Tenant choice |
| Twilio | SMS delivery | Phone numbers, message body |
| Resend | Transactional email | Email addresses, message body |
| Mapbox / Google Maps | Geocoding | Street addresses |
| Sentry | Error tracking | Stack traces; no PII in payloads |
| Wisetack / financing partner | Soft-credit application | Customer name, email, phone, amount |
| Google / Apple | App distribution + push | Device push tokens |

We have signed Data Processing Agreements with each.

---

## 5. International transfers

A1 Field Pro hosts data in **AWS us-east-1**. If you are outside the
United States, your data is transferred to the U.S. for processing,
under appropriate safeguards (Standard Contractual Clauses).

---

## 6. Data retention

- **Active accounts**: data is retained while the account is active.
- **Cancelled accounts**: data is retained for 30 days, then purged.
- **Backups**: KMS-encrypted backups are kept up to 365 days, then
  deleted. Restoring an account from backup requires a written request.
- **Audit logs**: 90 days.

## 7. Your rights

Depending on your jurisdiction (GDPR, CCPA, etc.):
- Access — request a copy of your data
- Correction — request inaccurate data be fixed
- Deletion — request your data be erased
- Portability — request a machine-readable export
- Restriction / objection
- Withdraw consent at any time

For Tenant users: contact `privacy@a1fieldpro.com`.
For end customers of a Tenant: contact that Tenant directly.

We respond within 30 days.

---

## 8. Security

We implement industry-standard safeguards: TLS 1.2+ in transit,
AES-256 / KMS at rest, bcrypt password hashing, MFA for admin
roles, encrypted integration tokens, automated vulnerability
scanning (CodeQL, Trivy, gitleaks), and ongoing penetration
testing. See our public Security Policy at
`https://a1fieldpro.com/security`.

No system is 100% secure. We commit to notifying affected users
of any data breach within 72 hours of discovery.

---

## 9. Children

The Service is **not directed at children under 16**. We do not
knowingly collect personal information from children. If you
believe a child has provided us their data, contact
`privacy@a1fieldpro.com` so we can delete it.

---

## 10. Changes

We may update this policy. Material changes will be communicated
via in-app banner and email at least 30 days before taking effect.
The "Last updated" date at the top is authoritative.

---

## 11. Contact

A1 Field Pro, Inc.
[STREET ADDRESS]
[CITY, STATE, ZIP]
[COUNTRY]

Email: `privacy@a1fieldpro.com`
DPO (data protection officer): `dpo@a1fieldpro.com`

---

*This policy is intended for use with A1 Field Pro. It is not legal advice;
please have it reviewed by counsel in your jurisdiction before
publishing it as the authoritative privacy notice for your business.*
