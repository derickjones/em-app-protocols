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
        
        # Create enterprise doc
        doc_ref = db.collection("enterprises").document(enterprise_id)
        doc_ref.set(enterprise)
        print(f"✅ Created enterprise: {enterprise['name']} ({enterprise_id})")
        
        # Create EDs and bundles
        for ed in eds_data:
            ed_id = ed.pop("id")
            bundles_data = ed.pop("bundles")
            
            ed_ref = doc_ref.collection("eds").document(ed_id)
            ed_ref.set(ed)
            print(f"  🏥 Created ED: {ed['name']} ({ed_id})")
            
            for bundle in bundles_data:
                bundle_id = bundle.pop("id")
                ed_ref.collection("bundles").document(bundle_id).set(bundle)
                print(f"    📦 Created bundle: {bundle['name']} ({bundle_id})")


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


if __name__ == "__main__":
    print("\n🌱 Seeding Firestore database...\n")
    seed_enterprises()
    print("\n✅ Seed complete!\n")
    
    print("To create a super admin, call:")
    print('  create_super_admin("your-email@gmail.com", "firebase-uid")')
    print("\nYou can get the UID from Firebase Console → Authentication → Users")
