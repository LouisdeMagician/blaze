"""
Provider Adapter for blockchain data providers.
Implements adapter pattern for standardizing blockchain data access.
"""
import logging
import time
import asyncio
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Tuple, Type, Protocol, runtime_checkable
from abc import ABC, abstractmethod

from src.blockchain.solana_client import solana_client, SolanaClientError
from src.blockchain.helius_client import helius_client, HeliusClientError
from src.services.cache_service import cache_service, CacheLevel, DataCategory
from src.blockchain.enhanced_rpc_provider import enhanced_solana_provider

logger = logging.getLogger(__name__)

class ProviderType(Enum):
    """Types of blockchain data providers."""
    SOLANA_RPC = "solana_rpc"
    HELIUS = "helius"
    SOLSCAN = "solscan"
    JUPITER = "jupiter"
    AUTO = "auto"  # Automatically select the best provider

class ResourceType(Enum):
    """Types of blockchain resources."""
    TOKEN = "token"
    ACCOUNT = "account"
    TRANSACTION = "transaction"
    NFT = "nft"
    PRICE = "price"
    LIQUIDITY = "liquidity"
    HOLDER = "holder"
    PROGRAM = "program"

class ProviderStatus(Enum):
    """Status of a provider."""
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

class BlockchainAdapter(ABC):
    """Abstract base class for blockchain provider adapters."""
    
    @abstractmethod
    async def get_token_info(self, address: str) -> Optional[Dict[str, Any]]:
        """Get token information."""
        pass
    
    @abstractmethod
    async def get_account_info(self, address: str) -> Optional[Dict[str, Any]]:
        """Get account information."""
        pass
    
    @abstractmethod
    async def get_transaction(self, signature: str) -> Optional[Dict[str, Any]]:
        """Get transaction details."""
        pass
    
    @abstractmethod
    async def get_token_holders(self, address: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get token holders."""
        pass
    
    @abstractmethod
    async def get_token_price(self, address: str) -> Optional[Dict[str, Any]]:
        """Get token price information."""
        pass
    
    @abstractmethod
    async def get_token_liquidity(self, address: str) -> Optional[Dict[str, Any]]:
        """Get token liquidity information."""
        pass
    
    @abstractmethod
    async def get_program_accounts(self, program_id: str, filters: List[Dict] = None) -> List[Dict[str, Any]]:
        """Get program accounts."""
        pass
    
    @abstractmethod
    async def get_status(self) -> ProviderStatus:
        """Get provider status."""
        pass

class SolanaRpcAdapter(BlockchainAdapter):
    """Adapter for Solana RPC provider."""
    
    def __init__(self):
        """Initialize the adapter."""
        self.client = solana_client
        self.enhanced_provider = enhanced_solana_provider
        self.last_status_check = 0
        self.status = ProviderStatus.UNKNOWN
        self.status_check_interval = 60  # 1 minute
    
    async def get_token_info(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get token information from Solana RPC.
        
        Args:
            address: Token address
            
        Returns:
            Optional[Dict]: Token information or None if not found
        """
        try:
            # Use enhanced provider
            account_info = await self.enhanced_provider.call_method("getAccountInfo", [address, {"encoding": "jsonParsed"}])
            
            if not account_info or not account_info.get("result"):
                return None
            
            # Parse the account info as SPL token
            result = account_info.get("result", {}).get("value", {})
            
            # Extract token info
            token_info = {
                "address": address,
                "raw_data": result,
                "source": "solana_rpc"
            }
            
            # Try to get token metadata if available
            token_metadata = await self.enhanced_provider.call_method("getTokenSupply", [address])
            
            if token_metadata and token_metadata.get("result"):
                supply_info = token_metadata.get("result", {}).get("value", {})
                token_info.update({
                    "supply": supply_info.get("amount"),
                    "decimals": supply_info.get("decimals")
                })
            
            return token_info
            
        except Exception as e:
            logger.error(f"Error getting token info for {address}: {e}")
            return None
    
    async def get_account_info(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get account information from Solana RPC.
        
        Args:
            address: Account address
            
        Returns:
            Optional[Dict]: Account information or None if not found
        """
        try:
            # Use enhanced provider
            account_info = await self.enhanced_provider.call_method("getAccountInfo", [address, {"encoding": "jsonParsed"}])
            
            if not account_info or not account_info.get("result"):
                return None
            
            # Format the account info
            result = account_info.get("result", {}).get("value", {})
            
            return {
                "address": address,
                "data": result,
                "source": "solana_rpc"
            }
            
        except Exception as e:
            logger.error(f"Error getting account info for {address}: {e}")
            return None
    
    async def get_transaction(self, signature: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction details from Solana RPC.
        
        Args:
            signature: Transaction signature
            
        Returns:
            Optional[Dict]: Transaction details or None if not found
        """
        try:
            # Use enhanced provider
            tx_info = await self.enhanced_provider.call_method(
                "getTransaction", 
                [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
            )
            
            if not tx_info or not tx_info.get("result"):
                return None
            
            # Format the transaction info
            result = tx_info.get("result", {})
            
            return {
                "signature": signature,
                "data": result,
                "source": "solana_rpc"
            }
            
        except Exception as e:
            logger.error(f"Error getting transaction {signature}: {e}")
            return None
    
    async def get_token_holders(self, address: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get token holders from Solana RPC.
        
        Args:
            address: Token address
            limit: Maximum number of holders to return
            
        Returns:
            List[Dict]: Token holders or empty list if none found
        """
        try:
            # Get token accounts by token mint
            params = [
                address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "encoding": "jsonParsed"}
            ]
            token_accounts = await self.enhanced_provider.call_method("getTokenAccountsByMint", params)
            
            if not token_accounts or not token_accounts.get("result"):
                return []
            
            # Extract holder information
            accounts = token_accounts.get("result", {}).get("value", [])
            
            holders = []
            for account in accounts[:limit]:
                account_data = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                owner = account_data.get("owner")
                amount = account_data.get("tokenAmount", {}).get("amount")
                
                if owner and amount:
                    holders.append({
                        "address": owner,
                        "balance": amount,
                        "account": account.get("pubkey"),
                        "source": "solana_rpc"
                    })
            
            # Sort by balance (descending)
            holders.sort(key=lambda x: int(x.get("balance", 0)), reverse=True)
            
            return holders[:limit]
            
        except Exception as e:
            logger.error(f"Error getting token holders for {address}: {e}")
            return []
    
    async def get_token_price(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get token price information from Solana RPC.
        
        Args:
            address: Token address
            
        Returns:
            Optional[Dict]: Token price information or None if not available
        """
        # Not available from basic RPC
        return None
    
    async def get_token_liquidity(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get token liquidity information from Solana RPC.
        
        Args:
            address: Token address
            
        Returns:
            Optional[Dict]: Token liquidity information or None if not available
        """
        # Not available from basic RPC
        return None
    
    async def get_program_accounts(self, program_id: str, filters: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Get program accounts from Solana RPC.
        
        Args:
            program_id: Program ID
            filters: Optional filters
            
        Returns:
            List[Dict]: Program accounts or empty list if none found
        """
        try:
            # Convert filters to RPC format
            rpc_filters = []
            if filters:
                for filter_item in filters:
                    if 'dataSize' in filter_item:
                        rpc_filters.append({"dataSize": filter_item['dataSize']})
                    elif 'memcmp' in filter_item:
                        rpc_filters.append({
                            "memcmp": {
                                "offset": filter_item['memcmp'].get('offset', 0),
                                "bytes": filter_item['memcmp'].get('bytes', '')
                            }
                        })
            
            # Prepare parameters
            params = [program_id, {"encoding": "base64", "filters": rpc_filters}]
            
            # Call RPC
            result = await self.enhanced_provider.call_method("getProgramAccounts", params)
            
            if not result or not result.get("result"):
                return []
            
            # Process results
            accounts = result.get("result", [])
            
            return [
                {
                    "pubkey": account.get("pubkey"),
                    "account": account.get("account"),
                    "source": "solana_rpc"
                }
                for account in accounts
            ]
            
        except Exception as e:
            logger.error(f"Error getting program accounts for {program_id}: {e}")
            return []
    
    async def get_status(self) -> ProviderStatus:
        """
        Get provider status.
        
        Returns:
            ProviderStatus: Current provider status
        """
        # Check if we need to refresh status
        current_time = time.time()
        if current_time - self.last_status_check < self.status_check_interval:
            return self.status
        
        self.last_status_check = current_time
        
        try:
            # Get cluster health
            health = await self.enhanced_provider.call_method("getHealth", [])
            
            if health and health.get("result") == "ok":
                self.status = ProviderStatus.ONLINE
            else:
                self.status = ProviderStatus.DEGRADED
            
            # Get manager stats to check if the circuit breaker is open
            manager_stats = self.enhanced_provider.get_manager_stats()
            
            # Check if any provider's circuit breaker is open
            for provider_name, provider_stats in manager_stats.get("providers", {}).items():
                circuit_state = provider_stats.get("circuit_breaker", {}).get("state")
                if circuit_state == "open":
                    logger.warning(f"Circuit breaker is open for provider {provider_name}")
                    self.status = ProviderStatus.DEGRADED
                    break
            
            return self.status
            
        except Exception as e:
            logger.error(f"Error checking RPC provider status: {e}")
            self.status = ProviderStatus.OFFLINE
            return self.status

class HeliusAdapter(BlockchainAdapter):
    """Adapter for Helius provider."""
    
    def __init__(self):
        """Initialize the adapter."""
        self.client = helius_client
        self.last_status_check = 0
        self.status = ProviderStatus.UNKNOWN
        self.status_check_interval = 60  # 1 minute
    
    async def get_token_info(self, address: str) -> Optional[Dict[str, Any]]:
        try:
            token_data = self.client.get_token_data(address)
            if not token_data or not token_data.get("name"):
                logger.warning(f"Helius returned no or incomplete token info for {address}, falling back to Solana RPC.")
                # Fallback to Solana RPC if available
                rpc_adapter = SolanaRpcAdapter()
                return await rpc_adapter.get_token_info(address)
            token_data["source"] = "helius"
            return token_data
        except HeliusClientError as e:
            logger.error(f"Error getting token info from Helius for {address}: {e}")
            rpc_adapter = SolanaRpcAdapter()
            return await rpc_adapter.get_token_info(address)
        except Exception as e:
            logger.error(f"Unexpected error getting token info from Helius: {e}", exc_info=True)
            rpc_adapter = SolanaRpcAdapter()
            return await rpc_adapter.get_token_info(address)
    
    async def get_account_info(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get account information from Helius.
        """
        # Helius doesn't have a direct account info endpoint
        # Fallback to using transactions for basic info
        try:
            # Not implemented in stub, return minimal info
            return {
                "address": address,
                "recent_activity": True,
                "source": "helius"
            }
        except HeliusClientError as e:
            logger.error(f"Error getting account info from Helius for {address}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting account info from Helius: {e}", exc_info=True)
            return None
    
    async def get_transaction(self, signature: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction details from Helius.
        """
        # Not implemented in stub
        return None
    
    async def get_token_holders(self, address: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            holders = self.client.get_token_holders(address, limit)
            if not holders:
                logger.warning(f"Helius returned no holders for {address}, falling back to Solana RPC.")
                rpc_adapter = SolanaRpcAdapter()
                return await rpc_adapter.get_token_holders(address, limit)
            for holder in holders:
                holder["source"] = "helius"
            return holders
        except HeliusClientError as e:
            logger.error(f"Error getting token holders from Helius for {address}: {e}")
            rpc_adapter = SolanaRpcAdapter()
            return await rpc_adapter.get_token_holders(address, limit)
        except Exception as e:
            logger.error(f"Unexpected error getting token holders from Helius: {e}", exc_info=True)
            rpc_adapter = SolanaRpcAdapter()
            return await rpc_adapter.get_token_holders(address, limit)
    
    def get_token_price(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get token price information from Helius.
        """
        try:
            price_data = self.client.get_token_price_data(address)
            if price_data:
                price_data["source"] = "helius"
            return price_data
        except HeliusClientError as e:
            logger.error(f"Error getting token price from Helius for {address}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting token price from Helius: {e}", exc_info=True)
            return None
    
    def get_token_liquidity(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get token liquidity information from Helius.
        """
        try:
            dex_info = self.client.get_dex_info(address)
            if dex_info:
                dex_info["source"] = "helius"
            return dex_info
        except HeliusClientError as e:
            logger.error(f"Error getting token liquidity from Helius for {address}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting token liquidity from Helius: {e}", exc_info=True)
            return None
    
    def get_program_accounts(self, program_id: str, filters: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Get program accounts from Helius.
        """
        # Not directly available in Helius
        return []
    
    def get_status(self) -> ProviderStatus:
        """
        Get provider status.
        
        Returns:
            ProviderStatus: Current provider status
        """
        now = time.time()
        
        # Only check status periodically
        if now - self.last_status_check < self.status_check_interval and self.status != ProviderStatus.UNKNOWN:
            return self.status
        
        try:
            # Check if API key is configured
            if not self.client.api_key:
                self.status = ProviderStatus.OFFLINE
                self.last_status_check = now
                return self.status
            
            # Simple health check - just make a small request
            self.client.initialize()
            test_address = "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt"  # Sample address
            result = self.client.get_token_transactions(test_address, 1)
            
            if result:
                self.status = ProviderStatus.ONLINE
            else:
                self.status = ProviderStatus.DEGRADED
                
            self.last_status_check = now
            return self.status
            
        except Exception as e:
            logger.error(f"Error checking Helius status: {e}")
            self.status = ProviderStatus.OFFLINE
            self.last_status_check = now
            return self.status

class ProviderManager:
    """Manager for blockchain provider adapters."""
    
    def __init__(self):
        """Initialize the manager."""
        self.adapters = {}
        self.preferred_providers = {
            ResourceType.TOKEN: ProviderType.HELIUS,
            ResourceType.ACCOUNT: ProviderType.SOLANA_RPC,
            ResourceType.TRANSACTION: ProviderType.HELIUS,
            ResourceType.NFT: ProviderType.HELIUS,
            ResourceType.PRICE: ProviderType.HELIUS,
            ResourceType.LIQUIDITY: ProviderType.JUPITER,
            ResourceType.HOLDER: ProviderType.HELIUS,
            ResourceType.PROGRAM: ProviderType.SOLANA_RPC,
        }
        self.cache_service = cache_service
        self.enhanced_solana_provider = enhanced_solana_provider
        
        # Initialize adapters
        self.initialize_adapters()
    
    def initialize_adapters(self):
        """Initialize blockchain provider adapters."""
        self.adapters[ProviderType.SOLANA_RPC] = SolanaRpcAdapter()
        self.adapters[ProviderType.HELIUS] = HeliusAdapter()
    
    async def get_token_info(self, address: str, provider_type: ProviderType = ProviderType.AUTO) -> Optional[Dict[str, Any]]:
        """
        Get token information using the appropriate provider.
        
        Args:
            address: Token address
            provider_type: Provider type
            
        Returns:
            Optional[Dict]: Token information or None if not found
        """
        # Try to get from cache first
        cache_key = f"token_info:{address}"
        result = await self.cache_service.get(cache_key)
        if result:
            return result
        
        adapter = await self.get_adapter(provider_type, ResourceType.TOKEN)
        result = await adapter.get_token_info(address)
        
        # Cache the result if found
        if result:
            await self.cache_service.set(cache_key, result, 3600)  # 1 hour TTL
        
        return result
    
    async def get_account_info(self, address: str, provider_type: ProviderType = ProviderType.AUTO) -> Optional[Dict[str, Any]]:
        """
        Get account information using the appropriate provider.
        
        Args:
            address: Account address
            provider_type: Provider type
            
        Returns:
            Optional[Dict]: Account information or None if not found
        """
        # Try to get from cache first
        cache_key = f"account_info:{address}"
        result = await self.cache_service.get(cache_key)
        if result:
            return result
        
        adapter = await self.get_adapter(provider_type, ResourceType.ACCOUNT)
        result = await adapter.get_account_info(address)
        
        # Cache the result if found (shorter TTL as account data can change)
        if result:
            await self.cache_service.set(cache_key, result, 300)  # 5 minutes TTL
        
        return result
    
    async def get_token_holders(self, address: str, limit: int = 20, 
                               provider_type: ProviderType = ProviderType.AUTO) -> List[Dict[str, Any]]:
        """
        Get token holders using the appropriate provider.
        
        Args:
            address: Token address
            limit: Maximum number of holders to return
            provider_type: Provider type
            
        Returns:
            List[Dict]: Token holders or empty list if none found
        """
        # Try to get from cache first
        cache_key = f"token_holders:{address}:{limit}"
        result = await self.cache_service.get(cache_key)
        if result:
            return result
        
        adapter = await self.get_adapter(provider_type, ResourceType.HOLDER)
        result = await adapter.get_token_holders(address, limit)
        
        # Cache the result if found
        if result:
            await self.cache_service.set(cache_key, result, 900)  # 15 minutes TTL
        
        return result
    
    async def get_token_price(self, address: str, provider_type: ProviderType = ProviderType.AUTO) -> Optional[Dict[str, Any]]:
        """
        Get token price using the appropriate provider.
        
        Args:
            address: Token address
            provider_type: Provider type
            
        Returns:
            Optional[Dict]: Token price or None if not available
        """
        # Try to get from cache first (short TTL for price data)
        cache_key = f"token_price:{address}"
        result = await self.cache_service.get(cache_key)
        if result:
            return result
        
        adapter = await self.get_adapter(provider_type, ResourceType.PRICE)
        result = await adapter.get_token_price(address)
        
        # Cache the result if found
        if result:
            await self.cache_service.set(cache_key, result, 60)  # 1 minute TTL for price data
        
        return result
    
    async def get_token_liquidity(self, address: str, provider_type: ProviderType = ProviderType.AUTO) -> Optional[Dict[str, Any]]:
        """
        Get token liquidity using the appropriate provider.
        
        Args:
            address: Token address
            provider_type: Provider type
            
        Returns:
            Optional[Dict]: Token liquidity or None if not available
        """
        # Try to get from cache first
        cache_key = f"token_liquidity:{address}"
        result = await self.cache_service.get(cache_key)
        if result:
            return result
        
        adapter = await self.get_adapter(provider_type, ResourceType.LIQUIDITY)
        result = await adapter.get_token_liquidity(address)
        
        # Cache the result if found
        if result:
            await self.cache_service.set(cache_key, result, 300)  # 5 minutes TTL
        
        return result
    
    async def check_provider_health(self) -> Dict[ProviderType, ProviderStatus]:
        """
        Check the health status of all providers.
        
        Returns:
            Dict[ProviderType, ProviderStatus]: Provider status by type
        """
        results = {}
        
        for provider_type, adapter in self.adapters.items():
            try:
                status = await adapter.get_status()
                results[provider_type] = status
            except Exception as e:
                logger.error(f"Error checking provider health for {provider_type}: {e}")
                results[provider_type] = ProviderStatus.UNKNOWN
        
        return results

# Initialize the provider manager
provider_manager = ProviderManager() 