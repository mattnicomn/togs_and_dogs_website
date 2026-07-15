# Google Search Console DNS Verification — usmissionhero.com

**Date:** 2026-07-15
**Status:** Pre-Apply (awaiting Matthew manual DNS entry)
**Domain:** usmissionhero.com
**Purpose:** Google Search Console ownership verification

---

## DNS Ownership

| Item | Value |
|------|-------|
| Authoritative DNS | AWS Route 53 |
| AWS Account | 253881689673 |
| AWS Profile | website-infra-sandbox |
| Managed by Terraform | No — manually managed via CLI/Console |
| Source repository | Not this repository (togs_and_dogs_website) |
| Existing apex TXT records | None |

## Required Action

Add a single TXT record to the Route 53 hosted zone for `usmissionhero.com`:

| Field | Value |
|-------|-------|
| Record name | *(blank — apex)* |
| Record type | TXT |
| Value | The approved Google Search Console verification value (wrapped in double quotes) |
| TTL | 300 |
| Routing policy | Simple |

## Safety

- No existing TXT records will be modified (none exist)
- No MX, SPF, DKIM, DMARC, A, AAAA, CNAME, or ACM records are affected
- No application deployment is required
- No Terraform apply is required
- The verification record should remain permanently after Google confirms ownership
- This does NOT authorize Google Play publication or Android deployment

## Verification Steps

1. Matthew adds the TXT record via Route 53 console or CLI
2. Wait 1–5 minutes for DNS propagation (TTL = 300s)
3. Confirm via: `nslookup -type=TXT usmissionhero.com`
4. Click "Verify" in Google Search Console
5. Confirm ownership verified

## What This Does NOT Authorize

- ❌ Google Play publication
- ❌ Android app deployment
- ❌ Application code deployment
- ❌ Terraform apply in any account
- ❌ Cognito, Stripe, Google Calendar changes
- ❌ Production data modifications
- ❌ Second-tenant creation
- ❌ Mobile distribution changes
