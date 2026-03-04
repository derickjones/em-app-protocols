# Department of AI Implementation and Adoption (AIA) — Intake Form Submission

**Date:** March 3, 2026
**Requestor:** Derick Jones, MD, MBA, MHI (jones.derick@mayo.edu)
**Department:** Emergency Medicine — Rochester, MN
**Product Name:** EM Protocols (emergencymedicine.app)
**Funding:** PSIF — Presidential Strategic Initiative Fund (Mayo Clinic Platform Deploy)
**Development Partner:** Cardamom Health (CAR-340074, SOW 3.1)
**Clinical Champions:** Derick Jones, MD, MBA, MHI & Jake Morey, MD, MBA
**Department Chair Support:** Jim Colletti, MD

---

## 1. PRODUCT: One-Pager / Product Details

### Product Overview

EM Protocols is a clinical decision support tool that uses Retrieval-Augmented Generation (RAG) to provide emergency medicine clinicians with instant, evidence-based answers at the bedside. It combines institutional protocols with curated open-access medical literature to deliver sub-2-second responses with inline citations, visual flowcharts, and source attribution.

The project is funded by the **Presidential Strategic Initiative Fund (PSIF)** for integration into the **Mayo Clinic Platform Deploy** program. An internal version is available for Mayo clinicians; an external version is planned for broader healthcare organizations via MCP Deploy.

### Problem Statement

When an ER physician or nurse needs to look up a protocol during an emergency, they currently navigate through clunky hospital websites, click through multiple PDFs, and manually search for the right section. **This takes too long when treating critical patients.**

### Solution

An AI-powered RAG system that:
1. **Ingests** hospital protocols (PDFs) uploaded by department admins
2. **Indexes** content using Google Vertex AI RAG Engine across 6 knowledge corpora
3. **Answers** clinician questions in plain English in under 2 seconds
4. **Shows** relevant flowcharts and clinical algorithms alongside answers
5. **Cites** exact sources with clickable links to original content

### Target Users

| User Type | Use Case |
|-----------|----------|
| Emergency Physicians | Real-time clinical decision support during all phases of patient care |
| Advanced Practice Providers | Protocol lookup and evidence-based guidance |
| Nurses | Nursing-specific protocol access and procedural guidance |
| Residents & Medical Students | Learning tool with evidence-based citations |
| ED Administrators | Upload, organize, and manage institutional protocol libraries |

### Clinical Workflow Integration

The tool is designed for use during **all steps of patient care** — from triage and initial assessment through active treatment and disposition. It is accessed as a web application at the bedside, with planned **Epic EHR integration in 2026** for embedded in-workflow access.

This is a **net-new tool** — it does not replace any existing system. It supplements existing resources like UpToDate, MDCalc, and institutional protocol websites by providing faster, AI-powered search with visual flowchart display and source citation.

### Key Differentiators

- **Speed:** Sub-2-second query responses vs. minutes navigating traditional protocol websites
- **Visual-First:** Flowcharts, algorithms, and diagrams displayed prominently alongside text answers
- **Multi-Source:** Combines institutional protocols with 6 curated open-access medical knowledge bases
- **Citations:** Every factual claim is cited with source attribution — unlike standalone LLM tools
- **Multi-Tenant:** Organization and ED-level isolation; each institution sees only their own protocols

### Intended Use Statement

EM Protocols is intended for use as a **clinical decision support tool** by licensed emergency medicine clinicians. It provides rapid access to institutional protocols and curated medical literature to assist in clinical decision-making. It is **not** intended to replace clinical judgment, serve as a standalone diagnostic tool, or provide patient-specific medical advice. All AI-generated answers are grounded in retrieved source documents with inline citations for verification. This tool does not establish a provider–patient relationship and is not intended for use by patients or the general public.

### Departmental Support & Funding

