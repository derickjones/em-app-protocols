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
  - created_at: timestamp
  - settings: {
      allow_user_signup: false,
      require_email_domain: "@memorial.org",
      max_protocols: 100
    }

  /themes/{themeId}  // Content themes within an org
    - name: "Protocols"
    - slug: "protocols"
    - description: "Clinical protocols and guidelines"
    - icon: "clipboard-list"
    - color: "#3B82F6"  // Blue
    - rag_corpus_id: "123456789"  // Each theme has its own RAG corpus
    - is_default: true
    - order: 1
    - created_at: timestamp
    
    /content/{contentId}  // Content items within a theme
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
    - theme_access: ["protocols", "education", "telemed"]  // Which themes user can access
    - created_at: timestamp
    - last_login: timestamp
    - invited_by: "adminUserId"

/users/{userId}  // Top-level for auth lookup
  - org_id: "memorial-hospital"
  - email: "dr.smith@memorial.org"
  - role: "admin"
```

### Example Themes for a Practice

| Theme | Description | Use Case |
|-------|-------------|----------|
| **Protocols** | Clinical guidelines, algorithms | "How do I treat sepsis?" |
| **Education** | Training materials, CME content | "Explain the pathophysiology of DKA" |
| **Telemed** | Telemedicine-specific workflows | "Virtual exam documentation requirements" |
| **Policies** | HR, compliance, procedures | "What's the PTO policy?" |
| **Formulary** | Drug information, dosing | "Pediatric amoxicillin dosing" |

### Theme Toggle UI

```
┌─────────────────────────────────────────────────────────┐
│  Memorial Hospital                                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [📋 Protocols ▼]  ← Theme selector dropdown             │
│   ├─ 📋 Protocols (selected)                             │
│   ├─ 📚 Education                                        │
│   ├─ 🖥️ Telemed                                          │
│   └─ 📜 Policies                                         │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Enter a clinical question...                        ││
│  └─────────────────────────────────────────────────────┘│
│                                                          │
│  Searching: Protocols corpus                             │
└─────────────────────────────────────────────────────────┘
```

### Storage Structure (Updated)

```
Cloud Storage:
├── content-raw/
│   └── {org-id}/
│       └── {theme-id}/
│           └── {content-id}.pdf
│
├── content-processed/
│   └── {org-id}/
│       └── {theme-id}/
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

**Recommended: One Corpus Per Theme Per Organization** ✅

```
Organization: Memorial Hospital
├── Corpus: memorial-protocols     (rag_corpus_id: "111...")
├── Corpus: memorial-education     (rag_corpus_id: "222...")
├── Corpus: memorial-telemed       (rag_corpus_id: "333...")
└── Corpus: memorial-policies      (rag_corpus_id: "444...")
```

**Benefits:**
- Complete data isolation between orgs AND themes
- User switches theme → queries different corpus
- Easy to manage permissions per theme
- Clean deletion (delete corpus = delete all theme content)
- No risk of cross-contamination in search results

**Trade-offs:**
- More corpora to manage
- Slightly higher overhead
- Worth it for clean separation

**Alternative: Single Corpus with Theme Metadata**
- All docs in one corpus with `theme_id` metadata filter
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

### UI: Admin Dashboard (with Themes)

```
┌─────────────────────────────────────────────────────────┐
│  Memorial Hospital - Admin Dashboard                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Theme: [� Protocols ▼]  ← Admin selects which theme   │
│                                                          │
│  [� Content]  [🎨 Themes]  [👥 Users]  [⚙️ Settings]    │
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
│  [🎨 Manage Themes] → Create new themes, edit colors    │
└─────────────────────────────────────────────────────────┘
```

### Theme Management UI (Admin Only)

```
┌─────────────────────────────────────────────────────────┐
│  Manage Themes                                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  [+ Create New Theme]                                    │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐│
│  │ 📋 Protocols    │ 24 items │ Default │ Edit │ Delete││
│  │ 📚 Education    │ 12 items │         │ Edit │ Delete││
│  │ 🖥️ Telemed      │  8 items │         │ Edit │ Delete││
│  │ 📜 Policies     │ 15 items │         │ Edit │ Delete││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  Note: Deleting a theme removes all its content and     │
│  RAG corpus. This cannot be undone.                     │
└─────────────────────────────────────────────────────────┘
```

### Upload Processing Pipeline (with Themes)

```
1. Admin selects theme (e.g., "Protocols")
2. Admin uploads PDF file
3. Frontend validates:
   - File type (PDF only)
   - File size (< 50MB)
   - Theme content limit not exceeded
   
4. Frontend uploads to Cloud Storage:
   gs://content-raw/{org-id}/{theme-id}/{content-id}.pdf
   
5. Frontend creates Firestore doc:
   /organizations/{org-id}/themes/{theme-id}/content/{content-id}
   status: "processing"
   
6. Cloud Function triggered by GCS upload:
   a. Extract text with Document AI
   b. Extract images
   c. Store processed content
   d. Add to theme's RAG corpus (theme.rag_corpus_id)
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

## 🔍 User Query Flow (Multi-Tenant with Themes)

```
1. User selects theme from dropdown: "Protocols"
2. User sends query: "STEMI treatment"
3. API receives request with JWT token + theme_id
4. Backend extracts org_id from token: "memorial-hospital"
5. Backend validates user has access to theme
6. Backend looks up theme's rag_corpus_id
7. Query ONLY that theme's RAG corpus
8. Return results with theme-specific citations
9. User sees only content from selected theme
```

### User Theme Toggle Experience

```
User opens app → Defaults to "Protocols" theme
User queries: "STEMI treatment" → Gets protocol results

User clicks theme dropdown → Selects "Education"
Theme indicator changes: "📚 Education"
User queries: "STEMI pathophysiology" → Gets education content

User switches to "Telemed"
User queries: "Virtual cardiac exam" → Gets telemed workflows
```

### API Endpoint Changes

```python
# Request now includes theme_id
class QueryRequest(BaseModel):
    query: str
    theme_id: str  # Which theme to search

# Multi-tenant + multi-theme version
@app.post("/query")
async def query_protocols(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)  # From JWT
):
    # Validate user has access to this theme
    theme = get_theme(current_user.org_id, request.theme_id)
    if request.theme_id not in current_user.theme_access:
        raise HTTPException(403, "No access to this theme")
    
    # Query theme-specific corpus
    result = rag_service.query(
        query=request.query,
        corpus_id=theme.rag_corpus_id
    )
    return result
```

### Frontend Theme State

```typescript
// Theme stored in React state
const [currentTheme, setCurrentTheme] = useState<Theme>(defaultTheme);

// Query includes theme
const handleQuery = async (query: string) => {
  const response = await fetch('/api/query', {
    method: 'POST',
    body: JSON.stringify({
      query,
      theme_id: currentTheme.id
    }),
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  // ... handle response
};
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
