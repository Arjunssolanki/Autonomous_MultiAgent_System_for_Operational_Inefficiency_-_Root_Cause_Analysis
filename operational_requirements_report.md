# System Architecture & Business Requirements Document (BRD/TRD)

**Document Reference:** BRD-OPS-2023-1024  
**Project Title:** Personal Loan Disbursement Pipeline Optimization & System Resilience  
**Author:** Lead Business Systems Analyst  
**Stakeholders:** Head of Operations, Engineering Lead, Lead Product Manager, Risk & Compliance Director  
**Status:** Approved for Engineering Sizing  
**Date:** October 24, 2023  

---

## Executive Overview

An operational inquiry into the instant personal loan disbursement pipeline identified a **11.0% Month-over-Month (MoM) reduction in pipeline completion** (dropping from 88.5% to 77.5%). 

This document translates the raw data anomalies identified in the October 24 Incident Report into detailed **Root-Cause Analyses**, quantifies the resulting **Business & Operational Impact**, and specifies actionable **Business and Engineering Requirements** for immediate implementation.

---

## 1. Comprehensive Root-Cause Analysis (RCA)

```
+---------------------------------------------------------------------------------------------------+
|                                  PIPELINE ANOMALY DIAGNOSTIC                                      |
+---------------------------------------------------------------------------------------------------+
|  [Bureau Fetch Failure]   --->   [Doc Validation Timeout]   --->   [E-Sign Webhook Deadlock]     |
|   • HTTP 504 Gateway Timeouts     • 180s Rigid Session Hard-Cap    • Callback Drops / Missing   |
|   • Single Point of Failure       • High Friction for Age > 45      • Missing Active Polling    |
|   • Latency Latched at 12.8s      • 39.2% Timeout Rate Observed    • Stranded Pipeline State   |
+---------------------------------------------------------------------------------------------------+
```

### Anomaly A: Automated Credit Bureau Fetch Latency & Failures
* **Observed Metric:** Credit Bureau Fetch p95 latency spiked by **+412%** (from < 2.5s to 12.8s).
* **Technical Root Cause:** The orchestrator relies on a single synchronous HTTP REST call to the primary Credit Bureau API gateway. The system lacks execution isolation, non-blocking asynchronous processing, and secondary failover routing. 
* **System Reaction:** When the primary bureau node experiences upstream latency or drops connections, the application API gateway hits its synchronous timeout threshold, throwing an **HTTP 504 Gateway Timeout**. This causes the workflow engine to prematurely terminate the application before reaching the underwriting engine.

### Anomaly B: Document Validation Session Timeout (Demographic Friction)
* **Observed Metric:** Document validation session timeouts for applicant cohort **Age > 45** surged by **+35.0%** (rising from a baseline of 4.2% to 39.2%).
* **Technical & UX Root Cause:** The client-side application layer enforces a strict, static **180-second hard session timeout**. The UX pattern for document capture requires active file selection, camera alignment, OCR document parsing, and preview confirmation. 
* **System Reaction:** Applicants in the 45+ age demographic require more time to complete physical document scanning, address image clarity flags, or navigate file directories. The aggressive 180s timer expires while the user is actively attempting to clear upload prompts, destroying client state, purging uploaded payloads, and forcing the user back to the application start point.

### Anomaly C: Instant E-Sign Integration Handshake Drop-Off
* **Observed Metric:** E-Sign Integration success rate degraded by **-14.1%** (98.2% down to 84.1%), driving an **11.5% spike in Pre-Activation Abandonment**.
* **Technical Root Cause:** The integration architecture relies exclusively on passive, single-shot asynchronous HTTP Webhook Callbacks from the third-party E-Sign vendor. 
* **System Reaction:** If the incoming webhook payload is dropped due to transient network failure, token expiration, or high load at the receiver interface, the internal state machine remains locked at `PENDING_ESIGN`. Even though the customer successfully completes the signature on the vendor interface, the backend system fails to transition to `READY_FOR_ACTIVATION`. The customer sees an infinite loading spinner or unhandled error state, resulting in final-step abandonment.

