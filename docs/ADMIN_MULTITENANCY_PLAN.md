# 🏢 Multi-Tenant Admin & Content Management Plan

## Overview

This document outlines how administrators upload and manage protocols, and how users in different healthcare organizations access their organization's content securely.

---

## 🎯 Goals

1. **Organization Isolation** - Each hospital/practice sees only their protocols
2. **Role-Based Access** - Admins manage content, users query it
3. **Simple Onboarding** - Easy for new orgs to get started
4. **Secure by Default** - HIPAA-compliant from day one
5. **Scalable** - Support 100s of organizations

---

## 🏗️ Core Concepts

### Hierarchy

```
Hospital/Practice (Organization)
└── Protocol Bundles
    ├── Practice Protocols    (ED clinical guidelines, ACLS, sepsis)
    ├── Nursing Protocols     (nursing-specific workflows)
    ├── Telemed Protocols     (telemedicine procedures)
    ├── Pediatric Protocols   (peds-specific guidelines)
    └── Trauma Protocols      (trauma center specific)
```

### Why Protocol Bundles?
- Different departments/roles need different content
- A nurse might only need "Nursing Protocols"
- A telemed physician needs "Telemed Protocols" 
- Users can toggle between bundles they have access to
- Each bundle has its own RAG corpus for clean separation

---

## 👥 User Roles

### **Super Admin** (Your Team)
- Create/manage organizations
- View system-wide analytics
- Manage subscription tiers
- Support and troubleshooting

### **Org Admin** (Hospital IT/Clinical Informatics)
- Upload/delete protocols for their org
- Manage users in their org
- View org usage analytics
- Configure org settings (logo, name, etc.)

### **User** (ED Physicians, Nurses, etc.)
- Query protocols
- View answers, images, citations
- No content management access

---

## 🏗️ Architecture

### Data Model (Firestore)

```
/organizations/{orgId}
  - name: "Memorial Hospital"
  - slug: "memorial-hospital"
  - logo_url: "gs://..."
  - subscription_tier: "professional"
  - created_at: timestamp
  - settings: {
      allow_user_signup: false,
      require_email_domain: "@memorial.org",
      max_protocols: 100
    }

  /bundles/{bundleId}  // Protocol Bundles within an org
    - name: "Practice Protocols"
    - slug: "practice"
    - description: "Clinical protocols and guidelines"
    - icon: "clipboard-list"
    - color: "#3B82F6"  // Blue
    - rag_corpus_id: "123456789"  // Each bundle has its own RAG corpus
    - is_default: true
    - order: 1
    - created_at: timestamp
    
    /content/{contentId}  // Content items within a bundle
      - title: "ACLS Cardiac Arrest Algorithm"
      - filename: "ACLS_2025.pdf"
      - uploaded_by: "userId"
      - upload_date: timestamp
      - status: "ready" | "processing" | "failed"
      - page_count: 12
      - image_count: 5
      - category: "Cardiac"
      - tags: ["ACLS", "cardiac arrest", "CPR"]
      - pdf_url: "gs://..."
      - last_updated: timestamp

  /users/{userId}
    - email: "dr.smith@memorial.org"
    - display_name: "Dr. Sarah Smith"
    - role: "admin" | "user"
    - bundle_access: ["practice", "nursing", "telemed"]  // Which bundles user can access
    - created_at: timestamp
    - last_login: timestamp
    - invited_by: "adminUserId"

/users/{userId}  // Top-level for auth lookup
  - org_id: "memorial-hospital"
  - email: "dr.smith@memorial.org"
  - role: "admin"
```

### Example Protocol Bundles for a Hospital

| Bundle | Description | Use Case |
|--------|-------------|----------|
| **Practice Protocols** | ED clinical guidelines, ACLS, sepsis | "How do I treat sepsis?" |
| **Nursing Protocols** | Nursing-specific workflows, assessments | "Sepsis nursing assessment checklist" |
| **Telemed Protocols** | Telemedicine procedures | "Virtual cardiac exam requirements" |
| **Pediatric Protocols** | Peds-specific guidelines | "Pediatric sepsis criteria" |
| **Trauma Protocols** | Trauma center specific | "Massive transfusion protocol" |

### Bundle Selector UI

