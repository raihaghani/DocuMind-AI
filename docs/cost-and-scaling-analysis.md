# Cost & Scaling Analysis

> **All monetary figures below are illustrative assumptions, not verified live
> vendor prices.** Cloud and AI prices change frequently and vary by region and
> contract. Treat the numbers as a **methodology and order-of-magnitude
> comparison**; confirm current prices with each vendor before budgeting.

## Deployment options compared

### Option A — Budget VPS (e.g. Hostinger / generic VPS)

A single virtual server runs the Django app (behind Gunicorn + Nginx), the
PostgreSQL database, and local disk storage for `private_uploads/`. SSL via
Let's Encrypt. Backups via a nightly cron dump to off-box storage.

| Item                     | Illustrative monthly cost |
| ------------------------ | ------------------------- |
| VPS (2 vCPU / 4–8 GB)    | $8 – $20                  |
| Managed backups / snapshots | $1 – $5                |
| Domain + SSL (Let's Encrypt free) | ~$1 (domain amortized) |
| **Infra subtotal**       | **~$10 – $26**            |

Pros: cheapest, simple mental model. Cons: single point of failure, manual
ops, vertical scaling only.

### Option B — AWS

| Item                               | Illustrative monthly cost |
| ---------------------------------- | ------------------------- |
| EC2 (t3.small/medium) or Fargate   | $15 – $45                 |
| RDS PostgreSQL (db.t3.micro/small) | $15 – $40                 |
| S3 storage + requests              | $1 – $10 (usage-based)    |
| Data transfer / networking         | $2 – $15                  |
| CloudWatch monitoring/logs         | $2 – $10                  |
| Backups (RDS snapshots, S3 versioning) | $2 – $10              |
| **Infra subtotal**                 | **~$37 – $130**           |

Pros: managed services, easy to scale, durable storage, built-in monitoring.
Cons: higher cost and operational complexity.

## AI API cost (applies to both options, only when `AI_PROVIDER=openai`)

The **mock provider costs $0** and is the default. When a real provider is
enabled, cost is driven by tokens per request:

```
tokens_per_request ≈ system_prompt + retrieved_context (TOP_K chunks)
                     + question + answer
                   ≈ 150 + (3 × ~300) + 50 + ~250  ≈ ~1,350 tokens
cost_per_request    = tokens_per_request / 1000 × price_per_1k_tokens
monthly_AI_cost     = cost_per_request × questions_per_user × active_users
```

With an **illustrative** blended rate of **$0.0005 per 1K tokens** (small/cheap
model), one request ≈ **$0.00068**.

> Retrieval directly limits AI cost: sending only the top 3 chunks (not the
> whole document) keeps `tokens_per_request` small and roughly constant
> regardless of document size.

## Illustrative usage scenarios

Assumptions shared across scenarios: average document ~1 MB; chunk/token sizes
as above; daily limit 10 questions/user.

### Scenario 1 — Small

| Assumption            | Value         |
| --------------------- | ------------- |
| Active users          | 20            |
| Questions/user/month  | 60            |
| Documents/user        | 5 (~5 MB)     |
| Total storage         | ~100 MB       |
| Monthly AI requests   | 1,200         |
| **Monthly AI cost**   | ~**$0.82**    |
| Recommended infra     | **VPS (A)**   |

### Scenario 2 — Medium

| Assumption            | Value          |
| --------------------- | -------------- |
| Active users          | 500            |
| Questions/user/month  | 100            |
| Documents/user        | 10 (~10 MB)    |
| Total storage         | ~5 GB          |
| Monthly AI requests   | 50,000         |
| **Monthly AI cost**   | ~**$34**       |
| Recommended infra     | VPS (scaled up) or small AWS |

### Scenario 3 — Larger

| Assumption            | Value          |
| --------------------- | -------------- |
| Active users          | 5,000          |
| Questions/user/month  | 150            |
| Documents/user        | 20 (~20 MB)    |
| Total storage         | ~100 GB        |
| Monthly AI requests   | 750,000        |
| **Monthly AI cost**   | ~**$510**      |
| Recommended infra     | **AWS (B)** with autoscaling + RDS + S3 |

## Cost calculation formulas

```
monthly_requests = active_users × questions_per_user_per_month
monthly_AI_cost  = monthly_requests × (tokens_per_request / 1000)
                   × price_per_1k_tokens
storage_GB       = active_users × documents_per_user × avg_document_MB / 1024
total_monthly    = infra_cost + monthly_AI_cost + storage_cost
```

## Dimensions compared

| Dimension              | VPS (A)                    | AWS (B)                         |
| ---------------------- | -------------------------- | ------------------------------- |
| Monthly infra cost     | Lowest (~$10–26)           | Higher (~$37–130+)              |
| Scalability            | Vertical (resize box)      | Horizontal + managed autoscale  |
| Operational complexity | Low setup, manual ops      | Higher, but managed services    |
| Reliability            | Single point of failure    | Multi-AZ options, managed DB    |
| Security               | You patch/secure the box   | Shared responsibility, IAM, VPC |
| Best for               | MVP / small usage          | Growth / production at scale    |

## Levers that reduce cost

- **Model choice** — a smaller model can cut AI cost by an order of magnitude.
- **Retrieval architecture** — sending only `TOP_K` chunks caps tokens per
  request regardless of document size.
- **Caching** — cache identical (document, question) answers to avoid repeat
  API calls.
- **Daily limits** — the per-user quota is a hard ceiling on worst-case spend.
- **Storage tiering** — move cold documents to cheaper storage classes.

## Recommendation

For the MVP and small deployments, **Option A (VPS)** with the **mock provider**
(or a cheap real model) keeps total cost near the infra floor (~$10–26/month).
Migrate to **Option B (AWS)** — RDS PostgreSQL, S3 for `private_uploads/`,
autoscaling app tier, CloudWatch — once reliability, horizontal scaling, and
managed backups justify the added cost and complexity (roughly the "Medium →
Larger" transition above).
