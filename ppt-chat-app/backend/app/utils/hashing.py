"""
Hashing utilities for template identification
"""

import hashlib
from typing import Union
from pathlib import Path

def hash_bytes(data: bytes) -> str:
    """
    Generate a SHA-256 hash from bytes
    
    Args:
        data: Bytes to hash
        
    Returns:
        Hex string of the hash (64 characters)
    """
    return hashlib.sha256(data).hexdigest()

def hash_file(file_path: Union[str, Path]) -> str:
    """
    Generate a SHA-256 hash from a file
    
    Args:
        file_path: Path to the file
        
    Returns:
        Hex string of the hash (64 characters)
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def get_template_id(pptx_bytes: bytes) -> str:
    """
    Generate a unique template ID from PPTX file bytes
    
    Args:
        pptx_bytes: PPTX file content as bytes
        
    Returns:
        Template ID (first 16 characters of hash for readability)
    """
    full_hash = hash_bytes(pptx_bytes)
    # Use first 16 characters for a shorter, more manageable ID
    return full_hash[:16]

def get_cache_key(template_id: str, suffix: str = "") -> str:
    """
    Generate a cache key for storing template-related data
    
    Args:
        template_id: Template identifier
        suffix: Optional suffix for the key
        
    Returns:
        Cache key string
    """
    if suffix:
        return f"template:{template_id}:{suffix}"
    return f"template:{template_id}"