```
┌─────────────────────────────────────────────────────────┐
│  Memorial Hospital                                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [📋 Practice Protocols ▼]  ← Bundle selector dropdown   │
│   ├─ 🏥 All Bundles (hospital-wide search)              │
│   ├─ ────────────────                                   │
│   ├─ 📋 Practice Protocols (selected)                   │
│   ├─ 🏥 Nursing Protocols                               │
│   ├─ 🖥️ Telemed Protocols                               │
│   ├─ 👶 Pediatric Protocols                             │
│   └─ � Trauma Protocols                                │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Enter a clinical question...                        ││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
│  Searching: Practice Protocols                           │
└─────────────────────────────────────────────────────────┘
```

### Storage Structure (Updated)

```
Cloud Storage:
├── content-raw/
│   └── {org-id}/
│       └── {bundle-id}/
│           └── {content-id}.pdf
│
├── content-processed/
│   └── {org-id}/
│       └── {bundle-id}/
│           └── {content-id}/
│               ├── extracted_text.txt
│               ├── metadata.json
│               └── images/
│                   ├── page_1_img_1.png
│                   └── page_2_img_1.png
│
└── org-assets/
    └── {org-id}/
        └── logo.png
```

### RAG Corpus Strategy

**Recommended: One Corpus Per Bundle Per Organization** ✅

```
Organization: Memorial Hospital
├── Corpus: memorial-practice     (rag_corpus_id: "111...")
├── Corpus: memorial-nursing      (rag_corpus_id: "222...")
├── Corpus: memorial-telemed      (rag_corpus_id: "333...")
├── Corpus: memorial-pediatric    (rag_corpus_id: "444...")
└── Corpus: memorial-trauma       (rag_corpus_id: "555...")
```

**Benefits:**
- Complete data isolation between orgs AND bundles
- User switches bundle → queries different corpus
- "All Bundles" search → queries multiple corpora in parallel
- Easy to manage permissions per bundle
- Clean deletion (delete corpus = delete all bundle content)
- No risk of cross-contamination in search results

**Trade-offs:**
- More corpora to manage
- Slightly higher overhead
- Worth it for clean separation

**Alternative: Single Corpus with Bundle Metadata**
- All docs in one corpus with `bundle_id` metadata filter
- Simpler but less isolated
- Risk: filter bypass could leak data
- Not recommended for sensitive separation
- Filter queries by `org_id`
- Risk: metadata filter bypass = data leak
- Not recommended for HIPAA

---

## 🔐 Authentication Flow

### Tech: Firebase Authentication

```
1. User visits app → prompted to sign in
2. Sign in with:
   - Email/password (invited users)
   - Google Workspace (if org allows)
   - SSO/SAML (enterprise tier)
3. Firebase creates JWT with custom claims:
   {
     org_id: "memorial-hospital",
     role: "admin" | "user"
   }
4. Frontend stores token, sends with all API requests
5. Backend validates token, extracts org_id
6. Queries scoped to org's RAG corpus
```

### User Onboarding Flows

**Flow 1: Admin Invites User**
```
1. Org Admin goes to Admin Panel → Users
2. Enters email: "dr.jones@memorial.org"
3. Selects role: "User"
4. System sends invite email with magic link
5. User clicks link → creates password → logged in
6. User auto-associated with org
```

**Flow 2: Domain-Restricted Signup** (Optional)
```
1. Org Admin enables "Allow signups from @memorial.org"
2. New user visits app → "Sign up"
3. Enters email: "nurse.kim@memorial.org"
4. System validates domain matches org setting
5. User creates account → pending admin approval OR auto-approved
```

---

## 📤 Admin Upload Flow

### UI: Admin Dashboard (with Bundles)

```
┌─────────────────────────────────────────────────────────┐
│  Memorial Hospital - Admin Dashboard                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Bundle: [� Protocols ▼]  ← Select bundle   │
│                                                          │
│  [� Content]  [🎨 Bundles]  [👥 Users]  [⚙️ Settings]    │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │  📤 Upload to: Protocols                             ││
│  │  ┌─────────────────────────────────────────────────┐││
│  │  │  Drag & drop PDF here or click to browse        │││
│  │  └─────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
│  📋 Protocols Content (24 items)                         │
│  ┌──────────────────────────────────────────────────────┐│
│  │ ✅ ACLS Cardiac Arrest 2025    │ 12 pages │ Delete  ││
│  │ ✅ Sepsis Bundle Protocol      │  8 pages │ Delete  ││
│  │ ⏳ Stroke Protocol (processing)│    --    │ Cancel  ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [🎨 Manage Bundles] → Create new bundles, configure    │
└─────────────────────────────────────────────────────────┘
```

