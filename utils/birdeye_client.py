import requests
import logging
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

class BirdeyeClient:
    """Client for Birdeye public API (price/volume history)."""
    BASE_URL = 'https://public-api.birdeye.so'

    def __init__(self):
        """Initialize the Birdeye client with API key from environment."""
        self.api_key = os.getenv('BIRDEYE_API_KEY', '')
        
    def _get_headers(self):
        """Get headers with API key if available."""
        if self.api_key:
            return {
                'X-API-KEY': self.api_key,
                'accept': 'application/json'
            }
        return {}

    def get_token_price(self, mint: str) -> Dict[str, Any]:
        """Get the current price for a token mint. Uses /defi/price first, then falls back."""
        headers = self._get_headers()
        url = f'{self.BASE_URL}/defi/price?address={mint}&chain=solana'
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json().get('data')
            if not data or not isinstance(data, dict):
                # Fallback to legacy endpoint (older API)
                url_fallback = f'{self.BASE_URL}/public/price?address={mint}'
                resp2 = requests.get(url_fallback, headers=headers, timeout=10)
                resp2.raise_for_status()
                data = resp2.json().get('data') or resp2.json().get('price')
                if not data:
                    logger.warning(f"Birdeye price fallback data for {mint} is empty: {resp2.text}")
                    return {}
                return data
            return data
        except Exception as e:
            logger.warning(f'Birdeye token price failed for {mint}: {e}')
            return {}

    def get_price_history(self, mint: str, timeframe: str = '1d') -> List[Dict[str, Any]]:
        """Get historical price and volume for a token mint."""
        headers = self._get_headers()
        url = f'{self.BASE_URL}/defi/history_price?address={mint}&timeframe={timeframe}&chain=solana'
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json().get('data', {}).get('items', [])
        except Exception as e:
            logger.warning(f'Birdeye price history failed for {mint}: {e}')
            return []

    def get_markets(self, mint: str) -> List[Dict[str, Any]]:
        """Get active markets/pairs for a token including liquidity/volume stats."""
        base_mint = mint[:-4] if mint.endswith('pump') else mint
        headers = self._get_headers()
        url = f'{self.BASE_URL}/defi/token_overview?address={base_mint}&chain=solana'
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            # The new endpoint returns a single object, not a list of markets.
            # We will simulate the old list-based structure for compatibility.
            data = resp.json().get('data')
            if not data or not isinstance(data, dict):
                return []
            
            return [{
                'liquidity': data.get('liquidity', 0),
                'liquidityUsd': data.get('liquidity', 0),
                'volume24hUsd': data.get('volume24h', 0),
                'price': data.get('price', 0),
                'priceChange24h': data.get('priceChange24h', 0),
                'source': 'birdeye_overview'
            }]
        except Exception as e:
            logger.warning('Birdeye get_markets failed for %s: %s', mint, e)
            # Fallback to DexScreener pairs for liquidity info
            try:
                ds_url = f'https://api.dexscreener.com/latest/dex/tokens/{base_mint}'
                ds_resp = requests.get(ds_url, timeout=10)
                if ds_resp.ok:
                    pairs = ds_resp.json().get('pairs', [])
                    return [
                        {
                            'dex': p.get('dexId', 'Unknown'),
                            'marketAddress': p.get('pairAddress', ''),
                            'quoteSymbol': p.get('quoteSymbol', 'Unknown'),
                            'liquidityUsd': float(p.get('liquidity', {}).get('usd', 0) or 0),
                            'volume24hUsd': float(p.get('volume', {}).get('h24', 0) or 0),
                        }
                        for p in pairs
                    ]
            except Exception as _e:
                logger.debug('DexScreener fallback failed for %s: %s', base_mint, _e)
            return [] 