| Field | Detail |
|-------|--------|
| **Funding Source** | PSIF — Presidential Strategic Initiative Fund |
| **Deployment Program** | Mayo Clinic Platform (MCP) Deploy |
| **Development Partner** | Cardamom Health (SOW 3.1, CAR-340074) |
| **Home Department** | Emergency Department, Rochester, MN |
| **Department Chair** | Jim Colletti, MD |
| **Clinical Champions** | Derick Jones, MD, MBA, MHI & Jake Morey, MD, MBA |
| **Co-Founders** | Derick Jones (Technical Lead) & Jake Morey |
| **Pilot Site** | Mayo Clinic Rochester Emergency Department |
| **Status** | Live — active use in pilot |

### Pilot Group

The current pilot includes:
- ED Digital Health Physicians
- ED Administrators and nursing leadership
- ED administrative leaders

Domain expert user sessions are **scheduled and ongoing** to validate clinical accuracy and usability.

### Timeline

| Milestone | Date |
|-----------|------|
| Functional prototype | February 2026 |
| **Live pilot use** | **Now (March 2026)** |
| SOW 3.1 M1 — Project kickoff & scope confirmation | January 5, 2026 |
| SOW 3.1 M2 — CAF migration with new LLM architecture | March 13, 2026 |
| Domain expert validation sessions | Ongoing |
| SOW 3.1 M3 — Production go-live, training & project closure | April 30, 2026 |
| Epic EHR integration (Plummer Chart via MCP iFrame) | 2026 |
| MCP Deploy (external version) | 2026 |

### Access Model

| Version | Access Method | Audience |
|---------|--------------|----------|
| **Internal** | Web app (emergencymedicine.app) via Mayo SSO | Mayo Clinic ED staff |
| **Internal (future)** | Embedded in Epic via SMART on FHIR | Mayo Clinic ED staff |
| **External (MCP Deploy)** | Web app via MCP Deploy platform | External healthcare organizations |

### Success Metrics

| Metric | Target | Current Status |
|--------|--------|----------------|
| Query response time | < 2 seconds | ✅ Achieved |
| RAG accuracy (domain expert validated) | > 90% | In validation (user sessions ongoing) |
| Image extraction quality | > 95% | ✅ Achieved |
| Pilot organization onboarding | 10 organizations | 1 active (Mayo Clinic Rochester) |
| User satisfaction | > 4.5/5 | Pending pilot expansion |
| System uptime | > 99.9% | ✅ Cloud Run auto-scaling |

---

## 2. DATA: Data Plan & Sources

### Data Categories

The system processes two categories of data:

#### A. Institutional Protocols (Proprietary)
- **What:** Clinical protocol PDFs uploaded by authorized ED administrators
- **Source:** Each institution's own approved clinical guidelines, pathways, and algorithms
- **PHI/PII:** **None** — protocols are standardized clinical procedures, not patient records
- **Storage:** Google Cloud Storage (US regions, AES-256 encryption at rest)
- **Access:** Organization-isolated; each institution can only access their own protocols

#### B. Open-Access Medical Literature (External)
Curated from 6 publicly available, Creative Commons-licensed medical knowledge bases:

| Source | License | Content | Volume |
|--------|---------|---------|--------|
| **Local Protocols** | Proprietary (institutional) | Department-specific clinical guidelines | ~50 protocols |
| **WikEM** | CC BY-SA 3.0 | Emergency medicine topic encyclopedia | ~5,000 pages |
| **PMC Open Access** | Per-article CC (BY, BY-NC, CC0) | Peer-reviewed EM journal articles (2015–present) | ~18,000 articles |
| **LITFL** | CC BY-NC-SA 4.0 | FOAMed: EM, critical care, toxicology, ECG interpretation | ~7,892 pages |
| **REBEL EM** | CC BY-NC-ND 3.0 | Evidence-based EM reviews and clinical pearls | ~1,359 posts |
| **ALiEM** | CC BY-NC-ND 3.0 (PV Cards & MEdIC only) | Clinical reference cards and medical education cases | ~258 pages |

### Data Preparation

