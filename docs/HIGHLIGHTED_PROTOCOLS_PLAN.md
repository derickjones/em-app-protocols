# Admin-Highlighted Protocols — Implementation Plan

## Overview
Allow admins/practice leadership to "highlight" specific protocols so they appear prominently for all users in their enterprise below the search bar — separate from personal favorites.

**Use cases:**
- New protocols just published (e.g., "Updated Sepsis Bundle — please review")
- Seasonal or timely protocols (e.g., "Heat Stroke" in summer, "Frostbite" in winter)
- High-frequency protocols leadership wants easy access to (e.g., "Stroke Alert")
- Protocols flagged after quality reviews / M&M conferences

---

## Current Architecture

### Data Model (Firestore)
```
enterprises/
  {enterprise_id}/                    ← "mayo-clinic"
    eds/
      {ed_id}/                        ← "rochester"
        bundles/
          {bundle_id}/                ← "acls"
```

### Protocols (GCS)
```
{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}/
  metadata.json      ← { protocol_id, org_id, page_count, char_count, image_count, images[] }
  extracted_text.txt
  page_*.png
```

### Auth Roles
- `user` — regular clinician, can view/search protocols
- `admin` — enterprise admin, can upload/delete protocols, manage users
- `super_admin` — system admin, can manage all enterprises

### Existing Favorites (localStorage)
- Personal per-user favorites stored in `localStorage` under `em-protocol-favorites`
- Stored as full `ProtocolCardData[]` (includes protocol_id, enterprise_id, ed_id, bundle_id, summary, pdf_url, images)
- Displayed in a list-style card below the search bar on the initial view

---

## Design: Highlighted Protocols

### Where It Lives

**Option A (Recommended): Firestore document per enterprise**  
Store highlighted protocols at the enterprise level so they apply to all users.

```
enterprises/{enterprise_id}/highlighted_protocols (subcollection)
  {protocol_id}/
    protocol_id: string
    enterprise_id: string
    ed_id: string
    bundle_id: string
    highlighted_by: string        ← uid of admin who highlighted it
    highlighted_at: timestamp
    label: string | null          ← optional badge text, e.g. "NEW", "Updated", "Review Required"
    priority: number              ← ordering (lower = higher priority)
    expires_at: timestamp | null  ← optional auto-expiration
```

**Why subcollection vs. array field:**
- No 1MB document size limit concern
- Easy to add/remove individual protocols without read-modify-write race conditions
- Can query/sort by highlighted_at, priority
- Scales to 100+ highlighted protocols if needed

### Frontend Display

**Below search bar, ABOVE personal favorites:**

```
┌──────────────────────────────────────────────────┐
│  🔖  Highlighted by Your Practice                │
│──────────────────────────────────────────────────│
│  Sepsis Bundle 2025                    NEW   ›   │
│──────────────────────────────────────────────────│
│  Stroke Alert Algorithm                      ›   │
│──────────────────────────────────────────────────│
│  Pediatric RSI Checklist          UPDATED    ›   │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  ⭐  Favorited Protocols                         │
│──────────────────────────────────────────────────│
│  ACLS Cardiac Arrest                         ›   │
│──────────────────────────────────────────────────│
│  Tranexamic Acid Protocol                    ›   │
└──────────────────────────────────────────────────┘
```

**Visual differentiation from personal favorites:**
- Different icon: 🔖 bookmark (or `Bookmark` from lucide-react) vs ⭐ star
- Different accent color: blue/indigo border-left or subtle gradient vs neutral
- Optional colored badges: `NEW` (green), `UPDATED` (blue), `REVIEW` (amber)
- Header text: "Highlighted by Your Practice" (enterprise-scoped)

### Admin UI (Admin Page)

Add a new tab/section in the existing admin page (`/admin`):

**Option 1: Toggle on existing browse view**  
In the browse protocols tree, add a "spotlight" toggle button next to each protocol. Clicking it highlights/un-highlights the protocol.

**Option 2 (Recommended): New "Highlighted" management section**  
A dedicated section where admins can:
1. Search/browse protocols to highlight
2. Add optional label and priority
3. Set optional expiration date
4. See currently highlighted protocols with drag-reorder
5. Remove highlights

