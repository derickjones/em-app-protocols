"""
Seed Firestore Database
Creates initial organizations and admin users for testing
"""

from google.cloud import firestore

# Initialize Firestore client
db = firestore.Client(project="clinical-assistant-457902")


def seed_organizations():
    """Create initial organizations with domain whitelists"""
    
    organizations = [
        {
            "id": "demo-hospital",
            "name": "Demo Hospital",
            "slug": "demo-hospital",
            "allowed_domains": ["demo.hospital.org", "gmail.com"],  # gmail.com for testing
            "default_bundles": ["practice"],
            "subscription_tier": "professional",
            "settings": {
                "allow_user_signup": True,
                "max_protocols": 100,
            },
        },
        {
            "id": "mayo-clinic",
            "name": "Mayo Clinic",
            "slug": "mayo-clinic",
            "allowed_domains": ["mayo.edu", "mayo.org"],
            "default_bundles": ["practice", "nursing"],
            "subscription_tier": "enterprise",
            "settings": {
                "allow_user_signup": True,
                "max_protocols": 500,
            },
        },
    ]
    
    for org in organizations:
        org_id = org.pop("id")
        doc_ref = db.collection("organizations").document(org_id)
        doc_ref.set(org)
        print(f"✅ Created organization: {org['name']} ({org_id})")
        
        # Create default bundles for each org
        seed_bundles(org_id)


def seed_bundles(org_id: str):
    """Create default bundles for an organization"""
    
    bundles = [
        {
            "id": "practice",
            "name": "Practice Protocols",
            "slug": "practice",
            "description": "Clinical protocols and guidelines",
            "icon": "clipboard-list",
            "color": "#3B82F6",
            "is_default": True,
            "order": 1,
        },
        {
            "id": "nursing",
            "name": "Nursing Protocols",
            "slug": "nursing",
            "description": "Nursing-specific workflows and assessments",
            "icon": "heart-pulse",
            "color": "#EC4899",
            "is_default": False,
            "order": 2,
        },
        {
            "id": "telemed",
            "name": "Telemed Protocols",
            "slug": "telemed",
            "description": "Telemedicine procedures and workflows",
            "icon": "video",
            "color": "#8B5CF6",
            "is_default": False,
            "order": 3,
        },
        {
            "id": "pediatric",
            "name": "Pediatric Protocols",
            "slug": "pediatric",
            "description": "Pediatric-specific guidelines",
            "icon": "baby",
            "color": "#F59E0B",
            "is_default": False,
            "order": 4,
        },
        {
            "id": "trauma",
            "name": "Trauma Protocols",
            "slug": "trauma",
            "description": "Trauma center specific protocols",
            "icon": "alert-triangle",
            "color": "#EF4444",
            "is_default": False,
            "order": 5,
        },
    ]
    
    bundles_ref = db.collection("organizations").document(org_id).collection("bundles")
    
    for bundle in bundles:
        bundle_id = bundle.pop("id")
        bundles_ref.document(bundle_id).set(bundle)
        print(f"  📦 Created bundle: {bundle['name']}")


def create_super_admin(email: str, uid: str):
    """Create a super admin user (call after first sign-in)"""
    
    user_ref = db.collection("users").document(uid)
    user_ref.set({
        "email": email,
        "role": "super_admin",
        "bundle_access": ["all"],
        "org_id": None,  # Super admins are not bound to an org
        "org_name": "System Admin",
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    print(f"✅ Created super admin: {email}")


if __name__ == "__main__":
    print("\n🌱 Seeding Firestore database...\n")
    seed_organizations()
    print("\n✅ Seed complete!\n")
    
    print("To create a super admin, call:")
    print('  create_super_admin("your-email@gmail.com", "firebase-uid")')
    print("\nYou can get the UID from Firebase Console → Authentication → Users")
