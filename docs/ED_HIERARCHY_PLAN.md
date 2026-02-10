# 🏥 Enterprise → ED → Bundle Hierarchy Plan

## Overview

Restructure the protocol hierarchy from flat org-based to a 3-level model:
**Enterprise → ED → Bundle → Protocol**

---

## Hierarchy

```
Enterprise (Hospital System)          ← User logs into this via domain
├── ED: Rochester                     ← User selects one or more EDs
│   ├── Bundle: acls
│   └── Bundle: jit-education
├── ED: Phoenix
│   ├── Bundle: acls
│   └── Bundle: jit-education
└── ED: Jacksonville
    └── Bundle: acls
```

### Current Mayo Clinic data
```
Mayo Clinic (Enterprise: mayo-clinic)
└── Rochester (ED: rochester)
    ├── acls (Bundle)
    │   ├── Algorithm-ACLS-Bradycardia-250514
    │   ├── Algorithm-ACLS-CA-250527
    │   ├── Algorithm-ACLS-CA-Circular-250620
    │   ├── Algorithm-ACLS-Electrical-Cardioversion-250514
    │   ├── Algorithm-ACLS-Tachycardia-250514
    │   ├── Algorithm-ALS-Termination-of-Resusc-250514
    │   └── Algorithm-BLS-Termination-of-Resusc-250514
    └── jit-education (Bundle)
        ├── Arthrocentesis_QRG
        ├── Chest_Tube_QRG
        ├── Lumbar_Puncture_QRG
        ├── Minnesota_Tube_QRG
        ├── Paracentesis_QRG
        ├── Pediatric_Chest_Tube_QRG
        ├── Pericardiocentesis_QRG
        ├── Pigtail_Chest_Tube_QRG
        ├── Thoracentesis_QRG
        └── Transvenous_Pacing_QRG
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hierarchy | Enterprise → ED → Bundle (3 levels) | Simple, matches real-world structure |
| Enterprise = ? | Hospital system (e.g., Mayo Clinic) | User logs in via domain |
| User ED visibility | All EDs in enterprise by default | Can select one or many to search |
| ED bundle sharing | Each ED has its own bundles | Different EDs may differ |
| RAG corpus | Single corpus, filter by path prefix | Simpler, cheaper |
| Admin levels | ED Admin (`/admin`) + Owner (`/owner`) | ED admins manage their ED, owners manage all |
| Upload flow | Admin picks ED, then bundle | Clear which ED gets the protocol |

---

## GCS Path Structure

### Current
```
gs://clinical-assistant-457902-protocols-processed/
└── mayo-clinic-rochester/              ← flat org_id
    ├── acls/
    │   └── {protocol_id}/
    │       ├── metadata.json
    │       ├── extracted_text.txt
    │       └── images/
    └── jit-education/
        └── {protocol_id}/
```

### New
```
gs://clinical-assistant-457902-protocols-processed/
└── mayo-clinic/                        ← enterprise_id
    └── rochester/                      ← ed_id
        ├── acls/                       ← bundle_id
        │   └── {protocol_id}/
        │       ├── metadata.json
        │       ├── extracted_text.txt
        │       └── images/
        └── jit-education/
            └── {protocol_id}/
```

**Path format:** `{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}/`

---

## Firestore Schema

### Current
```
organizations/{org_id}
  - name, slug, allowed_domains, default_bundles

users/{uid}
  - email, org_id, org_name, role, bundle_access
```

### New
```
enterprises/{enterprise_id}
  - name: "Mayo Clinic"
  - slug: "mayo-clinic"
  - allowed_domains: ["mayo.edu", "mayo.org", "gmail.com"]
  - subscription_tier: "enterprise"
  - settings: { allow_user_signup: true, max_protocols: 500 }

enterprises/{enterprise_id}/eds/{ed_id}
  - name: "Rochester"
  - slug: "rochester"
  - location: "Rochester, MN"  (optional)

enterprises/{enterprise_id}/eds/{ed_id}/bundles/{bundle_id}
  - name: "ACLS"
  - slug: "acls"
  - description: "Advanced Cardiac Life Support"
  - icon: "heart"
  - color: "#EF4444"
  - protocol_count: 7

users/{uid}
  - email: "doc@mayo.edu"
  - enterprise_id: "mayo-clinic"
  - enterprise_name: "Mayo Clinic"
  - role: "user" | "ed_admin" | "owner" | "super_admin"
  - ed_access: ["rochester"]     ← EDs user can access (default: all)
  - created_at: ...
