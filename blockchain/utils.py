"""
Blockchain utilities for Blaze Analyst.
Common blockchain operations for Solana, including transaction parsing,
account data fetching, and contract metadata extraction.
"""
import base64
import binascii
import logging
from typing import Dict, List, Optional, Any, Union, Tuple

from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.system_program import SYS_PROGRAM_ID

from src.blockchain.solana_client import solana_client
from src.blockchain.helius_client import helius_client

logger = logging.getLogger(__name__)

# Token program IDs
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"

def is_valid_solana_address(address: str) -> bool:
    """
    Check if an address is a valid Solana address.
    
    Args:
        address: Address to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        PublicKey(address)
        return True
    except (ValueError, TypeError):
        return False

def get_associated_token_address(wallet: str, token_mint: str) -> str:
    """
    Find the associated token account address for a wallet and token mint.
    
    Args:
        wallet: Wallet address
        token_mint: Token mint address
        
    Returns:
        str: Associated token account address
    """
    try:
        wallet_pubkey = PublicKey(wallet)
        token_pubkey = PublicKey(token_mint)
        
        seeds = [
            bytes(wallet_pubkey),
            bytes(PublicKey(TOKEN_PROGRAM_ID)),
            bytes(token_pubkey)
        ]
        
        # Find PDA
        program_id = PublicKey(ASSOCIATED_TOKEN_PROGRAM_ID)
        address, _ = PublicKey.find_program_address(seeds, program_id)
        
        return str(address)
    except Exception as e:
        logger.error(f"Error finding associated token account: {e}")
        raise

def get_metadata_address(token_mint: str) -> str:
    """
    Find the metadata account address for a token mint.
    
    Args:
        token_mint: Token mint address
        
    Returns:
        str: Metadata account address
    """
    try:
        token_pubkey = PublicKey(token_mint)
        
        # Find PDA for metadata
        seeds = [
            b"metadata",
            bytes(PublicKey(METADATA_PROGRAM_ID)),
            bytes(token_pubkey)
        ]
        
        # Find PDA
        program_id = PublicKey(METADATA_PROGRAM_ID)
        address, _ = PublicKey.find_program_address(seeds, program_id)
        
        return str(address)
    except Exception as e:
        logger.error(f"Error finding metadata account: {e}")
        raise

def parse_transaction(tx_data: Dict) -> Dict:
    """
    Parse a Solana transaction and extract key information.
    
    Args:
        tx_data: Raw transaction data
        
    Returns:
        Dict: Parsed transaction information
    """
    try:
        result = {
            'signature': tx_data.get('transaction', {}).get('signatures', [None])[0],
            'slot': tx_data.get('slot'),
            'timestamp': tx_data.get('blockTime'),
            'status': 'success' if tx_data.get('meta', {}).get('err') is None else 'failed',
            'fee': tx_data.get('meta', {}).get('fee', 0),
            'accounts': [],
            'instructions': [],
            'tokens': [],
        }
        
        # Extract accounts
        if 'accountKeys' in tx_data['transaction']['message']:
            result['accounts'] = tx_data['transaction']['message']['accountKeys']
        
        # Extract instructions
        if 'instructions' in tx_data['transaction']['message']:
            for idx, instr in enumerate(tx_data['transaction']['message']['instructions']):
                program_idx = instr.get('programIdIndex')
                if program_idx is not None and program_idx < len(result['accounts']):
                    program_id = result['accounts'][program_idx]
                    
                    instruction = {
                        'program_id': program_id,
                        'program_name': get_program_name(program_id),
                        'accounts': [result['accounts'][i] for i in instr.get('accounts', [])],
                        'data': instr.get('data'),
                    }
                    
                    result['instructions'].append(instruction)
        
        # Extract token transfers from log messages if available
        if 'logMessages' in tx_data.get('meta', {}):
            for log in tx_data['meta']['logMessages']:
                if 'Transfer' in log and 'amount' in log:
                    # This is a simplified approach, in a real system you'd use a parser for SPL token
                    # program instruction logs to extract transfers properly
                    result['tokens'].append({
                        'log': log
                    })
        
        # Extract pre and post token balances
        if 'preTokenBalances' in tx_data.get('meta', {}) and 'postTokenBalances' in tx_data.get('meta', {}):
            pre = {(b.get('accountIndex'), b.get('mint')): b for b in tx_data['meta']['preTokenBalances']}
            post = {(b.get('accountIndex'), b.get('mint')): b for b in tx_data['meta']['postTokenBalances']}
            
            # Find token transfers by comparing balances
            for key in set(pre.keys()) | set(post.keys()):
                pre_bal = pre.get(key, {}).get('uiTokenAmount', {}).get('uiAmount', 0) or 0
                post_bal = post.get(key, {}).get('uiTokenAmount', {}).get('uiAmount', 0) or 0
                
                if pre_bal != post_bal:
                    mint = key[1]
                    account_idx = key[0]
                    account = result['accounts'][account_idx] if account_idx < len(result['accounts']) else None
                    
                    result['tokens'].append({
                        'mint': mint,
                        'account': account,
                        'owner': pre.get(key, {}).get('owner') or post.get(key, {}).get('owner'),
                        'change': post_bal - pre_bal,
                    })
        
        return result
        
    except Exception as e:
        logger.error(f"Error parsing transaction: {e}")
        return {
            'error': str(e),
            'original': tx_data
        }

def get_program_name(program_id: str) -> str:
    """
    Get a human-readable name for common program IDs.
    
    Args:
        program_id: Program ID
        
    Returns:
        str: Human-readable program name
    """
    program_names = {
        str(SYS_PROGRAM_ID): "System Program",
        TOKEN_PROGRAM_ID: "Token Program",
        ASSOCIATED_TOKEN_PROGRAM_ID: "Associated Token Program",
        METADATA_PROGRAM_ID: "Metadata Program",
        "11111111111111111111111111111111": "System Program",
        "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin": "Serum DEX v3",
        "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr": "Memo Program",
        "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter Aggregator v3",
        "PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY": "Phoenix DEX",
        "JBu1AL4obBcCMqKBBxhpWCNUt136ijcuMZLFvTP7iWdB": "Phoenix AMM Program",
        "worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth": "Wormhole Token Bridge",
        "3u8hJUVTA4jH1wYAyUur7FFZVQ8H635K3tSHHF4ssjQ5": "Raydium Liquidity Pool V4",
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM Program",
        "So11111111111111111111111111111111111111112": "Wrapped SOL",
    }
    
    return program_names.get(program_id, "Unknown Program")

def decode_account_data(data: str, encoding: str = "base64") -> bytes:
    """
    Decode account data from base64 or other encoding.
    
    Args:
        data: Encoded account data
        encoding: Encoding format
        
    Returns:
        bytes: Decoded binary data
    """
    if encoding == "base64":
        try:
            return base64.b64decode(data)
        except binascii.Error as e:
            logger.error(f"Error decoding base64: {e}")
            raise
    else:
        raise ValueError(f"Unsupported encoding: {encoding}")

def get_token_account_data(token_account: str) -> Dict:
    """
    Get and parse token account data.
    
    Args:
        token_account: Token account address
        
    Returns:
        Dict: Parsed token account data
    """
    try:
        account_info = solana_client.get_account_info(token_account)
        
        if not account_info or 'value' not in account_info:
            return None
            
        value = account_info['value']
        
        if not value or not value.get('data'):
            return None
            
        data = value['data']
        if isinstance(data, list) and len(data) == 2:
            raw_data = data[0]
            encoding = data[1]
            
            binary_data = decode_account_data(raw_data, encoding)
            
            # Parse token account data structure
            # This is a simplified version - a complete implementation would parse all fields
            # correctly and handle different versions of the token account structure
            
            # For SPL tokens, some key offsets:
            # Mint: 0-32 bytes (32 bytes)
            # Owner: 32-64 bytes (32 bytes)
            # Amount: 64-72 bytes (8 bytes)
            # Flags: 72-73 bytes (1 byte)
            
            if len(binary_data) >= 73:
                mint_bytes = binary_data[0:32]
                owner_bytes = binary_data[32:64]
                amount_bytes = binary_data[64:72]
                flags_byte = binary_data[72]
                
                mint = str(PublicKey(mint_bytes))
                owner = str(PublicKey(owner_bytes))
                amount = int.from_bytes(amount_bytes, byteorder='little')
                
                return {
                    'mint': mint,
                    'owner': owner,
                    'amount': amount,
                    'is_frozen': (flags_byte & 2) != 0,
                    'is_initialized': (flags_byte & 1) != 0,
                    'delegate': None  # Would parse delegate if needed
                }
        
        return None
    
    except Exception as e:
        logger.error(f"Error getting token account data: {e}")
        return None

def get_token_metadata(token_mint: str) -> Dict:
    """
    Get on-chain metadata for a token.
    
    Args:
        token_mint: Token mint address
        
    Returns:
        Dict: Token metadata
    """
    try:
        # First try using Helius enhanced API if available
        try:
            metadata = helius_client.get_token_metadata(token_mint)
            if metadata and metadata.get('name'):
                return metadata
        except Exception as e:
            logger.warning(f"Error getting metadata from Helius, falling back to on-chain lookup: {e}")
        
        # Fallback to on-chain metadata
        metadata_address = get_metadata_address(token_mint)
        account_info = solana_client.get_account_info(metadata_address)
        
        if not account_info or 'value' not in account_info:
            return {}
            
        value = account_info['value']
        
        if not value or not value.get('data'):
            return {}
            
        data = value['data']
        if isinstance(data, list) and len(data) == 2:
            raw_data = data[0]
            encoding = data[1]
            
            binary_data = decode_account_data(raw_data, encoding)
            
            # Parse metadata account data
            # This is a simplified version - actual parsing would be more complex
            
            # Metadata structure is not parsed here but you would:
            # 1. Check for correct discriminator at start
            # 2. Parse the name, symbol, uri, etc.
            # 3. Handle additional fields like creators
            
            # For simplicity, we're returning empty dict
            return {}
        
        return {}
    
    except Exception as e:
        logger.error(f"Error getting token metadata: {e}")
        return {} 