---

## 2. Business Impact Summary

```
+---------------------------------------------------------------------------------------------------+
|                                     BUSINESS IMPACT SUMMARY                                       |
+---------------------------------------------------------------------------------------------------+
|  Financial Loss        • 11.0% decrease in overall pipeline conversion.                           |
|                        • Immediate reduction in net monthly loan origination volume.              |
+---------------------------------------------------------------------------------------------------+
|  Acquisition Waste     • High Customer Acquisition Cost (CAC) burned on users who abandon          |
|                          at the final step (14.6% pre-activation drop-off).                       |
+---------------------------------------------------------------------------------------------------+
|  Demographic Churn     • Loss of 45+ demographic segment (historically higher loan amounts and     |
|                          stronger credit profiles).                                               |
+---------------------------------------------------------------------------------------------------+
|  Support Overhead      • Spike in inbound customer service tickets and manual reconciliation       |
|                          workloads for stranded e-sign documents.                                 |
+---------------------------------------------------------------------------------------------------+
```

### 1. Financial Conversion Degradation
An 11% reduction in total pipeline completions directly diminishes total monthly loan origination volume. Assuming an average pipeline volume of 10,000 applications per month at an average loan size of $10,000, an 11% drop-off represents **1,100 unfulfilled loans per month**, equivalent to **$11,000,000 in lost gross loan origination volume** monthly.

### 2. Marketing Capital Burn & Acquisition Inefficiency
Pre-activation abandonment increased from 3.1% to 14.6%. Marketing expenditures incurred to acquire these users via paid channels (search, affiliate networks, target ads) are completely unrecovered. Capturing users through underwriting and signing only to lose them at the activation node represents maximum Customer Acquisition Cost (CAC) waste.

### 3. Customer Lifetime Value (LTV) Erosion in Key Demographics
The 45+ demographic represents a prime borrowing segment with higher average loan amounts and prime credit stability. A 39.2% failure rate during document validation selectively churns this high-value demographic, driving them to competitor platforms and skewing the portfolio toward lower-margin cohorts.

### 4. Support Ticket Inflation & Operational Expenses
Stranded e-sign states force users to contact support to confirm if their loan was approved or disbursed. This creates an unbudgeted operational workload, requiring support agents to manually verify third-party vendor dashboards, manually alter database status flags, and manually trigger disbursements.

---

## 3. Actionable Business & Technical Requirements

### Epic 1: Credit Bureau Fetch Fault Tolerance & Async Processing

#### Business Requirement
Ensure credit bureau checks never hard-fail an application due to vendor latency or transient timeouts, preserving overall conversion rates.

#### Functional Requirements
* **FR-1.1:** The system shall implement a secondary fallback Credit Bureau integration provider (Bureau B) when the primary provider (Bureau A) experiences service failures or elevated latency.
* **FR-1.2:** Bureau retrieval shall transition from a blocking synchronous call to a non-blocking asynchronous execution pattern.

#### Technical Specifications & Engineering Tasks
* **TR-1.1 (Circuit Breaker Pattern):** Implement a Resilience4j / Hystrix Circuit Breaker on the Bureau A API client. 
  * *Threshold:* Open circuit if 15% of requests over a rolling 60-second window return HTTP `5xx`, `504`, or exceed a `3000ms` response time.
* **TR-1.2 (Fallback Execution):** When the Circuit Breaker is `OPEN`, auto-route requests to the Bureau B API adapter within `< 100ms`.
* **TR-1.3 (Timeout Management):** Set strict socket read timeouts on the bureau HTTP client to `3000ms` (down from infinite/default).