- **PDF Processing:** Google Document AI extracts text with layout preservation and images (flowcharts, algorithms, diagrams)
- **Chunking:** Text is chunked with context preservation and linked to associated images and page numbers
- **Indexing:** Each source is indexed into a separate Vertex AI RAG corpus for clean isolation
- **Metadata:** Title, source URL, author, license, source type stored per document

### Data Quality Assessment

- All external sources are curated, peer-reviewed or editorially managed medical resources
- Creative Commons licenses verified for each source with full compliance documentation (see `docs/SOURCE_LICENSING_SUMMARY.md`)
- robots.txt compliance verified for all scraped sources
- Rate limiting and polite crawling implemented for all scrapers

### PHI/PII Assessment

| Data Element | PHI? | PII? | Notes |
|-------------|------|------|-------|
| Clinical protocols (PDFs) | ❌ No | ❌ No | Standardized procedures, not patient records |
| External medical literature | ❌ No | ❌ No | Published open-access content |
| User accounts | ❌ No | ⚠️ Minimal | Email address and display name only |
| Query logs | ❌ No | ❌ No | Clinical topic queries, no patient identifiers |

---

## 3. MODEL: AI/ML Approach

### Architecture: Retrieval-Augmented Generation (RAG)

The system does **not** train or fine-tune any AI model. It uses a RAG architecture that retrieves relevant source documents and passes them to a pre-trained language model for answer synthesis.

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Retrieval Engine** | Google Vertex AI RAG API | Semantic search across 6 indexed corpora |
| **Answer Generation** | Google Gemini 2.0 Flash | Synthesizes answers from retrieved context only |
| **PDF Processing** | Google Document AI | OCR, text extraction, image extraction |

### Model Details

| Parameter | Value |
|-----------|-------|
| **Model** | Gemini 2.0 Flash (via Vertex AI) |
| **Type** | Pre-trained LLM (Google) — no fine-tuning |
| **Temperature** | 0.2 (low creativity, high factuality) |
| **Max Output Tokens** | 2,000 |
| **Grounding** | Strict — model instructed to ONLY use provided context, not outside knowledge |
| **Citation Requirement** | Every factual claim must have an inline citation `[N]` matching a source |

### How RAG Works (vs. Standalone LLM)

```
User Query → Vertex AI RAG retrieves top-K relevant documents from indexed corpora
           → Retrieved documents passed as context to Gemini 2.0 Flash
           → Gemini generates answer ONLY from provided context
           → Answer includes inline citations [1], [2], etc.
           → Citations link to original source documents
```

**Key safety property:** The model cannot hallucinate facts from its training data because the system prompt explicitly instructs it to only use the provided retrieved context. If the context doesn't contain enough information, the model says so.

### Relevance Filtering

An adaptive relevance filter ensures only high-quality sources reach the model:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `score_multiplier` | 4.0 | Cutoff = best_score × 4.0; lower-relevance results dropped |
| `min_results` | 5 | Always include at least 5 unique sources |
| `max_results` | 10 | Never exceed 10 unique sources |
| `score_floor` | 0.05 | Minimum cutoff to prevent over-filtering |

### Bias/Fairness Analysis

- **Training bias:** Not applicable — we do not train or fine-tune any model
- **Source bias:** Curated from established, editorially reviewed medical resources (WikEM, PMC peer-reviewed journals, LITFL, REBEL EM, ALiEM)
- **Content bias:** Institutional protocols are authored and approved by each organization's clinical leadership
- **Demographic bias:** Clinical protocols are evidence-based and apply to patient populations as defined by each institution's guidelines

### Monitoring Plan

| What | How | Frequency |
|------|-----|-----------|
| Query response time | Cloud Run metrics + application logging | Continuous |
| RAG retrieval relevance scores | Logged per query with score distributions | Every query |
| Citation accuracy | Domain expert user sessions (ED physicians, nurses, admins) | Ongoing — sessions scheduled |
| Model output quality | User feedback + domain expert review | Ongoing during pilot |
| Source freshness | Re-scrape schedules per source | Weekly–monthly per source |
| Clinical accuracy validation | Structured user sessions with ED Digital Health physicians | Scheduled and ongoing |

---

