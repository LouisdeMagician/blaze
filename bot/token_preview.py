"""
Token preview card generator for Telegram bot.
Provides rich visual previews of tokens.
"""
import io
import logging
from typing import Dict, Any, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from src.bot.message_templates import Emoji
from src.services.scanner import contract_scanner

logger = logging.getLogger(__name__)

class TokenPreviewGenerator:
    """Generate visual preview cards for tokens"""
    
    @staticmethod
    async def generate_token_preview(token_address: str, include_price: bool = True) -> Optional[io.BytesIO]:
        """
        Generate a visual preview card for a token.
        
        Args:
            token_address: The token address
            include_price: Whether to include price information
            
        Returns:
            BytesIO: Image buffer or None if error
        """
        try:
            # Fetch token data
            token_data = await contract_scanner.get_token_info(token_address)
            if not token_data or not token_data.get("success"):
                logger.error(f"Failed to fetch token data for {token_address}")
                return None
            
            token_info = token_data.get("token_info", {})
            risk_data = token_data.get("risk_assessment", {})
            
            # Extract needed data
            token_name = token_info.get("name", "Unknown Token")
            token_symbol = token_info.get("symbol", "????")
            token_supply = token_info.get("supply", "Unknown")
            holders_count = token_info.get("holders", "Unknown")
            risk_level = risk_data.get("risk_level", "unknown").lower()
            
            # Fetch price data if needed
            price_data = None
            price_change = None
            if include_price:
                # In a real implementation, fetch this from price service
                # For now, using placeholder data
                price_data = 0.00123
                price_change = -2.5  # percentage
            
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.set_facecolor("#f5f5f5")
            
            # Remove axes
            ax.set_axis_off()
            
            # Add border
            border = patches.Rectangle((0, 0), 1, 1, linewidth=2, edgecolor='#e0e0e0', facecolor='none', transform=ax.transAxes)
            ax.add_patch(border)
            
            # Add token name and symbol
            ax.text(0.05, 0.85, token_name, fontsize=18, weight='bold')
            ax.text(0.05, 0.75, f"${token_symbol}", fontsize=14, color='#666666')
            
            # Add token address (shortened)
            short_address = f"{token_address[:6]}...{token_address[-6:]}"
            ax.text(0.05, 0.65, f"Address: {short_address}", fontsize=10, color='#999999')
            
            # Add risk level indicator
            risk_colors = {
                "low": "#4CAF50",
                "medium": "#FFC107",
                "high": "#F44336",
                "critical": "#9C27B0",
                "unknown": "#9E9E9E"
            }
            risk_color = risk_colors.get(risk_level, "#9E9E9E")
            
            # Add circular risk indicator
            risk_circle = patches.Circle((0.85, 0.8), 0.08, color=risk_color)
            ax.add_patch(risk_circle)
            ax.text(0.85, 0.8, risk_level[0].upper(), fontsize=14, color='white', 
                    ha='center', va='center', weight='bold')
            
            # Add risk level text
            ax.text(0.85, 0.7, f"Risk: {risk_level.capitalize()}", fontsize=10, ha='center')
            
            # Add token metrics
            ax.text(0.05, 0.5, "Supply:", fontsize=12, color='#666666')
            ax.text(0.2, 0.5, f"{token_supply:,}", fontsize=12)
            
            ax.text(0.05, 0.4, "Holders:", fontsize=12, color='#666666')
            ax.text(0.2, 0.4, f"{holders_count:,}", fontsize=12)
            
            # Add price information if available
            if price_data is not None:
                ax.text(0.05, 0.3, "Price:", fontsize=12, color='#666666')
                ax.text(0.2, 0.3, f"${price_data:.8f}", fontsize=12)
                
                # Add price change with color
                change_color = "#4CAF50" if price_change >= 0 else "#F44336"
                change_prefix = "+" if price_change >= 0 else ""
                ax.text(0.05, 0.2, "24h Change:", fontsize=12, color='#666666')
                ax.text(0.2, 0.2, f"{change_prefix}{price_change:.2f}%", fontsize=12, color=change_color)
            
            # Add footer with timestamp
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ax.text(0.5, 0.05, f"Generated: {timestamp}", fontsize=8, ha='center', color='#999999')
            
            # Save to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close(fig)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generating token preview: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def generate_token_comparison(token1_address: str, token2_address: str) -> Optional[io.BytesIO]:
        """
        Generate a comparison card for two tokens.
        
        Args:
            token1_address: First token address
            token2_address: Second token address
            
        Returns:
            BytesIO: Image buffer or None if error
        """
        try:
            # Fetch token data
            token1_data = await contract_scanner.get_token_info(token1_address)
            token2_data = await contract_scanner.get_token_info(token2_address)
            
            if not token1_data or not token1_data.get("success") or not token2_data or not token2_data.get("success"):
                logger.error(f"Failed to fetch token data for comparison")
                return None
            
            token1_info = token1_data.get("token_info", {})
            token2_info = token2_data.get("token_info", {})
            
            # Extract needed data
            token1_name = token1_info.get("name", "Unknown Token")
            token1_symbol = token1_info.get("symbol", "????")
            token2_name = token2_info.get("name", "Unknown Token")
            token2_symbol = token2_info.get("symbol", "????")
            
            # Create figure with two columns
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
            
            # Set background color
            ax1.set_facecolor("#f8f8f8")
            ax2.set_facecolor("#f8f8f8")
            
            # Remove axes
            ax1.set_axis_off()
            ax2.set_axis_off()
            
            # Add titles
            ax1.set_title(f"{token1_name} (${token1_symbol})", fontsize=16, weight='bold')
            ax2.set_title(f"{token2_name} (${token2_symbol})", fontsize=16, weight='bold')
            
            # Compare metrics
            metrics = [
                ("Supply", token1_info.get("supply", "Unknown"), token2_info.get("supply", "Unknown")),
                ("Holders", token1_info.get("holders", "Unknown"), token2_info.get("holders", "Unknown")),
                ("Age (days)", token1_info.get("age_days", "Unknown"), token2_info.get("age_days", "Unknown")),
                ("Liquidity", token1_info.get("liquidity", "Unknown"), token2_info.get("liquidity", "Unknown")),
                ("Market Cap", token1_info.get("market_cap", "Unknown"), token2_info.get("market_cap", "Unknown"))
            ]
            
            # Plot metrics
            for i, (metric, val1, val2) in enumerate(metrics):
                y_pos = 0.8 - (i * 0.15)
                
                # Left token
                ax1.text(0.1, y_pos, metric, fontsize=12, color='#666666')
                ax1.text(0.5, y_pos, str(val1), fontsize=12, ha='right')
                
                # Right token
                ax2.text(0.1, y_pos, metric, fontsize=12, color='#666666')
                ax2.text(0.5, y_pos, str(val2), fontsize=12, ha='right')
            
            # Add divider line
            fig.subplots_adjust(wspace=0.05)
            ax1.axvline(x=1, color='#dddddd', linestyle='-', linewidth=1)
            
            # Add footer
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fig.text(0.5, 0.05, f"Comparison generated: {timestamp}", fontsize=8, ha='center', color='#999999')
            
            # Save to buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            plt.close(fig)
            
            return buffer
            
        except Exception as e:
            logger.error(f"Error generating token comparison: {e}", exc_info=True)
            return None

# Singleton instance
token_preview_generator = TokenPreviewGenerator() 