"""
Firebase Authentication Service
Handles JWT validation and user management for multi-tenant auth
"""

import os
from typing import Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import google.auth.transport.requests
from google.oauth2 import id_token
from google.cloud import firestore

# Initialize Firestore client
db = firestore.Client(project="clinical-assistant-457902")

# HTTP Bearer scheme for extracting tokens
security = HTTPBearer(auto_error=False)


class UserProfile:
    """User profile with org and bundle access"""
    def __init__(
        self,
        uid: str,
        email: str,
        org_id: Optional[str] = None,
        org_name: Optional[str] = None,
        role: str = "user",
        bundle_access: list = None
    ):
        self.uid = uid
        self.email = email
        self.org_id = org_id
        self.org_name = org_name
        self.role = role
        self.bundle_access = bundle_access or []

    def to_dict(self):
        return {
            "uid": self.uid,
            "email": self.email,
            "orgId": self.org_id,
            "orgName": self.org_name,
            "role": self.role,
            "bundleAccess": self.bundle_access,
        }


def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase ID token and return decoded claims
    """
    try:
        # Verify the token with Google's public keys
        request = google.auth.transport.requests.Request()
        decoded = id_token.verify_firebase_token(
            token,
            request,
            audience="clinical-assistant-457902"
        )
        return decoded
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}"
        )


def check_email_verified(decoded_token: dict) -> bool:
    """
    Check if the user's email is verified.
    Google sign-in users are always verified.
    """
    return decoded_token.get("email_verified", False)


def get_org_by_domain(email_domain: str) -> Optional[dict]:
    """
    Look up organization by email domain
    Returns org data if domain is whitelisted, None otherwise
    """
    # Query organizations where allowed_domains contains this domain
    orgs_ref = db.collection("organizations")
    
    # Check for exact domain match in allowed_domains array
    query = orgs_ref.where("allowed_domains", "array_contains", email_domain)
    results = list(query.stream())
    
    if results:
        org_doc = results[0]
        return {"id": org_doc.id, **org_doc.to_dict()}
    
    return None


def get_or_create_user(decoded_token: dict) -> UserProfile:
    """
    Get existing user or create new user based on domain validation
    """
    uid = decoded_token["uid"]
    email = decoded_token.get("email", "")
    
    # Check if user already exists
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    
    if user_doc.exists:
        # Return existing user
        data = user_doc.to_dict()
        return UserProfile(
            uid=uid,
            email=email,
            org_id=data.get("org_id"),
            org_name=data.get("org_name"),
            role=data.get("role", "user"),
            bundle_access=data.get("bundle_access", [])
        )
    
    # New user - validate domain
    email_domain = email.split("@")[-1] if "@" in email else ""
    org = get_org_by_domain(email_domain)
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Email domain '{email_domain}' is not registered with any organization. Contact your administrator."
        )
    
    # Get default bundles for this org
    default_bundles = org.get("default_bundles", [])
    
    # Create new user
    user_data = {
        "email": email,
        "org_id": org["id"],
        "org_name": org.get("name", ""),
        "role": "user",
        "bundle_access": default_bundles,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    user_ref.set(user_data)
    
    return UserProfile(
        uid=uid,
        email=email,
        org_id=org["id"],
        org_name=org.get("name", ""),
        role="user",
        bundle_access=default_bundles
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserProfile:
    """
    FastAPI dependency to get current authenticated user
    Use this to protect endpoints
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    token = credentials.credentials
    decoded = verify_firebase_token(token)
    user = get_or_create_user(decoded)
    
    return user


async def get_verified_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserProfile:
    """
    FastAPI dependency to get current authenticated AND email-verified user
    Use this for endpoints that require verified email
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    token = credentials.credentials
    decoded = verify_firebase_token(token)
    
    # Check email verification
    if not check_email_verified(decoded):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before accessing this resource"
        )
    
    user = get_or_create_user(decoded)
    
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[UserProfile]:
    """
    FastAPI dependency to optionally get user (for endpoints that work with or without auth)
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        decoded = verify_firebase_token(token)
        return get_or_create_user(decoded)
    except HTTPException:
        return None


def require_bundle_access(user: UserProfile, bundle_id: str):
    """
    Check if user has access to a specific bundle
    Raises 403 if not authorized
    """
    # Super admins have access to everything
    if user.role == "super_admin":
        return
    
    # Check bundle access
    if bundle_id not in user.bundle_access and "all" not in user.bundle_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have access to bundle '{bundle_id}'"
        )


def require_admin(user: UserProfile):
    """
    Check if user is an admin
    """
    if user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