```

### Role Hierarchy

| Role | Scope | Can do |
|------|-------|--------|
| `super_admin` | System-wide | Manage all enterprises (your team) |
| `owner` | Enterprise-wide | Manage all EDs/admins in their enterprise (`/owner`) |
| `ed_admin` | Per-ED | Upload/delete protocols, manage users in their ED(s) (`/admin`) |
| `user` | Per-ED | Query protocols in their assigned ED(s) |

---

## API Changes

### Updated query request

```json
{
  "query": "STEMI treatment",
  "ed_ids": ["rochester"],
  "bundle_ids": ["acls"],
  "sources": ["local", "wikem"]
}
```

### RAG filtering at query time

```python
# Build GCS path prefixes from user's selected EDs + bundles
selected_prefixes = []
for ed_id in request.ed_ids:
    if request.bundle_ids:
        for bundle_id in request.bundle_ids:
            prefix = f"{user.enterprise_id}/{ed_id}/{bundle_id}/"
            selected_prefixes.append(prefix)
    else:
        # No bundle filter — search all bundles in this ED
        prefix = f"{user.enterprise_id}/{ed_id}/"
        selected_prefixes.append(prefix)

# After RAG retrieval, filter contexts by source URI prefix
filtered = [
    ctx for ctx in contexts
    if any(prefix in ctx["source"] for prefix in selected_prefixes)
]
```

### New/updated endpoints

```
GET  /enterprise                    → Current user's enterprise info + EDs
GET  /enterprise/eds                → List all EDs with their bundles
POST /query                         → Updated: ed_ids replaces hospital selection
POST /admin/protocols/upload        → Updated: requires ed_id + bundle_id
```

---

## Frontend Changes

### Home page layout

```
┌─────────────────────────────────────────┐
│ Mayo Clinic                        [⚙]  │  ← Enterprise (from login)
│                                         │
│ Emergency Departments:                  │
│ [✓ Rochester] [✗ Phoenix] [✗ Jax]      │  ← ED toggle chips
│                                         │
│ [Ask about emergency protocols...]      │  ← Search bar
│                                         │
│ [EM Universe] [Protocol]                │  ← Search mode
│ [acls] [jit-education]                  │  ← Bundle chips (from selected EDs)
└─────────────────────────────────────────┘
```

- Enterprise name in header (auto from login domain)
- ED selector: pill/chip toggles, multi-select
- Bundle chips: show union of bundles across selected EDs
- Persist selected EDs in localStorage

### Admin page (`/admin`)
- ED admin selects which ED they're managing
- Upload flow: pick ED → pick bundle → upload PDF
- Manage protocols within their ED

---

## Migration Steps

### 1. Migrate GCS files
```bash
# Rename from flat to hierarchical
# mayo-clinic-rochester/acls/... → mayo-clinic/rochester/acls/...
gsutil -m cp -r \
  gs://bucket/mayo-clinic-rochester/acls/ \
  gs://bucket/mayo-clinic/rochester/acls/

gsutil -m cp -r \
  gs://bucket/mayo-clinic-rochester/jit-education/ \
  gs://bucket/mayo-clinic/rochester/jit-education/

# Verify, then delete old
gsutil -m rm -r gs://bucket/mayo-clinic-rochester/
```

### 2. Re-index RAG corpus
- Delete old RAG files (old GCS paths)
- Re-import from new GCS paths so source URIs match

### 3. Migrate Firestore
- Create `enterprises/mayo-clinic` from `organizations/mayo-clinic`
- Create `enterprises/mayo-clinic/eds/rochester`
- Move bundles under the ED
- Update user docs: `org_id` → `enterprise_id` + `ed_access: ["rochester"]`
- Keep old `organizations` collection temporarily for rollback

### 4. Update API
- `auth_service.py`: `org_id` → `enterprise_id`, add `ed_access`
- `protocol_service.py`: Update path parsing for new 4-part paths
- `rag_service.py`: Add path-prefix filtering
- `main.py`: Update endpoints, query accepts `ed_ids`

### 5. Update Frontend
- Replace hospital dropdown with ED multi-select chips
- Update bundle chips to union of selected EDs' bundles
- Update query payload with `ed_ids`
- Update admin upload flow with ED picker

### 6. Deploy
- Deploy API to Cloud Run
- Push frontend to Vercel
- Verify queries work with new paths
