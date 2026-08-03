# Settlement Portfolio Intelligence Agent
## Cursor Implementation Guide

> Source: Design document provided by the user.

## 1. Purpose
The platform is an AI-assisted decision support system for settlement portfolio management. The AI explains and orchestrates optimized decisions but **does not make business decisions**. Human users remain responsible for approvals.

---

# Architecture

1. Borrower Data Collection
2. Predictive Models (PoAPP, PoA, PoF)
3. Expected Value Calculation
4. MILP Optimization
5. Offer Generation
6. AI Conversational Interface

## Core Principles

- AI explains recommendations.
- Optimization engine produces recommendations.
- Humans approve exceptions.
- Full explainability is required.
- Natural-language interface available platform-wide.

# User Roles

## 1. Collection Analyst
Purpose:
- Search borrowers
- Review customer information
- Generate settlement offers
- Compare scenarios
- Submit exceptional cases

Primary View:
Collection Workspace

---

## 2. Operational Manager

Purpose:
- Review escalations
- Validate AI recommendations
- Approve/reject exceptions
- Monitor SLA and approvals

Primary View:
Approvals & Exceptions Dashboard

KPIs:
- Approval rate
- Escalation volume
- SLA compliance
- Resolution time
- Policy exceptions

---

## 3. Executive

Purpose:
Strategic monitoring.

KPIs:
- Recovery rate
- Automation rate
- Operational cost
- Portfolio exposure
- Forecasting
- Risk distribution

Primary View:
Executive Dashboard

---

## 4. AI Agent

Responsibilities:
- Tool orchestration
- Explainability
- Scenario simulation
- Missing-data detection
- Recommendation explanation

Never:
- Make final business decisions.

# Main Views

## View 1 – Collection Workspace

Features:
- Borrower Search
- Customer Profile
- Current Debt
- Payment History
- AI Chat
- Recommended Offer
- Alternative Offers
- Explanation Panel
- Submit for Approval

---

## View 2 – Settlement Optimization

Features:
- Offer Grid
- Expected Value
- Probability Chain
- Optimization Constraints
- Best Recommendation
- Scenario Comparison

Uses:
- PoAPP
- PoA
- PoF
- Expected Value
- MILP

---

## View 3 – Portfolio Monitoring

Widgets:
- Portfolio KPIs
- Recovery Trend
- Risk Heatmap
- Alerts
- Forecast
- AI Insights

---

## View 4 – Approvals & Exceptions

Features:
- Pending Approvals
- Escalated Cases
- AI Recommendation
- Risk Score
- Policy Validation
- Approve
- Reject
- Audit Trail

---

## View 5 – Executive Dashboard

Widgets:
- Recovery Trend
- Automation Ratio
- Portfolio Exposure
- Revenue Impact
- Risk Segmentation
- Workflow Bottlenecks
- Policy Effectiveness
- Forecasted Recoveries

---

## View 6 – AI Assistant

Available globally.

Capabilities:
- Portfolio Questions
- Settlement Recommendations
- Scenario Simulation
- Explainability
- Business Insights

# Navigation

Dashboard
├── Collection Workspace
├── Settlement Optimization
├── Portfolio Monitoring
├── Approvals & Exceptions
├── Executive Dashboard
└── AI Assistant

# End-to-End Workflow

Borrower
→ AI Analysis
→ Optimization
→ Recommendation
→ Rule Validation

If compliant:
→ Execute

If exception:
→ Manager Approval

→ Portfolio Monitoring

→ Executive Reporting

# Cursor Development Notes

- Keep AI separated from optimization engine.
- Human approval is mandatory for exception paths.
- Every recommendation must be explainable.
- Every dashboard should expose role-specific KPIs.
- Chat should invoke backend tools instead of answering from memory.
- Modular architecture:
  - Frontend
  - AI Orchestrator
  - Optimization Engine
  - Predictive Models
  - Rule Engine
  - Knowledge Base
  - Monitoring
  - Audit & Logging

This document is derived from the supplied design document and is intended as a Cursor implementation guide.
