"""
Seed Firestore Database
Creates initial enterprises, EDs, bundles, and admin users
"""

from google.cloud import firestore

# Initialize Firestore client
db = firestore.Client(project="clinical-assistant-457902")


def seed_enterprises():
    """Create initial enterprises with EDs and bundles"""
    
    enterprises = [
        {
            "id": "mayo-clinic",
            "name": "Mayo Clinic",
            "slug": "mayo-clinic",
            "allowed_domains": ["mayo.edu", "mayo.org", "gmail.com"],
            "subscription_tier": "enterprise",
            "settings": {
                "allow_user_signup": True,
                "max_protocols": 500,
            },
            "eds": [
                {
                    "id": "rochester",
                    "name": "Rochester",
                    "slug": "rochester",
                    "location": "Rochester, MN",
                    "bundles": [
                        {
                            "id": "acls",
                            "name": "ACLS",
                            "slug": "acls",
                            "description": "Advanced Cardiac Life Support algorithms",
                            "icon": "heart",
                            "color": "#EF4444",
                            "order": 1,
                        },
                        {
                            "id": "jit-education",
                            "name": "JIT Education",
                            "slug": "jit-education",
                            "description": "Just-in-time procedural quick reference guides",
                            "icon": "clipboard-list",
                            "color": "#3B82F6",
                            "order": 2,
                        },
                    ]
                },
            ]
        },
    ]
    
    for enterprise in enterprises:
        enterprise_id = enterprise.pop("id")
        eds_data = enterprise.pop("eds")
        
        # Create enterprise doc (merge to avoid overwriting existing fields)
        doc_ref = db.collection("enterprises").document(enterprise_id)
        doc_ref.set(enterprise, merge=True)
        print(f"✅ Ensured enterprise: {enterprise['name']} ({enterprise_id})")
        
        # Create EDs and bundles (merge to avoid overwriting existing)
        for ed in eds_data:
            ed_id = ed.pop("id")
            bundles_data = ed.pop("bundles")
            
            ed_ref = doc_ref.collection("eds").document(ed_id)
            ed_ref.set(ed, merge=True)
            print(f"  🏥 Ensured ED: {ed['name']} ({ed_id})")
            
            for bundle in bundles_data:
                bundle_id = bundle.pop("id")
                ed_ref.collection("bundles").document(bundle_id).set(bundle, merge=True)
                print(f"    📦 Ensured bundle: {bundle['name']} ({bundle_id})")


def create_super_admin(email: str, uid: str):
    """Create a super admin user (call after first sign-in)"""
    
    user_ref = db.collection("users").document(uid)
    user_ref.set({
        "email": email,
        "role": "super_admin",
        "ed_access": [],
        "enterprise_id": None,
        "enterprise_name": "System Admin",
        "created_at": firestore.SERVER_TIMESTAMP,
    })
    print(f"✅ Created super admin: {email}")


def seed_super_admin_by_email(email: str):
    """
    Seed a super admin by email address.
    
    If a user doc already exists (matched by email), update its role to super_admin.
    Otherwise, create a placeholder doc keyed by email so that on first sign-in
    the auth service will find it and migrate it to the real UID.
    """
    # Check if a user doc with this email already exists
    query = db.collection("users").where("email", "==", email).limit(1)
    matches = list(query.stream())
    
    if matches:
        # Update existing doc to super_admin
        doc = matches[0]
        doc.reference.update({
            "role": "super_admin",
            "access_status": "approved",
        })
        print(f"✅ Updated existing user to super_admin: {email} (doc: {doc.id})")
    else:
        # Create a placeholder doc keyed by a deterministic ID (email hash)
        # The auth service will find this by email query on first login and migrate it
        import hashlib
        placeholder_id = f"seed-{hashlib.sha256(email.encode()).hexdigest()[:12]}"
        
        # Determine enterprise from email domain
        email_domain = email.split("@")[-1] if "@" in email else ""
        enterprise_id = None
        enterprise_name = None
        ed_access = []
        
        if email_domain == "mayo.edu":
            enterprise_id = "mayo-clinic"
            enterprise_name = "Mayo Clinic"
            # Get all EDs for mayo-clinic
            eds_ref = db.collection("enterprises").document("mayo-clinic").collection("eds")
            ed_access = [doc.id for doc in eds_ref.stream()]
        
        user_ref = db.collection("users").document(placeholder_id)
        user_ref.set({
            "email": email,
            "role": "super_admin",
            "ed_access": ed_access,
            "enterprise_id": enterprise_id,
            "enterprise_name": enterprise_name,
            "access_status": "approved",
            "created_at": firestore.SERVER_TIMESTAMP,
        })
        print(f"✅ Created super_admin placeholder for: {email} (doc: {placeholder_id})")
        print(f"   On first Google sign-in, this will be migrated to the real Firebase UID.")


# Default super admins to seed
SEED_SUPER_ADMINS = [
    "jones.derick@mayo.edu",
    "morey.jacob@mayo.edu",
]


if __name__ == "__main__":
    print("\n🌱 Seeding Firestore database...\n")
    seed_enterprises()
    
    print("\n👑 Seeding super admins...\n")
    for admin_email in SEED_SUPER_ADMINS:
        seed_super_admin_by_email(admin_email)
    
    print("\n✅ Seed complete!\n")
