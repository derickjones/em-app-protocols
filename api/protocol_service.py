"""
Protocol Service
Handles protocol metadata and image retrieval
"""

import os
import json
from typing import Dict, List, Optional
from google.cloud import storage

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
PROCESSED_BUCKET = f"{PROJECT_ID}-protocols-processed"


class ProtocolService:
    """Service for protocol metadata operations"""
    
    def __init__(self):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(PROCESSED_BUCKET)
        self._cache = {}
    
    def list_protocols(self, org_id: str) -> List[Dict]:
        """List all protocols for an organization"""
        protocols = []
        prefix = f"{org_id}/"
        
        # List all metadata.json files
        blobs = self.bucket.list_blobs(prefix=prefix)
        
        for blob in blobs:
            if blob.name.endswith("/metadata.json"):
                try:
                    content = blob.download_as_string()
                    metadata = json.loads(content)
                    protocols.append(metadata)
                except Exception as e:
                    print(f"Error loading {blob.name}: {e}")
        
        return protocols
    
    def get_protocol(self, org_id: str, protocol_id: str) -> Optional[Dict]:
        """Get metadata for a specific protocol"""
        cache_key = f"{org_id}/{protocol_id}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            blob = self.bucket.blob(f"{org_id}/{protocol_id}/metadata.json")
            
            if not blob.exists():
                return None
            
            content = blob.download_as_string()
            metadata = json.loads(content)
            
            # Add image URLs
            images = metadata.get("images", [])
            for img in images:
                gcs_uri = img.get("gcs_uri", "")
                if gcs_uri:
                    img["url"] = gcs_uri.replace(
                        "gs://",
                        "https://storage.googleapis.com/"
                    )
            
            self._cache[cache_key] = metadata
            return metadata
            
        except Exception as e:
            print(f"Error loading protocol {cache_key}: {e}")
            return None
    
    def get_protocol_images(self, org_id: str, protocol_id: str) -> List[Dict]:
        """Get images for a specific protocol"""
        protocol = self.get_protocol(org_id, protocol_id)
        
        if not protocol:
            return []
        
        images = []
        for img in protocol.get("images", []):
            gcs_uri = img.get("gcs_uri", "")
            if gcs_uri:
                images.append({
                    "page": img.get("page", 0),
                    "gcs_uri": gcs_uri,
                    "url": gcs_uri.replace("gs://", "https://storage.googleapis.com/")
                })
        
        return images
    
    def get_protocol_text(self, org_id: str, protocol_id: str) -> Optional[str]:
        """Get extracted text for a protocol"""
        try:
            blob = self.bucket.blob(f"{org_id}/{protocol_id}/extracted_text.txt")
            
            if not blob.exists():
                return None
            
            return blob.download_as_string().decode("utf-8")
            
        except Exception as e:
            print(f"Error loading text for {org_id}/{protocol_id}: {e}")
            return None
