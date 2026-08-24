# Fintech Automated KYC & Fraud Risk Detection Engine

A portfolio-grade analytics backend for automated KYC document screening, fraud-risk routing, and merchant onboarding insights. The system accepts PAN/Aadhaar/GSTIN document images, derives a tamper-risk score, routes each verification into an operational risk tier, and logs every decision to PostgreSQL for SQL-driven analysis.

> **Scope note:** This repository demonstrates engineering and analytics patterns for fintech KYC. It is not an official PhonePe system and must not be used as a substitute for regulated KYC, identity verification, or fraud-review controls.

## Why this project

The project extends document-tampering detection into an analytics engine that answers three business questions:

1. **Can we detect risky uploads?** Image-forensic scoring produces a `tamper_score` and authentic confidence.
2. **What intervention should happen next?** A deterministic risk policy routes low-risk cases to auto-approval, medium-risk cases to manual review, and high-risk cases to block/escalation.
3. **What is happening across the business?** PostgreSQL captures verification events for pass-rate, cohort, latency, merchant-risk, and anomaly analysis.

## Architecture

```text
KYC image upload
      |
      v
Flask API (`app.py`)
      |
      +--> document validation (PAN / Aadhaar / GSTIN)
      |
      +--> tamper scoring (`detector.py`)
      |
      +--> risk segmentation (`risk.py`)
      |       Low    -> AUTO_APPROVE
      |       Medium -> MANUAL_REVIEW
      |       High   -> BLOCK_AND_ESCALATE
      |
      v
PostgreSQL (`schema.sql`)
      |
      v
Business analytics (`analytics.sql`)
  - fraud spikes with LAG + DENSE_RANK
  - median / p95 latency
  - cohort pass rates
  - merchant risk segmentation
```

## Risk policy

The source brief leaves an uncovered 80-90% authentic-confidence band. This implementation closes that gap so every request has exactly one route:

| Risk tier | Rule | Operational intervention |
|---|---|---|
| Low | authentic confidence >= 90% and tamper score < 20% | `AUTO_APPROVE` |
| Medium | authentic confidence >= 60% and not High | `MANUAL_REVIEW` |
| High | authentic confidence < 60% **or** tamper score >= 40% | `BLOCK_AND_ESCALATE` |

The separation between authentic confidence and tamper probability makes the policy explicit and testable instead of hiding ambiguous thresholds in UI logic.

## SQL data model

`schema.sql` creates normalized onboarding entities plus the required verification event table:

- `users` — KYC subject / user dimension.
- `merchants` — merchant dimension including segment, city and onboarding cohort.
- `verifications` — one row per scan with `verification_id`, `user_id`, `merchant_id`, `document_type`, `tamper_score`, `flagged_status`, `processing_time_ms`, `timestamp`, and `ip_address`, plus risk/intervention fields used operationally.
- `fraud_escalations` — audit table for high-risk cases.

Indexes support time-series, merchant, status, document-type and risk-tier analytics.

## Business analytics

`analytics.sql` contains PostgreSQL queries that demonstrate:

- **Fraud trend analysis:** hourly merchant/location suspicious-upload rates, `LAG` deltas, and `DENSE_RANK` spike ranking.
- **Operational latency:** median and p95 processing time with `percentile_cont` across document types.
- **Retention/pass rates:** onboarding-cohort approval rates and repeat-verification activity.
- **Risk segmentation:** merchant-level tamper rates, z-score style statistical segmentation, and recommended operational interventions.

## Run locally

### 1. Start PostgreSQL

```bash
docker compose up -d db
```

### 2. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

### 4. Create the schema

```bash
psql "$DATABASE_URL" -f schema.sql
```

### 5. Run the API

```bash
python app.py
```

Health check:

```bash
curl http://localhost:5000/health
```

Example verification:

```bash
curl -X POST http://localhost:5000/api/v1/verifications \
  -F "document=@sample.png" \
  -F "user_id=USER-001" \
  -F "merchant_id=MERCHANT-001" \
  -F "document_type=PAN"
```

## API response

```json
{
  "verification_id": "0f1...",
  "document_type": "PAN",
  "tamper_score": 18.7,
  "authentic_confidence": 81.3,
  "flagged_status": "Authentic",
  "risk_tier": "Medium",
  "intervention": "MANUAL_REVIEW",
  "processing_time_ms": 142
}
```

## Project structure

```text
.
├── app.py                 # Flask routes + orchestration + SQL logging
├── database.py            # PostgreSQL connection and persistence layer
├── detector.py            # Lightweight image-forensic scorer
├── risk.py                # Statistical risk tier + intervention policy
├── schema.sql             # Relational KYC/merchant schema
├── analytics.sql          # CTEs, windows, percentiles, cohorts, segmentation
├── seed.sql               # Small synthetic merchant/user dataset
├── tests/
│   └── test_risk.py       # Boundary tests for operational risk routing
├── requirements.txt
├── .env.example
└── docker-compose.yml
```

## Model integration

`detector.py` is deliberately lightweight so the repository runs without shipping large model weights. Its `DocumentTamperDetector.score()` interface is the seam for a trained ViT/CLIP/LoRA detector. A production implementation should calibrate model probabilities on held-out data, measure false-positive/false-negative tradeoffs by document type, and version every scoring policy.

## Business impact metrics to track

- Auto-approval rate and manual-review rate.
- Suspicious/high-risk rate by merchant, city, segment and document type.
- Median and p95 processing latency.
- Cohort pass rate and repeat-verification rate.
- Fraud escalations per 1,000 verifications.
- Manual-review savings from safe low-risk auto-approval.

## Interview-ready talking points

- **SQL & data modeling:** normalized dimensions, event fact table, indexes, CTEs, windows, percentile analytics, cohort metrics.
- **Quantitative reasoning:** threshold-based segmentation, merchant z-score segmentation, latency distributions, anomaly deltas.
- **Business intervention design:** each risk band maps to a concrete action and measurable operational outcome.
- **Engineering tradeoff:** the scoring layer is swappable; the analytics contract and decision audit remain stable even as the model evolves.

## Limitations

- The bundled scorer is a heuristic baseline, not a regulated KYC decision model.
- No real identity data or sensitive KYC documents are included.
- Risk thresholds are demonstrative and require calibration before any real deployment.
- IP addresses are modeled for analytics/audit but should be governed by retention, access-control, and privacy policies in production.

## License

For educational and portfolio use.