### Bundle Management UI (Admin Only)

```
┌─────────────────────────────────────────────────────────┐
│  Manage Protocol Bundles                                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [+ Create New Bundle]                                   │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐│
│  │ 📋 Practice Protocols │ 24 items │ Default │ Edit   ││
│  │ 🏥 Nursing Protocols  │ 12 items │         │ Edit   ││
│  │ 🖥️ Telemed Protocols  │  8 items │         │ Edit   ││
│  │ 👶 Pediatric Protocols│ 15 items │         │ Edit   ││
│  │ � Trauma Protocols   │ 10 items │         │ Edit   ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  Note: Deleting a bundle removes all its content and    │
│  RAG corpus. This cannot be undone.                     │
└─────────────────────────────────────────────────────────┘
```

### Upload Processing Pipeline (with Bundles)

```
1. Admin selects bundle (e.g., "Practice Protocols")
2. Admin uploads PDF file
3. Frontend validates:
   - File type (PDF only)
   - File size (< 50MB)
   - Bundle content limit not exceeded
   
4. Frontend uploads to Cloud Storage:
   gs://content-raw/{org-id}/{bundle-id}/{content-id}.pdf
   
5. Frontend creates Firestore doc:
   /organizations/{org-id}/bundles/{bundle-id}/content/{content-id}
   status: "processing"
   
6. Cloud Function triggered by GCS upload:
   a. Extract text with Document AI
   b. Extract images
   c. Store processed content
   d. Add to bundle's RAG corpus (bundle.rag_corpus_id)
   e. Update Firestore: status = "ready"
   
6. Admin UI updates in real-time (Firestore listener)
   Shows: "✅ ACLS Protocol ready"
```

### Delete Protocol Flow

```
1. Admin clicks "Delete" on protocol
2. Confirmation modal: "Delete ACLS Protocol? This cannot be undone."
3. On confirm:
   a. Delete from RAG corpus
   b. Delete from Cloud Storage (PDF + images)
   c. Delete Firestore document
4. UI updates immediately
```

---

## 🔍 User Query Flow (Multi-Tenant with Bundles)

```
1. User selects bundle(s): "Practice Protocols" or "All Bundles"
2. User sends query: "STEMI treatment"
3. API receives request with JWT token + bundle_ids
4. Backend extracts org_id from token: "memorial-hospital"
5. Backend validates user has access to requested bundles
6. If single bundle: Query that bundle's RAG corpus
   If "all" or multiple: Query each corpus in parallel
7. Merge results, re-rank by relevance
8. Return results with bundle-specific citations (each citation shows which bundle)
9. User sees content from selected bundle(s)
```

### User Bundle Toggle Experience

```
User opens app → Defaults to "Practice Protocols" bundle
User queries: "STEMI treatment" → Gets protocol results

User clicks bundle dropdown → Selects "Nursing Protocols"
Bundle indicator changes: "🏥 Nursing Protocols"
User queries: "STEMI nursing care" → Gets nursing content

User switches to "All Bundles" (hospital-wide search)
User queries: "sepsis management" → Gets results from ALL bundles
```

---

## 🔍 Hospital-Level Search (Cross-Bundle Query)

### Concept

Users can search **across all bundles** or **selected bundles** within their hospital, not just one at a time.

```
┌─────────────────────────────────────────────────────────┐
│  Memorial Hospital                                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Search In: [🏥 All Bundles ▼]  ← Bundle selector       │
│   ├─ 🏥 All Bundles (search everything)                 │
│   ├─ ────────────────                                   │
│   ├─ 📋 Practice Protocols                              │
│   ├─ 🏥 Nursing Protocols                               │
│   ├─ 🖥️ Telemed Protocols                               │
│   ├─ 👶 Pediatric Protocols                             │
│   └─ 🚨 Trauma Protocols                                │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │  sepsis management                                   ││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
│  Searching: All hospital bundles                         │
└─────────────────────────────────────────────────────────┘
```

