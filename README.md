# 🏥 Emergency Medicine Protocol RAG System

A production-ready, HIPAA-compliant RAG (Retrieval-Augmented Generation) system that enables healthcare organizations to upload emergency medicine protocols in PDF format and provides fast, intelligent query capabilities with visual protocol display powered by Google Vertex AI.

---

## 🚀 Elevator Pitch

We're building an AI-powered emergency medicine app that solves a critical problem: current protocol websites are slow and cumbersome when seconds matter. Our system lets hospitals upload their EM protocols as PDFs, and we use Google's Vertex AI to provide instant, accurate answers with visual flowcharts. Think **"ChatGPT meets your hospital's protocol library"** - but fast, HIPAA-compliant, and built specifically for emergency medicine.

---

## 🔴 The Problem

Right now, when an ER doctor or nurse needs to look up a protocol during an emergency:
- They navigate through clunky hospital websites
- Click through multiple PDFs
- Manually search for the right section
- Struggle to find the relevant flowchart or algorithm
- **This takes too long when treating critical patients**

---

## ✅ Our Solution

We're building a **RAG (Retrieval-Augmented Generation) system** that:

1. **Ingests** hospital protocols (PDFs) automatically
2. **Extracts** all text AND images (flowcharts, algorithms, diagrams)
3. **Indexes** everything using Google Vertex AI's RAG engine
4. **Answers** clinician questions in plain English in under 2 seconds
5. **Shows** relevant flowcharts prominently alongside answers
6. **Cites** exact protocols and page numbers (clickable PDFs)

### **Example Query Flow**
**Question**: *"What's the STEMI treatment pathway?"*

**Response**: 
- **Answer**: Bullet-point summary from protocol
- **Visuals**: ACLS flowchart image displayed prominently
- **Citation**: "STEMI Protocol v2026, pages 3-4 [View PDF ↗]" (clickable)

---

## 🎯 Project Overview

### Vision
Transform cumbersome protocol websites into a fast, convenient, AI-powered system that provides real-time emergency medicine guidance with visual flowcharts and accurate citations.

### Target Users
- Emergency Physicians
- Advanced Practice Providers
- Nurses
- Residents
- Medical Students

### Key Differentiator
Unlike traditional protocol websites that are slow and cumbersome, this system provides **sub-2 second** responses with **prominent visual displays** of flowcharts and diagrams, making critical information instantly accessible during emergencies.

---

## 🚀 Critical Success Factors

1. ⚡ **Speed**: Sub-2 second query responses
2. 🎨 **Visual-First**: Flowcharts/diagrams prominently displayed
3. 🏥 **Multi-Tenant**: Organization isolation from day one
4. 🔒 **HIPAA Compliant**: Secure architecture from start
5. 📱 **Desktop-First**: Mobile optimization in later phase

---

## 📅 1-Month MVP Roadmap

### **Week 1: Foundation & Proof of Concept**
**Goal**: Prove Vertex AI RAG works with medical protocols

**Tasks**:
- Set up GCP project with HIPAA-compliant configuration
- Configure Vertex AI RAG Engine
- Test with 3-5 sample protocols from pilot partners
- Validate image extraction quality (Document AI)
- Test query accuracy with domain experts

**Deliverable**: Working RAG demo with real protocols

---

### **Week 2: Core Pipeline**
**Goal**: Automated PDF → RAG pipeline

**Tasks**:
- Build PDF upload service (Cloud Storage + validation)
- Implement Document AI processing
- Extract and store images separately
- Create chunking strategy that preserves context
- Link chunks to images and page numbers
- Set up organization-scoped RAG corpus

**Deliverable**: Upload PDF → auto-processed → queryable

---

### **Week 3: Query Interface & UI**
**Goal**: Fast, beautiful search experience

**Tasks**:
- Build query API with Vertex AI RAG
- Create response format (answer + images + citations)
- Design and build search UI
- Implement image gallery display
- Add clickable PDF citations (open to specific page)
- Performance optimization (caching, CDN)

**Deliverable**: Functional web app with visual results

---

### **Week 4: Multi-Org & Polish**
**Goal**: Production-ready for pilot partners

