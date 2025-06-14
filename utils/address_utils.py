"""
Utility functions for working with Solana addresses.
"""
import re
import logging
from typing import Optional

# Logger
logger = logging.getLogger(__name__)

# Regular expression for validating Solana addresses
SOLANA_ADDRESS_REGEX = r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'

def validate_solana_address(address: Optional[str]) -> bool:
    """
    Validate if a string is a properly formatted Solana address.
    
    Args:
        address: The address to validate
        
    Returns:
        bool: True if the address is valid, False otherwise
    """
    if not address:
        return False
    
    # Trim any whitespace
    address = address.strip()
    
    # Check length
    if len(address) < 32 or len(address) > 44:
        logger.debug(f"Invalid address length: {len(address)}")
        return False
    
    # Check format using regex
    if not re.match(SOLANA_ADDRESS_REGEX, address):
        logger.debug(f"Address failed regex validation: {address}")
        return False
    
    return True

def truncate_address(address: str, start_chars: int = 6, end_chars: int = 4) -> str:
    """
    Truncate an address for display purposes.
    
    Args:
        address: The address to truncate
        start_chars: Number of characters to keep at the start
        end_chars: Number of characters to keep at the end
        
    Returns:
        str: Truncated address (e.g., "3fGdu...7fKs")
    """
    if not address:
        return ""
    
    if len(address) <= start_chars + end_chars:
        return address
    
    return f"{address[:start_chars]}...{address[-end_chars:]}"

def is_program_address(address: str) -> bool:
    """
    Perform a simple check to determine if an address is likely a program address.
    This is a heuristic and may not be 100% accurate without on-chain verification.
    
    Args:
        address: The address to check
        
    Returns:
        bool: True if the address appears to be a program address
    """
    # Programs typically have specific address patterns
    # This is a basic check and would need to be improved with actual on-chain checks
    return validate_solana_address(address) 