### Search Results with Bundle Badges

When searching across multiple bundles, results show which bundle each citation came from:

```
┌─────────────────────────────────────────────────────────┐
│  Answer:                                                 │
│                                                          │
│  Sepsis management involves early recognition [1],       │
│  IV antibiotic administration within 1 hour [2], and    │
│  nursing assessment q15 minutes during resuscitation [3].│
│                                                          │
│  ─────────────────────────────────────────────────────  │
│                                                          │
│  📚 Source Protocols:                                    │
│  ┌──────────────────────────────────────────────────────┐│
│  │ [1] Sepsis Bundle Protocol                           ││
│  │     📋 Practice Protocols                            ││
│  │                                                       ││
│  │ [2] Antibiotic Administration Guidelines             ││
│  │     📋 Practice Protocols                            ││
│  │                                                       ││
│  │ [3] Sepsis Nursing Assessment Checklist              ││
│  │     🏥 Nursing Protocols  ← Different bundle!        ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Multi-Bundle Query Implementation

**Option A: Parallel Corpus Queries (Recommended)**
Query each bundle's corpus in parallel, merge and re-rank results.

```python
async def query_multiple_bundles(
    query: str,
    bundle_ids: List[str],  # ["practice", "nursing"] or ["all"]
    org_id: str
) -> QueryResult:
    # Resolve "all" to list of all accessible bundle IDs
    if "all" in bundle_ids:
        bundle_ids = get_user_accessible_bundles(org_id, user)
    
    # Query each bundle's corpus in parallel
    tasks = []
    for bundle_id in bundle_ids:
        corpus_id = get_bundle_corpus_id(org_id, bundle_id)
        tasks.append(query_single_corpus(query, corpus_id, bundle_id))
    
    # Wait for all queries to complete
    results = await asyncio.gather(*tasks)
    
    # Merge results, keeping top N by relevance score
    merged = merge_and_rank_results(results, top_n=5)
    
    # Generate unified answer from merged contexts
    answer = await generate_answer(query, merged.contexts)
    
    return QueryResult(
        answer=answer,
        citations=merged.citations,  # Each citation has bundle_id
        images=merged.images
    )
```

**Option B: Metadata Filtering (Single Corpus per Org)**
Less recommended, but simpler - all docs in one corpus with bundle metadata.

```python
# Filter by bundle_id metadata
result = rag_corpus.query(
    query=query,
    filter={"bundle_id": {"$in": bundle_ids}}
)
```

### API Endpoint Changes

```python
# Request now supports multiple bundles
class QueryRequest(BaseModel):
    query: str
    bundle_ids: List[str] = ["default"]  # Single bundle OR multiple OR ["all"]

# Example requests:
# Single bundle:  {"query": "STEMI", "bundle_ids": ["practice"]}
# Multi-bundle:   {"query": "sepsis", "bundle_ids": ["practice", "nursing"]}
# All bundles:    {"query": "sepsis", "bundle_ids": ["all"]}