**Tasks**:
- Implement organization management
- Add basic authentication (Firebase Auth)
- Create admin upload interface
- Test with all pilot partners
- Security audit and HIPAA checklist
- Deploy to production

**Deliverable**: Live app ready for 10 pilot organizations

---

## 🏗️ Architecture Overview

### **Tech Stack**

#### **Frontend**
- **Next.js** - React framework for fast, SEO-friendly development
- **Tailwind CSS** - Rapid beautiful UI development
- **shadcn/ui** - Pre-built accessible components
- **React PDF** - PDF viewer with page navigation
- **Deployment**: Vercel or Cloud Run

#### **Backend**
- **Python + FastAPI** - Fast development, excellent GCP SDK support
- **Cloud Run** - Serverless, auto-scaling, HIPAA-eligible
- **Cloud Functions** - Event-driven PDF processing

#### **Google Cloud Services**
- **Vertex AI RAG API** - Core RAG functionality
- **Document AI** - PDF processing with layout detection
- **Cloud Storage** - PDFs and images (HIPAA-compliant buckets)
- **Firestore** - Fast queries, real-time updates, multi-tenant friendly
- **Firebase Auth** - Quick authentication with organization claims
- **Cloud CDN** - Fast image delivery
- **Secret Manager** - API keys and credentials

---

## 📊 Data Architecture

### **Storage Structure**
```
Cloud Storage Buckets:
├── protocols-raw/
│   └── {organization-id}/
│       └── {protocol-id}/
│           └── original.pdf
├── protocols-processed/
│   └── {organization-id}/
│       └── {protocol-id}/
│           ├── extracted-text.json
│           ├── metadata.json
│           └── images/
│               ├── page-1-img-1.png
│               └── page-2-img-1.png
└── protocols-thumbnails/
    └── {organization-id}/
        └── {protocol-id}-thumb.png
```

### **Firestore Data Model**

```
organizations/{orgId}
  - name
  - subscription_tier
  - created_at
  - settings
  
  /protocols/{protocolId}
    - title
    - filename
    - upload_date
    - uploaded_by
    - status (processing|ready|failed)
    - page_count
    - storage_path
    - category (auto-labeled)
    - tags[]
    - last_updated
    
    /images/{imageId}
      - page_number
      - storage_path
      - type (flowchart|diagram|table|photo)
      - thumbnail_path
      - position_in_page
    
    /chunks/{chunkId}
      - content
      - page_range
      - related_image_ids[]
      - embedding_id (Vertex AI reference)

  /users/{userId}
    - email
    - role (admin|user)
    - created_at
    - last_login
```

---

## 🔄 Processing Pipeline

### **Upload Flow** (< 1 minute for 10-page PDF)

```
1. User uploads PDF → Cloud Storage
2. Triggers Cloud Function
3. Document AI extracts:
   - Text with layout
   - Images (high quality)
   - Tables (preserved structure)
4. Auto-label metadata (Vertex AI Gemini)
5. Chunk text (preserve context)
6. Generate embeddings → Vertex AI RAG corpus
7. Store images in Cloud Storage + CDN
8. Update Firestore: status = "ready"
9. Notify user (real-time update)
```

### **Image Extraction Strategy**
- Extract ALL images from PDF (Document AI)
- Classify type: flowchart, diagram, table, photo (Vertex AI Vision)
- **Prioritize** flowcharts and algorithms (ML model or heuristics)
- Generate thumbnails for fast loading
- Link images to text chunks that reference them
- Store metadata: "This flowchart appears on page 3, section 'ACLS Protocol'"

---

## 🔍 Query Flow (< 2 seconds)

### **Example Query**: "What's the STEMI treatment pathway?"

```
1. Generate query embedding (Vertex AI)
2. Search RAG corpus (scoped to user's org)
3. Retrieve top 5 chunks with context
4. Identify related images (flowcharts!)
5. Generate answer with Gemini:
   - Bullet point format
   - Include protocol names
   - Reference page numbers
6. Return response:
   {
     answer: "• Activate cath lab within 90 minutes...",
     images: [flowchart_urls],
     citations: [
       {
         protocol: "STEMI Protocol 2026",
         pages: [3, 4],
         pdf_url: "...",
         confidence: 0.95
       }
     ]
   }
7. Display prominently in UI
```