## 4. POC: Proof of Concept Results

### Scope

Validate that RAG-based clinical search outperforms standalone Gemini for bedside emergency medicine decision support.

### Test Methodology

5 representative EM queries tested against both standalone Gemini and our RAG system:
1. tPA contraindications and dosing for acute ischemic stroke
2. Undifferentiated shock management in hypotensive patient
3. Hyperkalemia management with EKG changes
4. Chest pain discharge criteria after negative troponin
5. RSI steps in suspected difficult airway

### Results Summary

| Criterion | Standalone Gemini | EM Protocol App (RAG) | Advantage |
|-----------|------------------|----------------------|-----------|
| **Medical Accuracy** | High (but unverifiable) | High (with citations) | RAG — verifiable |
| **Citations** | ❌ None | ✅ Inline with source links | RAG ✅ |
| **Visual Aids** | ❌ None | ✅ Flowcharts & algorithms | RAG ✅ |
| **Format Quality** | 9.2/10 (initial test) | 7-8/10 (after prompt upgrade) | Gemini (slight) |
| **Liability Protection** | ❌ No source attribution | ✅ Traceable to published sources | RAG ✅ |
| **Institutional Protocols** | ❌ No access | ✅ Organization-specific content | RAG ✅ |
| **Response Time** | ~1-2 seconds | ~1-2 seconds | Tie |

### Lessons Learned

1. **Prompt engineering matters:** Initial RAG scored 3.6/10 on format quality; after prompt upgrade (BLUF summary, markdown tables, flexible structure), improved to 7-8/10
2. **Multi-source retrieval is critical:** Single-corpus queries miss relevant context; parallel 6-corpus retrieval significantly improves answer quality
3. **Citation alignment:** Initial implementation had a mismatch where Gemini saw 5 sources but citations listed 15+; fixed with adaptive relevance filtering
4. **Table rendering:** Required `remark-gfm` for proper markdown table display in the frontend

---

## 5. REQUIREMENTS

### Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-1 | Clinicians can query in natural language and receive answers in < 2 seconds | ✅ Implemented |
| FR-2 | Answers include inline citations linking to source documents | ✅ Implemented |
| FR-3 | Relevant flowcharts and clinical images displayed alongside answers | ✅ Implemented |
| FR-4 | Admins can upload protocol PDFs via drag-and-drop, URL, or OneDrive | ✅ Implemented |
| FR-5 | Multi-tenant: each organization sees only their protocols | ✅ Implemented |
| FR-6 | Enterprise → ED → Bundle hierarchy for protocol organization | ✅ Implemented |
| FR-7 | Role-based access: super_admin, admin, user | ✅ Implemented |
| FR-8 | Dark mode and light mode support | ✅ Implemented |
| FR-9 | Two search modes: Clinical Search (Q&A) and Protocol Summary (card view) | ✅ Implemented |
| FR-10 | Source toggles: enable/disable individual knowledge bases per query | ✅ Implemented |

### Non-Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-1 | Response latency < 2 seconds (P95) | ✅ Met |
| NFR-2 | 99.9% uptime via Cloud Run auto-scaling | ✅ Met |
| NFR-3 | Encryption at rest (AES-256) and in transit (TLS 1.2+) | ✅ Met |
| NFR-4 | No PHI stored or transmitted | ✅ Met |
| NFR-5 | Organization-level data isolation | ✅ Met |
| NFR-6 | Desktop-first responsive design | ✅ Met |
| NFR-7 | Audit logging for all data access | ✅ Cloud Run logs |

### Acceptance Criteria

1. A clinician can type a clinical question and receive a cited, evidence-based answer within 2 seconds
2. Every factual claim in the response has an inline citation traceable to a source document
3. An admin can upload a protocol PDF and it becomes queryable within 5 minutes
4. Users in Organization A cannot see or query Organization B's protocols
5. The system correctly handles queries that span multiple knowledge sources (e.g., local protocol + WikEM + PMC)

---

