"""
Protocol Metadata Store
Retrieves protocol info and images for query responses
"""

from google.cloud import storage
import json
from typing import Optional, List, Dict
import os

PROJECT_ID = os.environ.get("PROJECT_ID", "clinical-assistant-457902")
PROCESSED_BUCKET = f"{PROJECT_ID}-protocols-processed"


class ProtocolStore:
    """Interface to protocol metadata and images"""
    
    def __init__(self):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(PROCESSED_BUCKET)
        self._cache = {}  # Simple in-memory cache
    
    def get_protocol_metadata(self, org_id: str, protocol_id: str) -> Optional[Dict]:
        """Get metadata for a specific protocol"""
        cache_key = f"{org_id}/{protocol_id}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            blob = self.bucket.blob(f"{org_id}/{protocol_id}/metadata.json")
            content = blob.download_as_string()
            metadata = json.loads(content)
            self._cache[cache_key] = metadata
            return metadata
        except Exception as e:
            print(f"Error loading metadata for {cache_key}: {e}")
            return None
    
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
    
    def get_images_for_protocol(self, org_id: str, protocol_id: str) -> List[Dict]:
        """Get all images for a protocol"""
        metadata = self.get_protocol_metadata(org_id, protocol_id)
        if metadata:
            return metadata.get("images", [])
        return []
    
    def get_image_url(self, gcs_uri: str, signed: bool = False, expiration_minutes: int = 60) -> str:
        """
        Convert GCS URI to accessible URL
        
        Args:
            gcs_uri: gs://bucket/path format
            signed: If True, generate a signed URL (for private buckets)
            expiration_minutes: How long the signed URL should be valid
        
        Returns:
            URL string
        """
        if not gcs_uri.startswith("gs://"):
            return gcs_uri
        
        # Parse gs://bucket/path
        parts = gcs_uri[5:].split("/", 1)
        bucket_name = parts[0]
        blob_path = parts[1] if len(parts) > 1 else ""
        
        if signed:
            # Generate signed URL for private bucket access
            from datetime import timedelta
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            return url
        else:
            # Public URL (requires bucket to be public)
            return f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
    
    def get_images_for_source(self, source_uri: str) -> List[Dict]:
        """
        Get images associated with a RAG source URI
        
        The source_uri from RAG looks like:
        gs://bucket/org_id/protocol_id/extracted_text.txt
        
        We extract org_id and protocol_id to find the images.
        """
        if not source_uri:
            return []
        
        # Parse the source URI
        # Format: gs://bucket/org_id/protocol_id/extracted_text.txt
        try:
            if source_uri.startswith("gs://"):
                path = source_uri.split("/", 3)[-1]  # Get path after bucket
                parts = path.split("/")
                if len(parts) >= 2:
                    org_id = parts[0]
                    protocol_id = parts[1]
                    return self.get_images_for_protocol(org_id, protocol_id)
        except Exception as e:
            print(f"Error parsing source URI {source_uri}: {e}")
        
        return []


def get_images_from_rag_response(rag_contexts: List[Dict], signed_urls: bool = False) -> List[Dict]:
    """
    Extract relevant images from RAG response contexts
    
    Args:
        rag_contexts: List of context objects from RAG retrieval
        signed_urls: Whether to generate signed URLs
    
    Returns:
        List of unique images with URLs
    """
    store = ProtocolStore()
    seen_images = set()
    images = []
    
    for ctx in rag_contexts:
        source_uri = ctx.get("sourceUri", "")
        
        # Get images for this source
        protocol_images = store.get_images_for_source(source_uri)
        
        for img in protocol_images:
            img_key = img.get("gcs_uri", "")
            if img_key and img_key not in seen_images:
                seen_images.add(img_key)
                images.append({
                    "page": img.get("page"),
                    "gcs_uri": img_key,
                    "url": store.get_image_url(img_key, signed=signed_urls),
                    "source": source_uri.split("/")[-2] if "/" in source_uri else "unknown"
                })
    
    # Sort by page number
    images.sort(key=lambda x: (x.get("source", ""), x.get("page", 0)))
    
    return images


# For testing
if __name__ == "__main__":
    store = ProtocolStore()
    
    # List all protocols for test-org
    print("Protocols in 'test-org':")
    for p in store.list_protocols("test-org"):
        print(f"  - {p.get('protocol_id')}: {p.get('char_count')} chars, {p.get('image_count')} images")
    
    # Also check default org (from POC)
    print("\nProtocols in 'default':")
    for p in store.list_protocols("default"):
        print(f"  - {p.get('protocol_id')}: {p.get('char_count')} chars, {p.get('image_count')} images")