---

## Implementation Steps

### Phase 1: Backend API (api/main.py)

**New endpoints:**

```python
# GET  /enterprise/highlighted
#   → Returns highlighted protocols for the user's enterprise
#   → Public for all authenticated users

# POST /enterprise/highlighted
#   → Highlight a protocol (admin/super_admin only)
#   → Body: { protocol_id, ed_id, bundle_id, label?, priority?, expires_at? }

# DELETE /enterprise/highlighted/{protocol_id}
#   → Remove highlight (admin/super_admin only)

# PATCH /enterprise/highlighted/{protocol_id}
#   → Update label, priority, or expiration (admin/super_admin only)
```

**Implementation details:**
- Read from `enterprises/{eid}/highlighted_protocols` subcollection
- On GET, also fetch protocol metadata from GCS (images, summary, pdf_url) to return full `ProtocolCardData`-compatible objects
- Auto-filter expired highlights (where `expires_at < now`)
- Sort by priority ASC, then highlighted_at DESC

### Phase 2: Frontend — User-Facing Display (page.tsx)

1. Add `highlightedProtocols` state (similar to `favoriteProtocols`)
2. Fetch from `GET /enterprise/highlighted` after enterprise loads
3. Render the "Highlighted by Your Practice" card above the personal favorites section
4. Same list-row UX (click → auto-search for that protocol)
5. Show badge labels (NEW, UPDATED, etc.) in colored pills on each row

### Phase 3: Frontend — Admin Management (admin/page.tsx)

1. Add "Highlighted" tab or section
2. Show currently highlighted protocols with:
   - Protocol name, label badge, priority
   - Edit button (change label/priority/expiry)
   - Remove button
3. "Add Highlight" button:
   - Opens protocol picker (search through enterprise protocols)
   - Label text input (optional, e.g., "NEW")
   - Priority number input
   - Optional expiration date picker
4. Drag-to-reorder for priority (stretch goal)

### Phase 4: Polish & Edge Cases

- **Expiration cleanup:** Cron or Cloud Function to delete expired highlights
  (or just filter on read — simpler for MVP)
- **Notification dot:** Show a subtle indicator in sidebar when new protocols are highlighted since user's last visit (stretch)
- **Max limit:** Cap at ~20 highlighted protocols per enterprise to prevent abuse
- **Permissions guard:** Only `admin` and `super_admin` can write; all authenticated enterprise users can read

---

## File Changes Summary

| File | Changes |
|------|---------|
| `api/main.py` | Add 4 endpoints: GET/POST/DELETE/PATCH `/enterprise/highlighted` |
| `frontend/app/page.tsx` | Add `highlightedProtocols` state, fetch on mount, render card above favorites |
| `frontend/app/admin/page.tsx` | Add "Highlighted Protocols" management section |
| `api/seed_database.py` | (optional) Seed sample highlighted protocols for demo |

---

## Firestore Security Rules Consideration

```
match /enterprises/{entId}/highlighted_protocols/{docId} {
  allow read: if request.auth != null;
  allow write: if get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role in ['admin', 'super_admin'];
}
```

---

## Estimated Effort

| Phase | Effort |
|-------|--------|
| Phase 1: Backend API | ~1-2 hours |
| Phase 2: Frontend display | ~1 hour |
| Phase 3: Admin management | ~2-3 hours |
| Phase 4: Polish | ~1 hour |
| **Total** | **~5-7 hours** |

---

## Open Questions

1. **Scope:** Should highlights be per-enterprise (all EDs see them) or per-ED? 
   → Recommend: Per-enterprise for MVP, add ED-scoping later if needed.

2. **Who can highlight?** Only `admin` + `super_admin`, or also "medical director" role?
   → Recommend: `admin` + `super_admin` for MVP. Can add a `medical_director` role later.

3. **Badge labels:** Free-text or predefined set (NEW, UPDATED, REVIEW, URGENT)?
   → Recommend: Free-text with suggested defaults for flexibility.

4. **Notifications:** Should users be notified when new protocols are highlighted?
   → Recommend: Defer to Phase 4 stretch goal.
