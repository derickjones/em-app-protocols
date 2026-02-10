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
    
    def list_protocols(self, enterprise_id: str, ed_id: str = None, bundle_id: str = None) -> List[Dict]:
        """List all protocols for an enterprise, optionally filtered by ED and bundle"""
        protocols = []
        
        if ed_id and bundle_id:
            prefix = f"{enterprise_id}/{ed_id}/{bundle_id}/"
        elif ed_id:
            prefix = f"{enterprise_id}/{ed_id}/"
        else:
            prefix = f"{enterprise_id}/"
        
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
    
    def get_protocol(self, enterprise_id: str, ed_id: str, bundle_id: str, protocol_id: str) -> Optional[Dict]:
        """Get metadata for a specific protocol"""
        cache_key = f"{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            blob = self.bucket.blob(f"{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}/metadata.json")
            
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
    
    def get_protocol_images(self, enterprise_id: str, ed_id: str, bundle_id: str, protocol_id: str) -> List[Dict]:
        """Get images for a specific protocol"""
        protocol = self.get_protocol(enterprise_id, ed_id, bundle_id, protocol_id)
        
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
    
    def get_protocol_text(self, enterprise_id: str, ed_id: str, bundle_id: str, protocol_id: str) -> Optional[str]:
        """Get extracted text for a protocol"""
        try:
            blob = self.bucket.blob(f"{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}/extracted_text.txt")
            
            if not blob.exists():
                return None
            
            return blob.download_as_string().decode("utf-8")
            
        except Exception as e:
            print(f"Error loading text for {enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}: {e}")
            return None
    
    def list_all_enterprises(self) -> Dict[str, Dict[str, Dict[str, List[Dict]]]]:
        """
        List all enterprises and their EDs with bundles and protocols.
        Returns: { enterprise: { ed: { bundle: [protocols] } } }
        GCS path: enterprise_id/ed_id/bundle_id/protocol_id/metadata.json
        """
        enterprises = {}
        
        # List all blobs and find metadata.json files
        blobs = self.bucket.list_blobs()
        
        for blob in blobs:
            if blob.name.endswith("/metadata.json"):
                try:
                    # Parse path: enterprise_id/ed_id/bundle_id/protocol_id/metadata.json
                    parts = blob.name.split("/")
                    
                    if len(parts) >= 5:
                        # enterprise_id/ed_id/bundle_id/protocol_id/metadata.json
                        enterprise_id = parts[0]
                        ed_id = parts[1]
                        bundle_id = parts[2]
                        protocol_id = parts[3]
                    elif len(parts) >= 4:
                        # Legacy: org_id/bundle_id/protocol_id/metadata.json
                        enterprise_id = parts[0]
                        ed_id = "default"
                        bundle_id = parts[1]
                        protocol_id = parts[2]
                    else:
                        continue
                    
                    # Initialize nested structure
                    if enterprise_id not in enterprises:
                        enterprises[enterprise_id] = {}
                    if ed_id not in enterprises[enterprise_id]:
                        enterprises[enterprise_id][ed_id] = {}
                    if bundle_id not in enterprises[enterprise_id][ed_id]:
                        enterprises[enterprise_id][ed_id][bundle_id] = []
                    
                    # Load metadata
                    content = blob.download_as_string()
                    metadata = json.loads(content)
                    enterprises[enterprise_id][ed_id][bundle_id].append(metadata)
                    
                except Exception as e:
                    print(f"Error loading {blob.name}: {e}")
        
        return enterprises
    
    def delete_protocol(self, enterprise_id: str, ed_id: str, bundle_id: str, protocol_id: str) -> bool:
        """Delete a protocol from processed bucket"""
        try:
            prefix = f"{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}/"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            
            if not blobs:
                return False
            
            for blob in blobs:
                blob.delete()
            
            # Clear from cache
            cache_key = f"{enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}"
            if cache_key in self._cache:
                del self._cache[cache_key]
            
            return True
        except Exception as e:
            print(f"Error deleting protocol {enterprise_id}/{ed_id}/{bundle_id}/{protocol_id}: {e}")
            return False
