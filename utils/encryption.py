"""
Encryption utilities for sensitive data.
Provides field-level encryption and secure key management.
"""
import base64
import os
import json
import logging
import hashlib
import hmac
import time
import secrets
from typing import Dict, Any, Optional, List, Union, Set, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.utils.settings import (
    SECURITY_ENCRYPTION_KEY,
    SECURITY_ENCRYPTION_SALT,
    SECURITY_SENSITIVE_FIELDS,
    SECURITY_FIELD_ENCRYPTION_ENABLED,
    SECURITY_JWT_SECRET,
    SECURITY_JWT_ALGORITHM,
    SECURITY_JWT_EXPIRY
)

logger = logging.getLogger(__name__)

class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.
    Supports field-level encryption and JWT token generation.
    """
    
    def __init__(self):
        """Initialize the encryption service."""
        self.encryption_key = SECURITY_ENCRYPTION_KEY
        self.encryption_salt = SECURITY_ENCRYPTION_SALT
        self.jwt_secret = SECURITY_JWT_SECRET
        self.jwt_algorithm = SECURITY_JWT_ALGORITHM
        self.jwt_expiry = SECURITY_JWT_EXPIRY
        self.sensitive_fields = set(SECURITY_SENSITIVE_FIELDS)
        self.enabled = SECURITY_FIELD_ENCRYPTION_ENABLED
        
        # Initialize Fernet cipher
        self.fernet = None
        if self.enabled:
            if not self.encryption_key:
                logger.warning("No encryption key provided, generating temporary one")
                self.encryption_key = self._generate_key()
            
            if not self.encryption_salt:
                logger.warning("No encryption salt provided, generating temporary one")
                self.encryption_salt = self._generate_salt()
                
            self.fernet = self._initialize_fernet()
    
    def _generate_key(self) -> str:
        """
        Generate a random encryption key.
        
        Returns:
            str: Base64-encoded encryption key
        """
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    
    def _generate_salt(self) -> str:
        """
        Generate a random salt.
        
        Returns:
            str: Hex-encoded salt
        """
        return os.urandom(16).hex()
    
    def _initialize_fernet(self) -> Fernet:
        """
        Initialize Fernet cipher with derived key.
        
        Returns:
            Fernet: Initialized Fernet cipher
        """
        # Convert string key and salt to bytes
        salt = bytes.fromhex(self.encryption_salt)
        
        # Use PBKDF2 to derive a key from the encryption key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000
        )
        
        # Derive the key
        key = base64.urlsafe_b64encode(kdf.derive(self.encryption_key.encode()))
        
        # Create Fernet cipher
        return Fernet(key)
    
    def encrypt_value(self, value: str) -> str:
        """
        Encrypt a string value.
        
        Args:
            value: String value to encrypt
            
        Returns:
            str: Encrypted value (base64-encoded)
        """
        if not self.enabled or not value:
            return value
        
        try:
            # Encrypt the value
            encrypted_data = self.fernet.encrypt(value.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Error encrypting value: {e}")
            return value
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """
        Decrypt an encrypted string value.
        
        Args:
            encrypted_value: Encrypted value (base64-encoded)
            
        Returns:
            str: Decrypted value
        """
        if not self.enabled or not encrypted_value:
            return encrypted_value
        
        try:
            # Decode and decrypt the value
            encrypted_data = base64.urlsafe_b64decode(encrypted_value)
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Error decrypting value: {e}")
            return encrypted_value
    
    def encrypt_dict(self, data: Dict[str, Any], additional_sensitive_fields: Set[str] = None) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in a dictionary.
        
        Args:
            data: Dictionary containing data to encrypt
            additional_sensitive_fields: Additional field names to encrypt
            
        Returns:
            Dict: Dictionary with sensitive fields encrypted
        """
        if not self.enabled or not data:
            return data
        
        # Create a copy of the data
        encrypted_data = data.copy()
        
        # Combine sensitive fields
        sensitive_fields = self.sensitive_fields.copy()
        if additional_sensitive_fields:
            sensitive_fields.update(additional_sensitive_fields)
        
        # Encrypt sensitive fields
        for field, value in encrypted_data.items():
            if field in sensitive_fields and isinstance(value, str):
                encrypted_data[field] = self.encrypt_value(value)
            elif isinstance(value, dict):
                encrypted_data[field] = self.encrypt_dict(value, additional_sensitive_fields)
            elif isinstance(value, list):
                encrypted_data[field] = [
                    self.encrypt_dict(item, additional_sensitive_fields) if isinstance(item, dict) else item
                    for item in value
                ]
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any], additional_sensitive_fields: Set[str] = None) -> Dict[str, Any]:
        """
        Decrypt sensitive fields in a dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            additional_sensitive_fields: Additional field names to decrypt
            
        Returns:
            Dict: Dictionary with sensitive fields decrypted
        """
        if not self.enabled or not data:
            return data
        
        # Create a copy of the data
        decrypted_data = data.copy()
        
        # Combine sensitive fields
        sensitive_fields = self.sensitive_fields.copy()
        if additional_sensitive_fields:
            sensitive_fields.update(additional_sensitive_fields)
        
        # Decrypt sensitive fields
        for field, value in decrypted_data.items():
            if field in sensitive_fields and isinstance(value, str):
                decrypted_data[field] = self.decrypt_value(value)
            elif isinstance(value, dict):
                decrypted_data[field] = self.decrypt_dict(value, additional_sensitive_fields)
            elif isinstance(value, list):
                decrypted_data[field] = [
                    self.decrypt_dict(item, additional_sensitive_fields) if isinstance(item, dict) else item
                    for item in value
                ]
        
        return decrypted_data
    
    def generate_jwt(self, payload: Dict[str, Any], expiry_seconds: int = None) -> str:
        """
        Generate a JWT token.
        
        Args:
            payload: Token payload
            expiry_seconds: Token expiry in seconds (default to settings)
            
        Returns:
            str: JWT token
        """
        if not self.jwt_secret:
            logger.warning("No JWT secret configured, generating temporary one")
            self.jwt_secret = secrets.token_hex(32)
        
        # Use default expiry if not specified
        if expiry_seconds is None:
            expiry_seconds = self.jwt_expiry
        
        # Add standard claims
        now = int(time.time())
        payload.update({
            "iat": now,
            "exp": now + expiry_seconds,
            "nbf": now
        })
        
        # Create token
        header = {
            "alg": self.jwt_algorithm,
            "typ": "JWT"
        }
        
        # Encode header and payload
        header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        
        # Create signature
        message = f"{header_encoded}.{payload_encoded}"
        signature = hmac.new(
            self.jwt_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        signature_encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        
        # Combine to form token
        token = f"{header_encoded}.{payload_encoded}.{signature_encoded}"
        
        return token
    
    def verify_jwt(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verify a JWT token and extract the payload.
        
        Args:
            token: JWT token
            
        Returns:
            Tuple[bool, Optional[Dict]]: (is_valid, payload)
        """
        if not token or not self.jwt_secret:
            return False, None
        
        try:
            # Split token
            parts = token.split(".")
            if len(parts) != 3:
                return False, None
            
            header_encoded, payload_encoded, signature_encoded = parts
            
            # Verify signature
            message = f"{header_encoded}.{payload_encoded}"
            expected_signature = hmac.new(
                self.jwt_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
            expected_signature_encoded = base64.urlsafe_b64encode(expected_signature).decode().rstrip("=")
            
            if signature_encoded != expected_signature_encoded:
                return False, None
            
            # Decode payload
            padded_payload = payload_encoded + "=" * ((4 - len(payload_encoded) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded_payload).decode())
            
            # Check expiry
            now = int(time.time())
            if payload.get("exp", 0) < now:
                return False, None
            
            # Check not before
            if payload.get("nbf", 0) > now:
                return False, None
            
            return True, payload
            
        except Exception as e:
            logger.error(f"Error verifying JWT: {e}")
            return False, None
    
    def generate_hash(self, value: str, salt: Optional[str] = None) -> str:
        """
        Generate a secure hash for a value.
        
        Args:
            value: Value to hash
            salt: Optional salt
            
        Returns:
            str: Secure hash
        """
        if not salt:
            salt = self._generate_salt()
        
        # Create hash
        hash_obj = hashlib.sha256()
        hash_obj.update(salt.encode())
        hash_obj.update(value.encode())
        
        return f"{salt}${hash_obj.hexdigest()}"
    
    def verify_hash(self, value: str, hash_value: str) -> bool:
        """
        Verify a hash against a value.
        
        Args:
            value: Value to check
            hash_value: Hash to verify against
            
        Returns:
            bool: True if hash matches
        """
        if not hash_value or "$" not in hash_value:
            return False
        
        # Extract salt
        salt, stored_hash = hash_value.split("$", 1)
        
        # Create hash
        hash_obj = hashlib.sha256()
        hash_obj.update(salt.encode())
        hash_obj.update(value.encode())
        
        return hash_obj.hexdigest() == stored_hash

# Singleton instance
encryption_service = EncryptionService() 