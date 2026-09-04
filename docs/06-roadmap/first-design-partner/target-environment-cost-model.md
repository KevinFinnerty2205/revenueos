# Target-environment cost model

- **Pricing checked:** 2 September 2026
- **Currency:** provider prices are USD before GST/tax; indicative AUD uses a conservative planning conversion of **USD 1 = AUD 1.50**, not a quoted exchange rate
- **Status:** estimate only; no card, purchase, account or plan is authorised

The owner should approve one **all-in platform cap** covering infrastructure and
Clerk, and a separate OpenAI cap. Do not treat a free tier, quota or provider alert as
a hard financial stop.

## Expected monthly cost

| Cost | Primary: AWS-SYD-PRIVATE-BETA-V1 | Alternative: FLY-SUPABASE-SYD-V1 |
| --- | ---: | ---: |
| App compute | Lightsail 4 GB IPv4 Linux instance: **USD 44** | Three small Sydney Fly Machines: **USD 20–35 estimate** |
| Database | Lightsail encrypted 2 GB Standard PostgreSQL: **USD 30** | Supabase Pro Micro project: **USD 25** including USD 10 compute credit |
| Private active storage | S3 Sydney: **about USD 0–1** at tiny-beta volume | Included to 100 GB in Supabase Pro |
| Portable backup storage | S3 Sydney: **about USD 0–1** plus requests | Separate S3 Sydney: **about USD 0–1** plus requests |
| DNS, metrics, logs, alarms, health | Route 53/CloudWatch/SNS estimate: **USD 3–7** | Fly/Supabase base telemetry plus small alert route: **USD 5–10 estimate**; a Supabase log drain alone is USD 60 and is not recommended |
| **Infrastructure subtotal** | **USD 78–83 / AUD 117–125** | **USD 50–71 / AUD 75–107** |
| Clerk identity | Recommended Pro: **USD 20/month billed annually**; month-to-month price must be rechecked | Same |
| **Expected platform total before OpenAI** | **USD 98–103 / AUD 147–155** plus tax | **USD 70–91 / AUD 105–137** plus tax |
| Owner planning cap recommendation | **AUD 200/month** | **AUD 180/month** |

The primary is not the lowest possible sticker price. It is recommended because the
app, database, private files, backup, logs and alarms remain with one infrastructure
supplier in Sydney. The alternative has less host administration but three
infrastructure suppliers once the independent backup is counted.

## What is fixed and what can vary

### Primary

- **Fixed:** USD 44 Lightsail app instance and USD 30 encrypted Standard database.
- **Free-tier limitations:** do not budget against an AWS introductory trial or
  credit. The 4 GB host, encrypted managed database, S3, logs and DNS are ongoing
  billable resources when any temporary offer ends.
- **Variable:** S3 bytes/requests/retrieval, CloudWatch log ingestion/storage,
  DNS/health checks, notifications, data-transfer overage, snapshots and tax.
- **Backup:** automatic database point-in-time recovery for seven days is included.
  Manual Lightsail snapshots are USD 0.05/GB-month. RevenueOS portable backups in S3
  are storage/request priced and should age out after 14 days.
- **Storage:** AWS currently lists S3 Standard storage in Sydney at USD 0.025/GB-month
  before request/transfer charges. Ten GB of active plus backup objects is therefore
  only about USD 0.25 for storage itself.
- **Database:** the USD 15/1 GB Lightsail database says **no data encryption** and is
  unsuitable. The minimum recommended encrypted plan is USD 30/2 GB. High
  Availability is USD 60, an optional later increase of USD 30.
- **Credit card:** AWS requires a payment method to create billable resources.
- **Operational complexity:** low-to-moderate. AWS manages PostgreSQL; the operator
  patches and monitors one Linux/container host.

### Alternative

- **Fixed:** Supabase Pro is USD 25/month. Fly Machines are metered per second but are
  effectively monthly fixed while continuously running.
- **Variable:** Fly machine size/runtime, IP and egress; Supabase overages; S3
  backup; alerting; tax.
- **Free-tier limitations:** Supabase Free pauses after one week of inactivity, has
  500 MB database/1 GB file storage and is not the production target. Fly's trial is
  not a permanent production allowance. A production design partner must not depend
  on either.
- **Backup:** Supabase Pro includes daily backups retained seven days, not the
  recommended 14. A daily encrypted portable backup to S3 remains required.
- **Storage/database:** Pro includes 8 GB database disk, 100 GB files and 250 GB
  egress; overages are usage-priced. The included Micro compute is 1 GB RAM.
- **Credit card:** expect payment methods for Fly, Supabase Pro and AWS backup.
- **Operational complexity:** moderate. No app-host patching, but deployment,
  monitoring, support and incident evidence cross three suppliers.

## Clerk cost and free-tier decision

Clerk Hobby is currently free with no credit card, 50,000 monthly retained users,
100 organisations, up to 20 members per organisation, invitations and one-day
application logs. That is numerically enough for 1–5 partners, but Pro is recommended
because it adds MFA, a custom session lifetime and seven-day logs. Clerk advertises
Pro at USD 20/month when billed annually; annual billing means an upfront commitment
that requires explicit owner approval. Recheck the non-annual price before setup.

## OpenAI is separate

OpenAI is variable and excluded from the platform totals. The
[OpenAI decision](first-partner-openai-decision.md) recommends an initial **AUD
50/month alert-and-stop amount**, not automatic extra spend. If OpenAI is not
approved, use `NATIVE-NO-EXTERNAL-AI-V1` and OpenAI cost is zero.

## Spend controls required before setup

1. Record the selected architecture and maximum approved **AUD monthly platform
   spend**, including Clerk and tax treatment.
2. Record whether annual Clerk Pro billing is authorised; otherwise stop and present
   the exact current month-to-month price or use Hobby only after accepting its
   security/log limitations.
3. Configure provider budgets/alerts wherever available and daily internal review,
   but use RevenueOS flags and worker stop as the actual emergency cost control.
4. Require owner approval before a larger instance, High Availability database,
   longer logs/backups, paid log drain, extra project, premium support or over-cap
   usage.
5. Review actual cost weekly during the first month and keep a content-free record.

## Official pricing sources

- [Amazon Lightsail pricing](https://aws.amazon.com/lightsail/pricing/)
- [Fly.io resource pricing](https://fly.io/docs/about/pricing/)
- [Supabase pricing and included limits](https://supabase.com/pricing)
- [Clerk pricing](https://clerk.com/pricing)

Provider pricing can change. The setup work must capture a dated read-only quote and
stop if it exceeds the approved cap; it must not silently resize or substitute a
service.