---

## 🎨 UI/UX Design

### **Search Interface**
- **Large search bar** (Google-style, center of page)
- Auto-suggestions as user types
- Recent queries (if time permits)
- Example queries ("Try: 'sepsis bundle'")

### **Results Display**
```
┌─────────────────────────────────────────┐
│  [AI Answer - Bullet Points]            │
│  • Key point 1                           │
│  • Key point 2                           │
└─────────────────────────────────────────┘

┌───────────┐ ┌───────────┐ ┌───────────┐
│ Flowchart │ │ Algorithm │ │  Table    │
│  Image 1  │ │  Image 2  │ │  Image 3  │
└───────────┘ └───────────┘ └───────────┘
     ↑ Click to enlarge

📄 Sources:
• STEMI Protocol (v2026.1) - Pages 3-4 [View PDF ↗]
• Cardiac Cath Lab Activation - Page 2 [View PDF ↗]
```

### **PDF Viewer**
- Opens in modal/sidebar
- Jumps to cited page number
- Highlight relevant section (if feasible)
- Close and return to results

### **Visual Priority**
- Images take **50% of screen space**
- Text answer: clean, scannable
- Mobile: stack vertically (images → answer → citations)

---

## 🔐 HIPAA Compliance

### **GCP Configuration**
- Enable **Cloud Healthcare API** (HIPAA-eligible services)
- Sign **BAA (Business Associate Agreement)** with Google
- Use only HIPAA-compliant services
- Enable **VPC Service Controls** for data perimeter
- Configure **Cloud Audit Logs** (all access logged)

### **Data Handling**
- Encryption at rest (default with GCP)
- Encryption in transit (TLS 1.2+)
- No PHI in protocols if possible (just clinical guidelines)
- If PHI present: DLP API for detection/redaction
- Data residency controls (US-only regions)

### **Access Controls**
- Organization-level data isolation (Firestore security rules)
- Authentication required for all endpoints
- Role-based access (Firebase custom claims)
- Session management and timeout
- Audit logging for all data access

### **Compliance Checklist**
- ✅ BAA with Google Cloud
- ✅ Access controls and authentication
- ✅ Encryption (rest + transit)
- ✅ Audit logging
- ✅ Data isolation (multi-tenancy)
- ✅ Security monitoring
- 📋 Privacy policy and ToS
- 📋 Risk assessment documentation
- 📋 Incident response plan

---

## ✨ MVP Features

### **For Organizations (Admin Users)**
✅ Upload PDFs (drag-and-drop)  
✅ Auto-processing with progress indicator  
✅ View all protocols in library  
✅ Simple organization settings  

❌ ~~Advanced metadata editing~~ (auto-generate only)  
❌ ~~Version control~~ (just show last updated)  
❌ ~~User role management~~ (admin vs user only)  

### **For End Users (Clinicians)**
✅ Fast natural language search  
✅ AI-generated answers (bullet points)  
✅ Relevant images/flowcharts displayed prominently  
✅ Clickable citations to PDF (opens at specific page)  
✅ See which protocol(s) answer came from  
✅ Mobile-responsive (works on tablet, optimized later)  

❌ ~~Save favorites~~ (later)  
❌ ~~Query history~~ (later)  
❌ ~~Share results~~ (later)  

---

## 💰 Cost Estimate

### **Assumptions (First Year, 10 Organizations)**
- 10 organizations × 100 protocols = 1,000 PDFs
- Average 5 pages per PDF = 5,000 pages
- 10,000 queries/month total

### **GCP Costs** (monthly, steady state)
- **Document AI**: ~$0.50/page × 5,000 = $2,500 (one-time processing)
- **Vertex AI RAG**: ~$0.001/query × 10,000 = $10
- **Cloud Storage**: ~100 GB × $0.02 = $2
- **Firestore**: ~$0.06/100K reads × moderate usage = $20
- **Cloud Run**: ~$50 (light traffic)
- **Cloud CDN**: ~$20
- **Total**: ~$100/month (after initial processing)
- **First year**: ~$3,700 (includes one-time processing)

