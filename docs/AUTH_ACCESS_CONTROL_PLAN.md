# Auth & Access Control Plan

## Overview

Mayo-gated authentication system using Firebase Auth with Google Sign-In. Two paths to access: auto-approved Mayo Google accounts and trust-based owner approval for personal Gmail users.

---

## Login Flow

```
User arrives at login page
│
├─ Clicks "Sign in with Google"
│   ├─ @mayo.edu email → ✅ Auto-approved, full access
│   │
│   └─ non-mayo email (e.g. personal Gmail)
│       ├─ ✅ Signed in (authenticated) but ❌ no app access
│       ├─ Sees the "Mayo Bundle" section with "Request Access"
│       ├─ Enters Name + @mayo.edu email
│       ├─ Owner approves on trust (name + email look legit)
│       ├─ That Google account gets linked/approved
│       └─ User can now access the app with that same Gmail
│
└─ Not signed in → Must sign in with Google first
    (no anonymous request access)
```

---

## Flow 1: Google Sign-In with @mayo.edu (Primary)

1. User clicks **"Sign in with Google"**
2. Firebase Auth completes OAuth
3. Backend checks email domain:
   - **`@mayo.edu`** → Auto-approve, set role to `user`, let them in
   - **Anything else** → Authenticated but no app access; show Mayo Bundle section
4. On first @mayo.edu login, create a Firestore user doc with their info + role

---

## Flow 2: Request Access (Non-Mayo Google Account)

**When shown:** After signing in with a non-`@mayo.edu` Google account. Displayed under a "Mayo Bundle" section on the login/landing page.

**Requires:** User must be signed in with Google (any account). No anonymous requests.

### Form Fields

| Field | Validation |
|-------|-----------|
| **Full Name** | Required |
| **Mayo Email** | Required, must end in `@mayo.edu` |

### UX Details

- Client-side validation: reject non-`@mayo.edu` emails with inline error: *"Please enter your @mayo.edu email address"*
- On submit → create a Firestore access request doc with status `pending`
- Show confirmation: *"Your request has been submitted. Please allow 3-5 business days for approval. You'll be able to access the app once approved."*
- Trigger an **in-app notification** for all owners

### Key Detail

Access is tied to the **Google account they signed in with** (e.g. personal Gmail), not the `@mayo.edu` email in the form. The owner approves on trust that the person behind the Gmail is who they claim to be.

---

## Flow 3: Owner Approval (at `/owner`)

### What Owners See

- A **"Pending Requests"** section with a badge count
- Each request shows:

| Signed-in Account | Claimed Mayo Email | Name | Date | Action |
|---|---|---|---|---|
| john.smith@gmail.com | john.smith@mayo.edu | Dr. John Smith | 2026-03-05 | ✅ ❌ |

- **Approve** → sets user role to `user`, they can access the app on next login
- **Deny** → updates request status to `denied`

### Approval is Trust-Based

No email verification (Mayo blocks verification links). Owner reviews the signed-in Google account vs. the claimed Mayo email + name and makes a judgment call.

---

## Role System

| Role | Access | Managed At |
|------|--------|-----------|
| **Owner** | Full control + manage admins + approve/deny access requests | `/owner` |
| **Admin** | Manage content + see notifications about new requests | `/admin` |
| **User** | View protocols, use RAG search | Auto on @mayo.edu login or owner approval |
| **Pending** | Authenticated but no app access (waiting for owner approval) | `/owner` |

**Storage:** Firebase Auth **custom claims** for role (`owner`, `admin`, `user`). Gates routes on both frontend (Next.js middleware) and backend (API auth checks).

---

## Firestore Collections

### `users/{uid}`

Created on first approved login (auto or manual).

```
email: "smith@mayo.edu"
name: "Dr. Smith"
role: "user" | "admin" | "owner"
created_at: timestamp
last_login: timestamp
```

### `access_requests/{auto_id}`

Created from the Request Access form.

```
google_email: "john.smith@gmail.com"       ← from Firebase Auth (actual login)
google_uid: "abc123"                        ← from Firebase Auth
mayo_email: "john.smith@mayo.edu"           ← from the form (claimed)
name: "Dr. John Smith"                      ← from the form
status: "pending" | "approved" | "denied"
requested_at: timestamp
reviewed_by: "owner-uid"                    (nullable)
reviewed_at: timestamp                      (nullable)
```

### `notifications/{auto_id}`

In-app alerts for owners.

```
type: "access_request"
message: "New access request from john.smith@gmail.com"
target_role: "owner"
read: false
created_at: timestamp
reference_id: "{access_request_id}"
```

---

## In-App Notification System

- New access request → write a notification doc targeting `owner` role
- Owner dashboard uses Firestore `onSnapshot` listener for real-time badge count
- Badge on `/owner` nav item: **"Requests (3)"**
- Clicking navigates to pending requests section
- Approving/denying clears the notification

---

## What Needs Building

| Component | Where | What |
|-----------|-------|------|
| Login page update | `frontend/app/login/` | Add Mayo Bundle section + Request Access form |
| Domain gate on Google sign-in | `frontend/lib/auth-context.tsx` + API | Check `@mayo.edu` after OAuth, auto-approve or show request form |
| Access request API endpoint | `api/main.py` | `POST /access-requests` |
| Owner approval UI | `frontend/app/owner/` | Pending requests list with approve/deny |
| Owner approval API | `api/main.py` | `PATCH /access-requests/{id}` |
| Custom claims setup | `api/auth_service.py` | Set roles via Firebase Admin SDK |
| Notification writes | `api/` | On new request, write notification doc |
| Notification reads | `frontend/app/owner/` | Badge count + list via Firestore listener |
| Route protection | `frontend/` middleware or layout | Gate `/admin`, `/owner` by role |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auto-approve @mayo.edu Google sign-in | ✅ Yes | Zero friction for Mayo staff |
| Email verification for request flow | ❌ No | Mayo blocks verification links |
| Approval method | Trust-based by owner | Owner sees Google account + claimed Mayo email, judges legitimacy |
| Must be signed in to request access | ✅ Yes | Prevents spam, ties request to a real Google account |
| Notification delivery | In-app only | No email dependency |
| Approval timeline messaging | 3-5 business days | Sets honest expectations |
| Role storage | Firebase Auth custom claims | Works on both frontend and backend |
| Access request management | `/owner` only for now | Can expand to `/admin` later |
