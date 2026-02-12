# Azure AD Enterprise Application Approval Request

---

**Date:** February 11, 2026

**Requestor:** Derick Jones (jones.derick@mayo.edu)

**Department:** Emergency Medicine

**Request Type:** Azure AD Third-Party Application Consent

---

## Application Details

| Field | Value |
|-------|-------|
| **Application Name** | EM Protocol App |
| **Application Type** | Web Application (SPA) |
| **Publisher** | Emergency Medicine App (Internal Clinical Tool) |
| **Authentication Method** | Microsoft Identity Platform (OAuth 2.0 / OpenID Connect) |
| **Azure AD Tenant** | Common (Multi-tenant) |
| **Application URL** | https://em-app-protocols.vercel.app |
| **Firebase Project ID** | clinical-assistant-457902 |

---

## Purpose & Business Justification

The EM Protocol App is a clinical decision support tool designed for Emergency Medicine physicians and staff. It provides:

- **Rapid access to evidence-based clinical protocols** for emergency medical procedures
- **AI-powered search** across institutional protocol libraries using Retrieval-Augmented Generation (RAG)
- **Centralized protocol management** for ED leadership to upload, organize, and distribute clinical guidelines — administrators can upload protocol PDFs directly, via URL, or from OneDrive
- **Multi-site support** for institutions with multiple Emergency Departments

This tool improves clinical workflow efficiency by providing instant, searchable access to approved institutional protocols at the point of care.

---

## Permissions Requested

The application requests the following permissions through Microsoft Sign-In:

| Permission | Type | Purpose |
|------------|------|---------|
| `openid` | Delegated | Standard OpenID Connect sign-in |
| `profile` | Delegated | Read user's basic profile (name) |
| `email` | Delegated | Read user's email address |
| `Files.Read` | Delegated | Allow admins to select and upload protocol documents from OneDrive |

### File Access Details

Authorized administrators use the application to upload approved clinical protocol documents (PDFs) to the platform. The app supports multiple upload methods to accommodate corporate device restrictions:

1. **OneDrive File Picker** — Admins can browse and select protocol PDFs stored in their OneDrive. The app uses the Microsoft OneDrive Picker SDK to allow file selection. Only files explicitly chosen by the user are accessed — the app does not browse, index, or access any other files.

2. **URL Upload** — Admins can paste a direct link to a protocol PDF (e.g., a OneDrive or SharePoint sharing link). The backend fetches the file from the provided URL.

3. **Direct File Upload** — Standard file picker upload from the local device.

**Important:** File access is limited to:
- ✅ Only files explicitly selected by the administrator
- ✅ Only PDF documents (clinical protocols and guidelines)
- ✅ Read-only access — the app does not modify, delete, or write to OneDrive
- ❌ No background or automatic file access
- ❌ No access to Mail, Calendar, Teams, or Contacts
- ❌ No access to SharePoint sites or lists beyond user-shared links
- ❌ No directory data or organizational info
- ❌ No on-premises resources

---

## Security & Compliance

| Aspect | Detail |
|--------|--------|
| **Data Storage** | Google Cloud Platform (GCP), US regions only |
| **Authentication** | Firebase Authentication via Microsoft Identity Platform |
| **Data in Transit** | TLS 1.2+ encryption (HTTPS only) |
| **Data at Rest** | AES-256 encryption (GCP default) |
| **PHI/PII** | No patient data is stored or transmitted. The application only contains institutional clinical protocols and guidelines (non-PHI). Uploaded documents are standardized procedure protocols, not patient records. |
| **HIPAA** | Not applicable — no PHI is processed |
| **User Data Stored** | Email address, display name, and role assignment only |

---

## Technical Architecture

```
User Browser → em-app-protocols.vercel.app (Frontend)
                    ↓
              Microsoft Login (login.microsoftonline.com)
                    ↓
              Firebase Authentication (Token Validation)
                    ↓
              Cloud Run API (em-protocol-api, us-central1)
                    ↓
              Google Cloud Storage (Protocol Documents)
```

- **Frontend:** Next.js application hosted on Vercel
- **Backend API:** FastAPI on Google Cloud Run
- **Authentication:** Firebase Auth with Microsoft Identity Provider
- **Storage:** Google Cloud Storage (clinical protocol PDFs and extracted text)

---

## Action Requested

Please grant **tenant-wide admin consent** for the "EM Protocol App" in the Mayo Clinic Azure AD tenant. This can be done via:

1. **Azure AD Admin Portal** → Enterprise Applications → Admin consent requests
2. Or directly at: `https://login.microsoftonline.com/{tenant-id}/adminconsent?client_id={app-client-id}`

This will allow Mayo Clinic users with authorized email domains to sign in to the application using their existing Mayo credentials via Single Sign-On (SSO).

---

## Contact Information

**Requestor:** Derick Jones
**Email:** jones.derick@mayo.edu
**Role:** Application Developer / Emergency Medicine

---

*This application is currently in active development and pilot testing with Emergency Medicine staff. Admin consent will enable seamless SSO for all authorized Mayo Clinic users.*