```
[ Underwriting Engine ] 
         │
         ▼
  [ Circuit Breaker ]
     ├── (Normal Latency < 3s) ──────► [ Bureau A (Primary) ]
     └── (Timeout / Open Circuit) ───► [ Bureau B (Fallback) ]
```

---

### Epic 2: Adaptive Session Management & Accessible Document Validation UX

#### Business Requirement
Eliminate demographic drop-off for applicants aged 45+ by extending document upload windows and providing real-time assistance during camera capture and validation.

#### Functional Requirements
* **FR-2.1:** The Document Validation step shall dynamically manage session timeouts based on user interaction events, preventing sudden session termination during active document uploads.
* **FR-2.2:** The UI shall provide clear, high-contrast, guided tooltips explaining document requirements (e.g., clarity, framing, lighting) prior to system rejection.

#### Technical Specifications & Engineering Tasks
* **TR-2.1 (Dynamic Session Extensions):** 
  * Increase base session timeout from **180 seconds to 360 seconds**.
  * Implement an active heartbeat mechanism: Every user interaction (file select, camera open, retake, frame drag) sends an asynchronous `/api/v1/session/heartbeat` request, resetting the 360-second idle timer.
* **TR-2.2 (Client-Side Pre-Validation & Error Recovery):**
  * Implement client-side image compression and quality checks (blur detection, minimum resolution) before transmission to reduce network payload size and drop latency.
  * If OCR validation fails, display inline, accessible feedback (e.g., *"Image too blurry—please place ID on a flat surface"*), keeping the session active instead of forcing a full process restart.

---

### Epic 3: Active State Reconciliation Engine for E-Sign Completion

#### Business Requirement
Ensure 100% of completed e-sign contracts are recognized by the core banking engine, eliminating the `PENDING_ESIGN` deadlock and reducing pre-activation abandonment to `< 3.0%`.

#### Functional Requirements
* **FR-3.1:** The system shall automatically reconcile and activate loan applications upon vendor signature completion, even if the primary webhook notification fails to deliver.
* **FR-3.2:** The application UI shall actively verify completion status in the background and transition the user seamlessly to the `READY_FOR_ACTIVATION` view.

#### Technical Specifications & Engineering Tasks
* **TR-3.1 (Active Polling & Fallback Worker):**
  * Implement an asynchronous scheduled worker task (e.g., Celery / Temporal / AWS Step Functions) triggered when a user enters `PENDING_ESIGN`.
  * If no webhook response is registered within **15 seconds** of redirect back to the app, the worker shall initiate active outbound polling to the vendor's `GET /v1/signatures/{signature_id}/status` API endpoint.
  * Polling frequency: Every 10 seconds for 2 minutes, back off to every 60 seconds for up to 15 minutes.
* **TR-3.2 (Idempotent State Machine Updates):**
  * Refactor the workflow engine state handler to ensure idempotent status updates:
    ```sql
    UPDATE loan_applications 
    SET status = 'READY_FOR_ACTIVATION', updated_at = NOW() 
    WHERE id = :loan_id AND status = 'PENDING_ESIGN';
    ```
  * Ensure both Webhook Listener and Active Poller hit the same idempotent state updater, preventing double-activation calls.

```
[ Customer Completes E-Sign ]
         │
         ├─── (Primary Flow: Webhook Success) ────► [ Core Engine: READY_FOR_ACTIVATION ]
         │                                                      ▲
         └─── (Failure Flow: Webhook Dropped)                   │
                     │                                          │
                     ▼                                          │
         [ Active Poller (Every 10s) ] ── (Status: SIGNED) ─────┘
```

---

## 4. Acceptance Criteria (Engineering Verification)

The following Acceptance Criteria must pass in Staging/UAT environments prior to production release.

