# 🏢 Multi-Tenant Admin & Content Management Plan

## Overview

This document outlines how administrators upload and manage protocols, and how users in different healthcare organizations access their organization's content securely.

---

## 🎯 Goals

1. **Organization Isolation** - Each healthcare org sees only their protocols
2. **Role-Based Access** - Admins manage content, users query it
3. **Simple Onboarding** - Easy for new orgs to get started
4. **Secure by Default** - HIPAA-compliant from day one
5. **Scalable** - Support 100s of organizations

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
  - rag_corpus_id: "123456789"  // Vertex AI RAG corpus for this org
  - created_at: timestamp
  - settings: {
      allow_user_signup: false,
      require_email_domain: "@memorial.org",
      max_protocols: 100
    }

  /protocols/{protocolId}
    - title: "ACLS Cardiac Arrest Algorithm"
    - filename: "ACLS_2025.pdf"
    - uploaded_by: "userId"
    - upload_date: timestamp
    - status: "ready" | "processing" | "failed"
    - page_count: 12
    - image_count: 5
    - category: "Cardiac"
    - tags: ["ACLS", "cardiac arrest", "CPR"]
    - pdf_url: "gs://protocols-raw/memorial-hospital/..."
    - last_updated: timestamp

  /users/{userId}
    - email: "dr.smith@memorial.org"
    - display_name: "Dr. Sarah Smith"
    - role: "admin" | "user"
    - created_at: timestamp
    - last_login: timestamp
    - invited_by: "adminUserId"

/users/{userId}  // Top-level for auth lookup
  - org_id: "memorial-hospital"
  - email: "dr.smith@memorial.org"
  - role: "admin"
```

### Storage Structure

```
Cloud Storage:
├── protocols-raw/
│   └── {org-id}/
│       └── {protocol-id}.pdf
│
├── protocols-processed/
│   └── {org-id}/
│       └── {protocol-id}/
│           ├── extracted_text.txt
│           ├── metadata.json
│           └── images/
│               ├── page_1_img_1.png
│               └── page_2_img_1.png
│
└── org-assets/
    └── {org-id}/
        └── logo.png
```

### RAG Corpus Strategy

**Option A: One Corpus Per Organization** ✅ Recommended
- Complete data isolation
- Easy to delete org data
- Slight overhead for corpus management
- Each org has their own `rag_corpus_id`

**Option B: Single Corpus with Metadata Filtering**
- All docs in one corpus with `org_id` metadata
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

### UI: Admin Dashboard

```
┌─────────────────────────────────────────────────────────┐
│  Memorial Hospital - Admin Dashboard                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [📁 Protocols]  [👥 Users]  [📊 Analytics]  [⚙️ Settings]│
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │  📤 Upload New Protocol                              ││
│  │  ┌─────────────────────────────────────────────────┐││
│  │  │  Drag & drop PDF here or click to browse        │││
│  │  │                                                  │││
│  │  │         [Choose File]                           │││
│  │  └─────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
│  📋 Current Protocols (24)                               │
│  ┌──────────────────────────────────────────────────────┐│
│  │ ✅ ACLS Cardiac Arrest 2025    │ 12 pages │ Delete  ││
│  │ ✅ Sepsis Bundle Protocol      │  8 pages │ Delete  ││
│  │ ⏳ Stroke Protocol (processing)│    --    │ Cancel  ││
│  │ ✅ Trauma Algorithm            │ 15 pages │ Delete  ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Upload Processing Pipeline

```
1. Admin selects PDF file
2. Frontend validates:
   - File type (PDF only)
   - File size (< 50MB)
   - Org hasn't hit protocol limit
   
3. Frontend uploads to Cloud Storage:
   gs://protocols-raw/{org-id}/{protocol-id}.pdf
   
4. Frontend creates Firestore doc:
   /organizations/{org-id}/protocols/{protocol-id}
   status: "processing"
   
5. Cloud Function triggered by GCS upload:
   a. Extract text with Document AI
   b. Extract images
   c. Store processed content
   d. Add to org's RAG corpus
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

## 🔍 User Query Flow (Multi-Tenant)

```
1. User sends query: "STEMI treatment"
2. API receives request with JWT token
3. Backend extracts org_id from token: "memorial-hospital"
4. Backend looks up org's rag_corpus_id
5. Query ONLY that org's RAG corpus
6. Return results with org-specific citations
7. User sees only their org's protocols
```

### API Endpoint Changes

```python
# Current (single tenant)
@app.post("/query")
async def query_protocols(request: QueryRequest):
    result = rag_service.query(request.query)
    return result

# Multi-tenant version
@app.post("/query")
async def query_protocols(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)  # From JWT
):
    # Get org's RAG corpus
    org = get_organization(current_user.org_id)
    
    # Query org-specific corpus
    result = rag_service.query(
        query=request.query,
        corpus_id=org.rag_corpus_id
    )
    return result
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
