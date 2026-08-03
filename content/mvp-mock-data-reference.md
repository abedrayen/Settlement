# MVP Mock Data Reference

Schema-faithful synthetic seed generated from `Quant_data_layout_08062026.xlsx` field layout (Excel has no data rows).

Production-like portfolio: every customer has a **legal name** and **customer code**. No hardcoded hero borrower or fixed edge-case IDs.

## Identity

| Field | Example |
|-------|---------|
| Legal name | `James Smith` (individuals) / `Northbridge Trading Ltd` (corporate) |
| CustomerCode | `243445` – `243544` |
| SettlementCode | `880012` – `880111` |

## Scale

| Entity | Count / Range |
|--------|----------------|
| Customers | 100 |
| Accounts | ~150 (1–2 per customer) |
| Applications | ~60 |
| Offer grid | 9 rows per customer (RR 20/40/60% × inst 1/2/3) |
| Payments | 6 months per customer |
| Activities | 3–5 per customer |
| Portfolio KPI months | 202601–202606 (All + segments) |
| Frontier strategies | 10 points |
| Monitoring | PoAPP / PoA / PoF metrics |

## Natural portfolio flags

Sparse, production-like incidence (not pinned to specific codes):

- Deceased (~2% of individuals)
- Legal entities on Corporate segment
- Financial hardship on half of Vulnerable segment
- Occasional OOD flag

## EV Formula

`EV = PoAPP × PoA × PoF × (Balance × RR)`

Implemented in `backend/app/services/scoring.py` and used by both `seed_db.py` and the simulated ModelScorer so seed and on-demand scores stay aligned.

Validated by `backend/scripts/validate_hero.py`.

Optimal offer at runtime is selected by **PuLP MILP** over the 9-cell grid (seed still stores a max-EV recommended row for baselines).

## Reseed

```bash
python scripts/seed_db.py --force
```

## Policy Documents (RAG)

Located in `content/docs/`:

- recovery-rate-policy.md
- deceased-borrower-policy.md
- corporate-collections-policy.md
- poa-model-card.md
- vulnerability-policy.md
