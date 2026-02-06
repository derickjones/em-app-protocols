#!/bin/bash
# Seed Firestore with test organizations using REST API

PROJECT_ID="clinical-assistant-457902"
ACCESS_TOKEN=$(gcloud auth application-default print-access-token 2>/dev/null)
FIRESTORE_URL="https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/(default)/documents"

echo "🌱 Seeding Firestore database..."
echo ""

# Create demo-hospital organization
echo "Creating demo-hospital organization..."
curl -s -X PATCH \
  "${FIRESTORE_URL}/organizations/demo-hospital?updateMask.fieldPaths=name&updateMask.fieldPaths=slug&updateMask.fieldPaths=allowed_domains&updateMask.fieldPaths=default_bundles&updateMask.fieldPaths=subscription_tier" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "name": {"stringValue": "Demo Hospital"},
      "slug": {"stringValue": "demo-hospital"},
      "allowed_domains": {"arrayValue": {"values": [{"stringValue": "demo.hospital.org"}, {"stringValue": "gmail.com"}]}},
      "default_bundles": {"arrayValue": {"values": [{"stringValue": "practice"}]}},
      "subscription_tier": {"stringValue": "professional"}
    }
  }' > /dev/null

echo "✅ Created: Demo Hospital"

# Create mayo-clinic organization
echo "Creating mayo-clinic organization..."
curl -s -X PATCH \
  "${FIRESTORE_URL}/organizations/mayo-clinic?updateMask.fieldPaths=name&updateMask.fieldPaths=slug&updateMask.fieldPaths=allowed_domains&updateMask.fieldPaths=default_bundles&updateMask.fieldPaths=subscription_tier" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "name": {"stringValue": "Mayo Clinic"},
      "slug": {"stringValue": "mayo-clinic"},
      "allowed_domains": {"arrayValue": {"values": [{"stringValue": "mayo.edu"}, {"stringValue": "mayo.org"}]}},
      "default_bundles": {"arrayValue": {"values": [{"stringValue": "practice"}, {"stringValue": "nursing"}]}},
      "subscription_tier": {"stringValue": "enterprise"}
    }
  }' > /dev/null

echo "✅ Created: Mayo Clinic"

# Create bundles for demo-hospital
echo ""
echo "Creating bundles for demo-hospital..."
for bundle in practice nursing telemed pediatric trauma; do
  case $bundle in
    practice)
      name="Practice Protocols"
      color="#3B82F6"
      ;;
    nursing)
      name="Nursing Protocols"
      color="#EC4899"
      ;;
    telemed)
      name="Telemed Protocols"
      color="#8B5CF6"
      ;;
    pediatric)
      name="Pediatric Protocols"
      color="#F59E0B"
      ;;
    trauma)
      name="Trauma Protocols"
      color="#EF4444"
      ;;
  esac
  
  curl -s -X PATCH \
    "${FIRESTORE_URL}/organizations/demo-hospital/bundles/${bundle}?updateMask.fieldPaths=name&updateMask.fieldPaths=slug&updateMask.fieldPaths=color" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
      \"fields\": {
        \"name\": {\"stringValue\": \"${name}\"},
        \"slug\": {\"stringValue\": \"${bundle}\"},
        \"color\": {\"stringValue\": \"${color}\"}
      }
    }" > /dev/null
  echo "  📦 Created bundle: ${name}"
done

echo ""
echo "✅ Seed complete!"
echo ""
echo "Organizations created:"
echo "  - Demo Hospital (allowed domains: demo.hospital.org, gmail.com)"
echo "  - Mayo Clinic (allowed domains: mayo.edu, mayo.org)"