### **Revenue Goal**
$99-299/org/month = $11,880-$35,880/year (10 orgs)

---

## 📋 Repository Structure

```
em-app-external/
├── frontend/           # Next.js app
│   ├── components/     # React components
│   ├── pages/          # Next.js pages
│   ├── styles/         # Tailwind CSS
│   └── lib/            # Utilities
├── backend/            # FastAPI services
│   ├── api/            # API routes
│   ├── services/       # Business logic
│   ├── models/         # Data models
│   └── utils/          # Helpers
├── functions/          # Cloud Functions
│   ├── pdf-processor/  # PDF processing pipeline
│   └── rag-indexer/    # RAG corpus indexing
├── infrastructure/     # Terraform (GCP setup)
│   ├── main.tf
│   ├── variables.tf
│   └── modules/
├── docs/               # Documentation
│   ├── api.md
│   ├── deployment.md
│   └── user-guide.md
└── scripts/            # Deployment & utility scripts
```

---

## 🚦 Getting Started

### **Prerequisites**
- Google Cloud Platform account
- GCP project with billing enabled
- BAA signed with Google Cloud (for HIPAA compliance)
- Node.js 18+ and Python 3.11+
- Terraform (for infrastructure setup)

### **Initial Setup**

1. **Clone the repository**
```bash
git clone <repository-url>
cd em-app-external
```

2. **Set up GCP project**
```bash
cd infrastructure
terraform init
terraform plan
terraform apply
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your GCP project details
```

4. **Install dependencies**
```bash
# Frontend
cd frontend
npm install

# Backend
cd ../backend
pip install -r requirements.txt
```

5. **Run locally**
```bash
# Frontend
npm run dev

# Backend
uvicorn main:app --reload
```

---

## 🎯 Next Steps (Priority Order)

### **Immediate (This Week)**
1. ✅ Set up GCP project with HIPAA-eligible configuration
2. ✅ Get 10-20 sample PDFs from pilot partners
3. ✅ Test Vertex AI RAG with sample protocols (proof of concept)
4. ✅ Validate Document AI image extraction quality
5. ✅ Create tech stack decision document

### **Week 1 Deep Dive**
6. Design Firestore schema (organizations, protocols, users)
7. Build minimal PDF upload (Cloud Storage + Function trigger)
8. Test end-to-end: Upload → Process → Query
9. Get feedback from 1-2 pilot users on query quality

### **Before Development Starts**
10. Sign BAA with Google Cloud
11. Create project timeline (Gantt chart, milestones)
12. Set up repository structure
13. Design UI mockups (Figma or similar)
14. Prepare sample data set (anonymized protocols)

---

## 📊 Success Metrics

### **MVP Success Criteria**
- Query response time < 2 seconds
- RAG accuracy > 90% (validated by domain experts)
- Image extraction quality > 95%
- Successfully onboard 10 pilot organizations
- Positive feedback from pilot users
- HIPAA compliance audit passed

### **Long-Term Metrics**
- User satisfaction score > 4.5/5
- Successful PDF processing rate > 98%
- System uptime > 99.9%
- 100s-1000s of organizations using the platform
- Weekly protocol updates automated

---

## 🔒 Security & Compliance

### **Security Best Practices**
- All secrets stored in Google Secret Manager
- No hardcoded credentials
- CORS properly configured
- Input validation on all endpoints
- Rate limiting on API endpoints
- Regular security audits

### **Data Privacy**
- Organization data completely isolated
- No cross-organization queries possible
- User data minimization
- Right to deletion implemented
- Data retention policies configured

---

## 🤝 Contributing

(To be added as team expands)

---

## 📝 License

(To be determined - consider commercial licensing)

---

## 📞 Support

For questions or support:
- Email: (to be added)
- Slack: (to be added for pilot partners)
- Documentation: See `/docs` folder

---

## 🙏 Acknowledgments

- Pilot partner healthcare organizations
- Google Cloud Vertex AI team
- Emergency medicine domain experts

---

**Last Updated**: January 23, 2026  
**Version**: 0.1.0 (Pre-MVP)  
**Status**: Planning Phase
