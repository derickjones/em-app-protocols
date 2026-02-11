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
    """User profile with enterprise and ED access"""
    def __init__(
        self,
        uid: str,
        email: str,
        enterprise_id: Optional[str] = None,
        enterprise_name: Optional[str] = None,
        role: str = "user",
        ed_access: list = None
    ):
        self.uid = uid
        self.email = email
        self.enterprise_id = enterprise_id
        self.enterprise_name = enterprise_name
        self.role = role
        self.ed_access = ed_access or []

    def to_dict(self):
        return {
            "uid": self.uid,
            "email": self.email,
            "enterpriseId": self.enterprise_id,
            "enterpriseName": self.enterprise_name,
            "role": self.role,
            "edAccess": self.ed_access,
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


def get_enterprise_by_domain(email_domain: str) -> Optional[dict]:
    """
    Look up enterprise by email domain
    Returns enterprise data if domain is whitelisted, None otherwise
    """
    # Query enterprises where allowed_domains contains this domain
    enterprises_ref = db.collection("enterprises")
    
    # Check for exact domain match in allowed_domains array
    query = enterprises_ref.where("allowed_domains", "array_contains", email_domain)
    results = list(query.stream())
    
    if results:
        enterprise_doc = results[0]
        return {"id": enterprise_doc.id, **enterprise_doc.to_dict()}
    
    return None


def get_or_create_user(decoded_token: dict) -> UserProfile:
    """
    Get existing user or create new user based on domain validation
    """
    # Firebase tokens use 'sub' for user ID, but may also have 'uid' or 'user_id'
    uid = decoded_token.get("sub") or decoded_token.get("uid") or decoded_token.get("user_id")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: no user ID found"
        )
    email = decoded_token.get("email", "")
    
    # Check if user already exists by UID
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    
    if user_doc.exists:
        # Return existing user
        data = user_doc.to_dict()
        return UserProfile(
            uid=uid,
            email=email,
            enterprise_id=data.get("enterprise_id"),
            enterprise_name=data.get("enterprise_name"),
            role=data.get("role", "user"),
            ed_access=data.get("ed_access", [])
        )
    
    # No doc found by UID — check if a record exists by email
    # (e.g. admin created via owner dashboard before user's first login)
    if email:
        email_query = db.collection("users").where("email", "==", email).limit(1)
        email_matches = list(email_query.stream())
        if email_matches:
            existing_doc = email_matches[0]
            existing_data = existing_doc.to_dict()
            
            # Migrate: copy data to the real UID document, delete the old one
            existing_data["email"] = email  # ensure email is current
            user_ref.set(existing_data)
            existing_doc.reference.delete()
            
            return UserProfile(
                uid=uid,
                email=email,
                enterprise_id=existing_data.get("enterprise_id"),
                enterprise_name=existing_data.get("enterprise_name"),
                role=existing_data.get("role", "user"),
                ed_access=existing_data.get("ed_access", [])
            )
    
    # Truly new user - validate domain
    email_domain = email.split("@")[-1] if "@" in email else ""
    enterprise = get_enterprise_by_domain(email_domain)
    
    if not enterprise:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Email domain '{email_domain}' is not registered with any enterprise. Contact your administrator."
        )
    
    # Get all EDs for this enterprise (default: access to all)
    eds_ref = db.collection("enterprises").document(enterprise["id"]).collection("eds")
    all_eds = [doc.id for doc in eds_ref.stream()]
    
    # Create new user
    user_data = {
        "email": email,
        "enterprise_id": enterprise["id"],
        "enterprise_name": enterprise.get("name", ""),
        "role": "user",
        "ed_access": all_eds,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    user_ref.set(user_data)
    
    return UserProfile(
        uid=uid,
        email=email,
        enterprise_id=enterprise["id"],
        enterprise_name=enterprise.get("name", ""),
        role="user",
        ed_access=all_eds
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


def require_ed_access(user: UserProfile, ed_id: str):
    """
    Check if user has access to a specific ED
    Raises 403 if not authorized
    """
    # Super admins and owners have access to everything
    if user.role in ["super_admin", "owner"]:
        return
    
    # Check ED access
    if ed_id not in user.ed_access and "all" not in user.ed_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have access to ED '{ed_id}'"
        )


def require_admin(user: UserProfile):
    """
    Check if user is an admin (ed_admin, owner, or super_admin)
    """
    if user.role not in ["ed_admin", "owner", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