## 6. CLINICAL & TECHNICAL: Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                              │
│                  emergencymedicine.app                            │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTPS
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Vercel)                              │
│              Next.js 16 + React 19 + Tailwind CSS 4              │
│                                                                   │
│  • Search interface (2 modes: Clinical Search, Protocol Summary) │
│  • Source toggle controls (WikEM, PMC, LITFL, REBEL EM, ALiEM)  │
│  • Enterprise/ED/Bundle selector                                 │
│  • Admin dashboard (protocol upload)                             │
│  • Owner dashboard (manage admins)                               │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTPS (REST API)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                BACKEND API (Google Cloud Run)                     │
│              FastAPI (Python 3.12) — us-central1                 │
│                                                                   │
│  • /query — RAG search with streaming responses                  │
│  • /enterprise — user organization data                          │
│  • /admin/* — protocol CRUD operations                           │
│  • /auth/* — Firebase authentication                             │
│  • /upload — PDF upload + processing pipeline                    │
└────┬─────────────┬──────────────┬───────────────────────────────┘
     │             │              │
     ▼             ▼              ▼
┌─────────┐ ┌───────────┐ ┌──────────────┐
│Firebase  │ │ Google    │ │ Vertex AI    │
│Auth +    │ │ Cloud     │ │ RAG Engine   │
│Firestore │ │ Storage   │ │ (us-west4)   │
│          │ │           │ │              │
│• Users   │ │• Raw PDFs │ │• 6 corpora:  │
│• Roles   │ │• Processed│ │  - Local     │
│• Orgs    │ │  text     │ │  - WikEM     │
│• EDs     │ │• Images   │ │  - PMC       │
│• Bundles │ │           │ │  - LITFL     │
│          │ │           │ │  - REBEL EM  │
│          │ │           │ │  - ALiEM     │
└─────────┘ └───────────┘ └──────┬───────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │ Gemini 2.0   │
                          │ Flash        │
                          │ (us-central1)│
                          │              │
                          │ Answer gen   │
                          │ from context │
                          └──────────────┘
```

### Query Flow

```
1. User types clinical question in search bar
2. Frontend sends authenticated request to Cloud Run API
3. API queries 6 RAG corpora in parallel (ThreadPoolExecutor)
4. Adaptive relevance filter selects top 5-10 unique sources
5. Retrieved contexts passed to Gemini 2.0 Flash with system prompt
6. Gemini generates answer using ONLY provided context
7. Answer streamed back to frontend via Server-Sent Events (SSE)
8. Frontend renders markdown with tables, citations, and images
9. Citation list built from filtered context sources
```

### EHR Integration Points

- **Current:** Standalone web application, no EHR integration
- **Planned (SOW 3.1 M3):** Embed chatbot within Epic (Plummer Chart) via MCP iFrame to support Emergency Department clinical workflows
- **Integration Method:** SMART on FHIR launch context; FHIR keys for production and test environments required
- **Epic Build:** Cardamom performs build in Epic MDEV environment; Mayo ERIS team responsible for migration across other environments
- **Patient Context:** Future capability to leverage patient-specific context where appropriate to support clinical use
- **Note:** The current app does not access, store, or transmit any patient data or EHR records

### Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind CSS 4, TypeScript |
| Backend | Python 3.12, FastAPI, Google Cloud Run |
| Authentication | Firebase Auth (Microsoft SSO + email/password) |
| Database | Google Cloud Firestore |
| Storage | Google Cloud Storage (6 buckets) |
| AI/ML | Google Vertex AI RAG API, Gemini 2.0 Flash, Document AI |
| Hosting | Vercel (frontend), Google Cloud Run (API) |
| Domain | emergencymedicine.app |

---

## 7. UI/UX: Interface Design

### Search Interface

- **Large centered search bar** (Google-style) with placeholder "What's the emergency?"
- **Source toggle buttons** inside search bar: Globe (WikEM + literature), Building (local protocols)
- **ED selection chips** showing selected Emergency Departments
- **Two search modes:**
  - **Clinical Search:** Streaming Q&A with markdown-formatted answers, inline citations, and images
  - **Protocol Summary:** Card-based view showing relevant protocol summaries

### Results Display

- **Bottom Line Up Front (BLUF):** 1-2 sentence actionable summary at top of every response
- **Structured formatting:** Markdown tables for dosing/scoring, bullet lists for criteria, numbered steps for procedures
- **Image carousel:** Protocol flowcharts and diagrams with horizontal scrolling, hover-to-zoom
- **Citation badges:** Color-coded by source type (blue = Local, green = WikEM, purple = PMC, etc.)
- **Dark mode / Light mode:** Full theme support

### Admin Interface

- **Admin Dashboard** (`/admin`): Upload protocols via drag-and-drop, URL, or OneDrive file picker; view and manage protocols per ED/bundle
- **Owner Dashboard** (`/owner`): Manage enterprises, EDs, bundles, and admin users across organizations

### Sidebar

- **Conversation history** with recent queries
- **Enterprise/ED/Bundle selector** with checkboxes
- **Source toggles** (WikEM, PMC, LITFL, REBEL EM, ALiEM)
- **Dark mode toggle**

---

## 8. COMPLIANCE & ASSESSMENTS

### IRB Determination

- **Status:** IRB review not yet initiated
- **Assessment:** The application processes published clinical guidelines and open-access medical literature — no patient data, no human subjects research. An IRB determination letter (exempt or not applicable) should be obtained prior to broader deployment.

### Mayo IT & Governance Involvement

| Item | Status |
|------|--------|
| **PSIF oversight** | ✅ Mayo IT involved through PSIF and MCP Deploy program governance |
| **AIA governance policies** | ✅ Aware of and following AIA governance requirements |
| **Azure AD admin consent** | ⏳ Pending — request submitted (see `docs/Mayo_IT_App_Approval_Request.md`) |
| **Domain expert validation** | ✅ User sessions scheduled and ongoing with ED Digital Health physicians, administrators, and nursing leadership |

### Clinical Disclaimers & Safety Language

The following disclaimers are live in the application:

**Clinical Disclaimer (Legal page + footer):**
> "EM Protocols is a clinical decision support tool designed exclusively for use by trained healthcare professionals. **This tool is not a substitute for professional medical judgment.** The information provided is intended as a reference aid and should not be used as the sole basis for clinical decisions. Users are responsible for independently verifying all information against institutional protocols, current medical literature, and their own clinical assessment of individual patients. This tool is not intended for use by patients or the general public and does not establish a provider–patient relationship."

**AI-Generated Content Disclosure (Legal page):**
> "Answers provided by EM Protocols are generated by Google Gemini 2.0 Flash, a large language model, using Retrieval-Augmented Generation (RAG). **AI-generated responses have not been reviewed by a human and may contain errors, omissions, or inaccuracies.** Content may not reflect the most current medical evidence or institutional guidelines. Users should always review cited sources directly and exercise independent clinical judgment before acting on any information provided by this tool."

**No Warranty (Legal page):**
> "EM Protocols and all content, services, and outputs are provided 'as is' and 'as available' without warranty of any kind. The clinician end user is solely responsible for all decisions regarding medical diagnosis and treatment for any person under their care."

**Use of Content (Legal page):**
> "EM Protocols uses Retrieval-Augmented Generation (RAG), not AI model training. Source content is stored in a search index and retrieved as verbatim excerpts with citations. Content is not ingested into model weights, is not modified, and can be removed from the index at any time upon request. This tool is used for educational and clinical decision support purposes only and is not operated commercially."

**AI Hallucination Safeguard:**
The system is configured so that if no relevant context is retrieved for a query, the AI explicitly states it does not have sufficient information to answer — rather than generating a speculative response.

### Data Privacy & Security

| Aspect | Detail |
|--------|--------|
| **PHI** | ❌ No patient data stored, transmitted, or processed |
| **PII** | Minimal — user email and display name for authentication only |
| **Protocol Content** | Mayo-owned institutional protocols; permission granted by local ED department; verified to contain no PHI |
| **Data at Rest** | AES-256 encryption (GCP default) |
| **Data in Transit** | TLS 1.2+ (HTTPS only) |
| **Authentication** | Firebase Auth with Microsoft SSO (Mayo Azure AD) |
| **Authorization** | Role-based (super_admin, admin, user) with org-level isolation |
| **Audit Logging** | Cloud Run request logs, Firestore access logs |
| **Data Residency** | US regions only (Google Cloud) |

### HIPAA Assessment

| HIPAA Consideration | Applicability |
|--------------------|---------------|
| Business Associate Agreement (BAA) | Available with GCP; recommended for institutional deployment |
| PHI handling | Not applicable — no PHI processed |
| Minimum necessary standard | N/A — no patient data |
| Breach notification | N/A — no PHI |

### Technical Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| AI hallucination (incorrect medical info) | High | RAG grounding: model restricted to retrieved context only; temperature=0.2; inline citations for verification |
| Source content inaccuracy | Medium | All sources are peer-reviewed or editorially managed; citations enable clinician verification |
| Unauthorized access to protocols | Medium | Firebase Auth + role-based access + organization-level Firestore isolation |
| Service availability | Low | Cloud Run auto-scaling with 99.9% SLA |
| Data loss | Low | GCP managed storage with automatic replication |
| Over-reliance on AI output | Medium | Disclaimer: "AI-generated summary for clinical reference — verify with primary sources"; intended as decision *support*, not decision *making* |

### Safety Measures

1. **Grounding:** Gemini is explicitly instructed to ONLY use provided context — if information is insufficient, it says so
2. **Citations:** Every factual claim requires an inline citation — clinicians can verify against the original source
3. **Source transparency:** Color-coded citation badges show whether information comes from institutional protocols, WikEM, PMC journals, etc.
4. **Low temperature (0.2):** Minimizes creative/speculative outputs
5. **Adaptive filtering:** Relevance scoring drops low-quality retrieval results before they reach the model
6. **No patient data:** The system never processes, stores, or has access to patient information

### Licensing & Legal Compliance

All external content sources operate under Creative Commons licenses with documented compliance:
- Full attribution in every citation
- Non-commercial use (educational/clinical tool)
- License-specific requirements (ShareAlike, NoDerivatives) respected per source
- Detailed compliance documentation maintained in `docs/SOURCE_LICENSING_SUMMARY.md`

---

## 9. STATEMENT OF WORK: Cardamom Health (SOW 3.1)

### Engagement Overview

| Field | Detail |
|-------|--------|
| **SOW** | 3.1 — Emergency Medicine LLM Chatbot Integration |
| **Master Agreement** | Professional Consulting Services Agreement, CAR-340074 (effective January 14, 2025) |
| **Consultant** | Cardamom Health ("Cardamom") — EHR consulting services firm providing data, analytics, and application experts |
| **Relationship** | Extension of SOW A-3.0 "Emergency Medicine LLM Chatbot Integration" |
| **Contract Period** | January 1, 2026 – March 31, 2026 |
| **Total Fixed Fee** | $51,000 |

### Objectives

1. **CAF Migration & Model Framework Implementation** — Migrate the existing solution into the CAF environment and implement the updated model framework with a new LLM optimized for Emergency Medicine workflows
2. **Production Go-Live** — Deploy the Emergency Medicine LLM chatbot into Mayo production workflows as a production-ready application for Mayo end users

### Scope

#### In Scope

- Finalize and deploy the LLM-powered chatbot with MCP-aligned UI/UX in a production-ready state
- Formally migrate solution to the CAF environment with updated architecture using LLMs specifically for the chatbot
- Embed the chatbot within Epic (Plummer Chart) via MCP iFrame to support Emergency Department clinical workflows
- Enable the chatbot to leverage patient-specific context where appropriate to support clinical use
- Coordinate production deployment activities, including planning, status reporting, and cross-team change management

#### Out of Scope

- Training the LLM on new data sources, including Mayo-specific data sources
- Modifications to the RAG system or intake and processing of source material
- Long-term maintenance & support post-implementation (requires separate agreement)
- Change management and training (beyond SOW deliverables)

### Milestones & Payment

| Milestone | Description | Due Date | Fee | Acceptance Criteria |
|-----------|-------------|----------|-----|---------------------|
| **M1** — Project Kickoff & Scope Confirmation | Transition active workstreams into 2026 delivery year | Jan 5, 2026 | $17,000 | Scope alignment with MCP |
| **M2** — Migrate EM Chatbot to CAF | Migrate solution to CAF with new LLM architecture | Mar 13, 2026 | $7,000 | Fully deployed in MCP/Deploy |
| **M3** — Go-Live, Training & Project Closure | Deploy solution into production and formally close project | Apr 30, 2026 | $27,000 | All deliverables accepted, transition complete |
| | | **Total** | **$51,000** | |

### Deliverables

**M1 — Project Initiation and Kickoff:**
- Transition active workstreams into the 2026 delivery year
- Align teams on priorities and next steps

**M2 — Replatform the Solution:**
- Migrate the LLM chatbot solution to the CAF environment using the updated LLM architecture
- Evaluate and validate LLM model performance to determine optimal configuration for EM workflows
- Complete and deliver updated solution and architecture documentation

**M3 — Production Deployment:**
- Application deployed in GCP and Epic Production
- Delivered GitHub Repository with application code
- GitHub Repository with Terraform code for infrastructure deployment in GCP
- Documentation of overall architecture

### Roles & Responsibilities

| Responsibility | Mayo Clinic | Cardamom | Shared |
|---------------|:-----------:|:--------:|:------:|
| Provide access to existing EM application model & data | ✅ | | |
| Define clinical objectives & success criteria | | | ✅ |
| Enhanced UI/UX | | ✅ | |
| Chatbot deployment within MCP environment | | ✅ | |
| Design & execute workflow integration in Epic | | ✅ | |
| Project management & coordination | | ✅ | |
| User training & adoption support | | | ✅ |
| Knowledge transfer & transition | | | ✅ |
| Ongoing maintenance and support | ✅ | | |

### Dependencies

| Dependency | Owner | Required By |
|-----------|-------|-------------|
| MDEV functional with FHIR keys | Mayo IT | Jan 1, 2026 |
| CAF enabled for Vertex AI | Mayo IT | Jan 15, 2026 |
| ERIS resources assigned for build and testing | Mayo IT | Jan 31, 2026 |
| Production and Test environment FHIR keys available | Mayo IT | Jan 31, 2026 |
| Cardamom access to Epic Test environment | Mayo IT | Jan 31, 2026 |
| Mayo data scientists for model optimization/validation | Mayo | Ongoing |
| Clinical SMEs for validation and success metrics | Mayo EM | Ongoing |
| Epic analysts/Access staff for workflow integration | Mayo IT | Ongoing |
| Stakeholder review/sign-off on model updates & designs | Mayo EM | Ongoing |
| MCP Tech team guidance on data availability & limitations | MCP Deploy | Ongoing |
| Governance/change control approvals aligned with go-live | Mayo IT | Ongoing |

### Compliance Requirements (SOW)

Consultant must comply with:
- Mayo Clinic's data security and privacy policies
- HIPAA, FDA, and relevant healthcare regulations
- Any applicable Business Associate Agreement (BAA)

---

## Contact

| Role | Name | Email |
|------|------|-------|
| **Co-Founder & Technical Lead** | Derick Jones, MD, MBA, MHI | jones.derick@mayo.edu |
| **Co-Founder & Clinical Champion** | Jake Morey, MD, MBA | — |
| **Department Chair (Sponsor)** | Jim Colletti, MD | — |
| **Development Partner** | Cardamom Health (SOW 3.1) | — |
| **Department** | Emergency Medicine, Rochester, MN | — |
| **Application URL** | https://emergencymedicine.app | — |
| **Funding** | PSIF — Mayo Clinic Platform Deploy | — |
| **Repository** | github.com/derickjones/em-app-protocols (private) | — |
