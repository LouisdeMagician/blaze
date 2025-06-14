import requests
import logging
from typing import Dict, Any, Optional
import time

logger = logging.getLogger(__name__)

class JupiterClient:
    """Client for Jupiter Aggregator API (DEX liquidity/route)."""
    BASE_URL = 'https://quote-api.jup.ag/v6'
    PRICE_URL = 'https://price.jup.ag/v6'
    
    def __init__(self):
        """Initialize the Jupiter client."""
        self.last_request_time = 0
        self.rate_limit_delay = 0.2  # 200ms between requests to avoid rate limiting
        
    def _rate_limit(self):
        """Apply rate limiting to avoid API throttling."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()

    def get_quote(self, input_mint: str, output_mint: str, amount: int) -> Dict[str, Any]:
        """Get DEX quote for a given input/output mint and amount."""
        self._rate_limit()
        url = f'{self.BASE_URL}/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount}'
        try:
            resp = requests.get(url, timeout=10)
            if not resp.ok:
                logger.warning(f'Jupiter quote failed with status {resp.status_code} for {input_mint}->{output_mint}')
                return {}
            data = resp.json()
            if not data:
                return {}
            return data
        except requests.exceptions.Timeout:
            logger.warning(f'Jupiter quote timed out for {input_mint}->{output_mint}')
            return {}
        except requests.exceptions.RequestException as e:
            logger.warning(f'Jupiter quote request failed for {input_mint}->{output_mint}: {e}')
            return {}
        except Exception as e:
            logger.warning(f'Jupiter quote failed for {input_mint}->{output_mint}: {e}')
            return {}

    def get_token_price(self, mint: str, vs_token: str = "USDC") -> Dict[str, Any]:
        """Fetch current token price vs USDC or another token from Jupiter Price API.
        
        Args:
            mint: The token mint address to get price for
            vs_token: The token to price against (default: USDC)
            
        Returns:
            Dict with price info or empty dict if unavailable
        """
        self._rate_limit()
        # Default USDC mint if not specified
        if vs_token == "USDC":
            vs_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            
        url = f"{self.PRICE_URL}/price?ids={mint}&vsToken={vs_token}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            if not data or mint not in data:
                return {}
                
            price_data = data.get(mint, {})
            if "price" not in price_data:
                return {}
                
            return {
                "price": float(price_data.get("price", 0)),
                "price_change_24h": price_data.get("priceChange24h", 0),
                "vs_token": vs_token,
                "timestamp": int(time.time())
            }
        except Exception as e:
            logger.warning(f'Jupiter price failed for {mint}: {e}')
            return {}
            
    def get_token_liquidity(self, mint: str) -> Dict[str, Any]:
        """Get liquidity information for a token from Jupiter.
        
        Returns information about the token's liquidity across DEXes.
        
        Args:
            mint: The token mint address
            
        Returns:
            Dict with liquidity info or empty dict if unavailable
        """
        self._rate_limit()
        # USDC mint for reference
        usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        
        # Get quotes for different amounts to calculate price impact
        amounts = [100_000, 1_000_000, 10_000_000]  # $0.1, $1, $10 in USDC (6 decimals)
        quotes = {}
        
        for amount in amounts:
            try:
                quote = self.get_quote(usdc_mint, mint, amount)
                if quote and "priceImpactPct" in quote:
                    quotes[str(amount)] = {
                        "price_impact_pct": float(quote.get("priceImpactPct", 0)) * 100,
                        "out_amount": int(quote.get("outAmount", 0)),
                        "routes_count": len(quote.get("routePlan", [])),
                    }
            except Exception as e:
                logger.debug(f"Error getting quote for {amount} USDC -> {mint}: {e}")
                
        if not quotes:
            return {}
            
        return {
            "quotes": quotes,
            "timestamp": int(time.time())
        } 