@app.post("/query")
async def query_protocols(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    # Validate user has access to requested bundles
    for bundle_id in request.bundle_ids:
        if bundle_id != "all" and bundle_id not in current_user.bundle_access:
            raise HTTPException(403, f"No access to bundle: {bundle_id}")
    
    # Query across bundles
    result = await rag_service.query_multiple_bundles(
        query=request.query,
        bundle_ids=request.bundle_ids,
        org_id=current_user.org_id
    )
    return result
```

### Frontend Bundle State

```typescript
// Selected bundles stored in React state
// Can be a single bundle, multiple, or "all"
const [selectedBundles, setSelectedBundles] = useState<string[]>(["practice"]);

// UI helper for display
const isAllBundles = selectedBundles.includes("all");
const bundleLabel = isAllBundles 
  ? "All Bundles" 
  : selectedBundles.length === 1 
    ? bundles.find(b => b.id === selectedBundles[0])?.name 
    : `${selectedBundles.length} Bundles`;

// Query includes selected bundles
const handleQuery = async (query: string) => {
  const response = await fetch('/api/query', {
    method: 'POST',
    body: JSON.stringify({
      query,
      bundle_ids: selectedBundles  // ["practice"] or ["practice", "nursing"] or ["all"]
    }),
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  const data = await response.json();
  // Each citation includes bundle_id for badge display
  // data.citations = [{ title: "...", bundle_id: "practice", bundle_name: "Practice Protocols" }]
};

// Bundle selector component
<BundleSelector
  bundles={userBundles}
  selected={selectedBundles}
  onChange={setSelectedBundles}
  allowMultiple={true}
  showAllOption={true}
/>
```

---

## 🛠️ Implementation Phases

### Phase 1: Basic Auth (Week 1)
- [ ] Set up Firebase Auth
- [ ] Create login/signup pages
- [ ] Protect /query endpoint with JWT validation
- [ ] Add org_id to user claims
- [ ] Create seed org for testing

### Phase 2: Admin Dashboard (Week 2)
- [ ] Build admin layout with navigation
- [ ] Protocol list view (from Firestore)
- [ ] Upload UI with drag-and-drop
- [ ] Delete protocol functionality
- [ ] Processing status indicators

### Phase 3: Multi-Tenant RAG (Week 2-3)
- [ ] Create RAG corpus per org
- [ ] Update upload pipeline to use org corpus
- [ ] Scope queries to org corpus
- [ ] Test org isolation

### Phase 4: User Management (Week 3)
- [ ] User invite flow
- [ ] User list for admins
- [ ] Role management (admin/user)
- [ ] Domain-restricted signup (optional)

### Phase 5: Polish (Week 4)
- [ ] Analytics dashboard
- [ ] Org settings page
- [ ] Logo/branding upload
- [ ] Usage limits and quotas

---

## 🔒 Security Checklist

- [ ] All API endpoints validate JWT
- [ ] org_id extracted from token, never from request body
- [ ] RAG queries scoped to org's corpus only
- [ ] Cloud Storage rules enforce org isolation
- [ ] Firestore rules enforce org isolation
- [ ] Admin actions logged for audit
- [ ] No cross-org data access possible
- [ ] Invite tokens expire after 7 days
- [ ] Password requirements enforced

---

## 📊 Database Schema (Firestore Security Rules)

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // Users can read their own profile
    match /users/{userId} {
      allow read: if request.auth.uid == userId;
      allow write: if false; // Admin SDK only
    }
    
    // Org members can read org data
    match /organizations/{orgId} {
      allow read: if request.auth.token.org_id == orgId;
      
      // Only admins can write
      allow write: if request.auth.token.org_id == orgId 
                   && request.auth.token.role == 'admin';
      
      // Protocols: same rules
      match /protocols/{protocolId} {
        allow read: if request.auth.token.org_id == orgId;
        allow write: if request.auth.token.org_id == orgId 
                     && request.auth.token.role == 'admin';
      }
      
      // Users in org
      match /users/{userId} {
        allow read: if request.auth.token.org_id == orgId;
        allow write: if request.auth.token.org_id == orgId 
                     && request.auth.token.role == 'admin';
      }
    }
  }
}
```

---

## 💰 Subscription Tiers (Future)

| Feature | Free | Professional | Enterprise |
|---------|------|--------------|------------|
| Protocols | 5 | 50 | Unlimited |
| Users | 3 | 25 | Unlimited |
| Queries/month | 100 | 5,000 | Unlimited |
| SSO/SAML | ❌ | ❌ | ✅ |
| Custom branding | ❌ | ✅ | ✅ |
| Analytics | Basic | Full | Full + API |
| Support | Community | Email | Dedicated |

---

## 🚀 Quick Start Commands

```bash
# Create new organization
gcloud firestore documents create \
  organizations/memorial-hospital \
  --data '{"name": "Memorial Hospital", "subscription_tier": "professional"}'

# Create RAG corpus for org
gcloud ai rag-corpora create \
  --display-name="memorial-hospital-protocols" \
  --location=us-west4

# Invite first admin
firebase auth:import users.json --hash-algo=BCRYPT
```

---

## Next Steps

1. **Decide on auth approach**: Firebase Auth vs. Auth0 vs. custom
2. **Design admin UI mockups**: Figma or similar
3. **Set up Firebase project**: Enable Auth, Firestore rules
4. **Create first organization**: Seed data for testing
5. **Build login flow**: Before admin dashboard

---

**Created**: February 4, 2026
**Status**: Planning
**Owner**: @derickjones