### Feature 1: Bureau Circuit Breaker & Failover Routing
```gherkin
Scenario: Primary Credit Bureau API responds with high latency
  Given the primary credit bureau (Bureau A) p95 latency exceeds 3000ms
  When a new loan application triggers a bureau fetch
  Then the Circuit Breaker trips to OPEN state
  And the request is automatically routed to Bureau B within 100ms
  And the pipeline execution continues without throwing an HTTP 504 error.

Scenario: Primary Credit Bureau API returns HTTP 500 error
  Given Bureau A returns three consecutive HTTP 500 responses
  When an applicant submits their details
  Then the system logs a fallback event to telemetry
  And executes the query against Bureau B
  And the user application state transitions to UNDERWRITING_COMPLETE.
```

### Feature 2: Document Validation Session Extension
```gherkin
Scenario: Applicant aged 45+ spends over 180 seconds on document upload
  Given an applicant is on the Document Validation step
  And the elapsed session time reaches 175 seconds
  When the applicant interacts with the camera input or file picker
  Then an asynchronous heartbeat call is dispatched to /api/v1/session/heartbeat
  And the session expiration clock is reset to 360 seconds
  And the applicant completes upload without experiencing a session timeout popup.
```

### Feature 3: E-Sign Webhook Failure Self-Healing
```gherkin
Scenario: Vendor webhook fails to deliver after contract signing
  Given an applicant completes signing on the vendor interface
  And the vendor webhook fails to reach the backend listener due to network drop
  When the front-end app returns to the landing view
  Then the backend Active Poller queries the vendor status API within 15 seconds
  And verifies signature status as COMPLETED
  And updates application status from PENDING_ESIGN to READY_FOR_ACTIVATION
  And triggers automated disbursement within the target SLA.
```

---

## 5. Success Metrics & Implementation KPI Roadmap

Engineering implementation will be evaluated post-deployment against the following target KPIs:

| Target Metric | Baseline (Pre-Incident) | Incident Metric | Target Outcome (Post-Fix) | SLA Tracking Window |
| :--- | :--- | :--- | :--- | :--- |
| **Pipeline Completion Rate** | 88.5% | 77.5% | **≥ 88.5%** | 14 Days Post-Release |
| **E-Sign Success Rate** | 98.2% | 84.1% | **≥ 98.5%** | Real-time / Daily |
| **Bureau Fetch Latency (p95)** | < 2.5s | 12.8s | **< 2.5s (Combined)** | Continuous Alerting |
| **Doc Validation Timeout (Age > 45)** | 4.2% | 39.2% | **< 4.0%** | Daily Cohort Tracking |
| **Pre-Activation Abandonment** | 3.1% | 14.6% | **< 3.0%** | Real-time Dashboard |

---

## 6. Implementation Timeline & RACI Matrix

### Phased Execution Schedule
* **Phase 1 (Immediate / Patch Sprint - Days 1 to 3):**
  * Extend client-side document validation session timeout to 360 seconds.
  * Increase HTTP read timeouts on Bureau gateway adapters.
* **Phase 2 (Sprint N+1 - Days 4 to 10):**
  * Deploy Circuit Breaker pattern and secondary bureau fallback routing.
  * Implement active polling background worker for E-Sign status verification.
  * Push client-side UX upload guidance and inline OCR error messaging.
* **Phase 3 (Sprint N+2 - Days 11 to 14):**
  * End-to-end integration testing, load testing, chaos testing (simulating webhook drops).
  * Dashboard setup and telemetry verification.

### RACI Matrix

| Workstream | Lead BSA | Engineering Lead | QA Lead | Head of Ops |
| :--- | :---: | :---: | :---: | :---: |
| Requirements & Acceptance Criteria | **R / A** | C | C | I |
| Circuit Breaker & Fallback Architecture | I | **R / A** | C | I |
| UX Timeout & Capture Enhancements | C | **R** | C | **A** |
| E-Sign Polling Worker Implementation | I | **R / A** | C | I |
| Operational KPI Verification | **R** | C | C | **A** |

*Key: R = Responsible, A = Accountable, C = Consulted, I = Informed*