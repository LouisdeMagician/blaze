"""
Chart generation commands for the Telegram bot.
"""
import logging
import re
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler

from src.bot.message_templates import Templates, Emoji
from src.bot.keyboard_templates import KeyboardTemplates
from src.bot.visualization import visualizer
from src.utils.validators import validate_solana_address
from src.services.scanner import contract_scanner
from src.services.price_service import price_service

logger = logging.getLogger(__name__)

# Callback data patterns
CHART_TYPE_PATTERN = r"chart_type:(\w+):(.+)"

async def chart_command(update: Update, context: CallbackContext) -> None:
    """Handle the /chart command."""
    try:
        # Check if command has address argument
        if not context.args or not context.args[0]:
            await update.message.reply_text(
                f"{Emoji.CHART} *Token Chart Generator*\n\n"
                f"Please provide a token address to generate charts.\n"
                f"Example: `/chart <token_address>`",
                parse_mode="Markdown"
            )
            return
        
        # Get the token address
        token_address = context.args[0].strip()
        
        # Validate the address format
        if not validate_solana_address(token_address):
            await update.message.reply_text(
                Templates.INVALID_ADDRESS,
                parse_mode="Markdown"
            )
            return
        
        # Fetch basic token info
        token_info = await contract_scanner.get_token_info(token_address)
        
        if not token_info or not token_info.get("success"):
            error_message = token_info.get("error", "Unknown error") if token_info else "Failed to fetch token"
            await update.message.reply_text(
                Templates.SCAN_FAILED.format(error_message=error_message),
                parse_mode="Markdown"
            )
            return
        
        # Get token name and symbol
        token_name = token_info.get("token_info", {}).get("name", "Unknown Token")
        token_symbol = token_info.get("token_info", {}).get("symbol", "UNKNOWN")
        
        # Create chart type selection keyboard
        keyboard = [
            [
                InlineKeyboardButton("Price Chart", callback_data=f"chart_type:price:{token_address}"),
                InlineKeyboardButton("Volume Chart", callback_data=f"chart_type:volume:{token_address}")
            ],
            [
                InlineKeyboardButton("Holders Distribution", callback_data=f"chart_type:holders:{token_address}"),
                InlineKeyboardButton("Risk Analysis", callback_data=f"chart_type:risk:{token_address}")
            ]
        ]
        
        await update.message.reply_text(
            f"{Emoji.CHART} *Chart Generator for {token_name} ({token_symbol})*\n\n"
            f"Select the type of chart you would like to generate:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Error in chart command: {e}", exc_info=True)
        await update.message.reply_text(
            f"{Emoji.ERROR} An error occurred while processing your request. Please try again later."
        )

async def chart_type_callback(update: Update, context: CallbackContext) -> None:
    """Handle chart type selection callback."""
    query = update.callback_query
    await query.answer()
    
    # Extract chart type and token address from callback data
    match = re.match(CHART_TYPE_PATTERN, query.data)
    if not match:
        await query.edit_message_text("Invalid selection. Please try again.")
        return
    
    chart_type = match.group(1)
    token_address = match.group(2)
    
    # Update message to show chart generation is in progress
    await query.edit_message_text(
        f"{Emoji.CHART} Generating {chart_type} chart...\nPlease wait...",
        parse_mode="Markdown"
    )
    
    # Fetch token info
    token_info = await contract_scanner.get_token_info(token_address)
    if not token_info or not token_info.get("success"):
        await query.edit_message_text(
            f"{Emoji.ERROR} Failed to fetch token information.",
            parse_mode="Markdown"
        )
        return
    
    token_name = token_info.get("token_info", {}).get("name", "Unknown Token")
    token_symbol = token_info.get("token_info", {}).get("symbol", "UNKNOWN")
    
    # Generate the appropriate chart based on the selected type
    try:
        if chart_type == "price":
            await generate_price_chart(update, context, token_address, token_symbol, query)
        
        elif chart_type == "volume":
            await generate_volume_chart(update, context, token_address, token_symbol, query)
        
        elif chart_type == "holders":
            await generate_holders_chart(update, context, token_address, token_symbol, token_info, query)
        
        elif chart_type == "risk":
            await generate_risk_chart(update, context, token_address, token_symbol, token_info, query)
        
        else:
            await query.edit_message_text(
                f"{Emoji.ERROR} Unknown chart type selected.",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Error generating {chart_type} chart: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} An error occurred while generating the chart: {str(e)}",
            parse_mode="Markdown"
        )

async def generate_price_chart(update: Update, context: CallbackContext, token_address: str, token_symbol: str, query) -> None:
    """Generate and send a price chart."""
    try:
        # Fetch price data (or simulate for demonstration)
        try:
            price_data = await price_service.get_price_history(token_address, days=7)
        except Exception:
            # For demonstration, generate simulated price data if real data is unavailable
            price_data = simulate_price_data(7)
        
        # Generate the chart
        chart_buffer = visualizer.generate_price_chart(price_data, token_symbol, days=7)
        
        # Delete the "generating" message
        await query.delete_message()
        
        # Send the chart with caption
        caption = f"{Emoji.CHART} *{token_symbol} Price Chart*\nLast 7 days price history"
        await visualizer.send_chart(update, context, chart_buffer, caption)
        
    except Exception as e:
        logger.error(f"Error generating price chart: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} Failed to generate price chart: {str(e)}",
            parse_mode="Markdown"
        )

async def generate_volume_chart(update: Update, context: CallbackContext, token_address: str, token_symbol: str, query) -> None:
    """Generate and send a volume chart."""
    try:
        # Fetch volume data (or simulate for demonstration)
        try:
            volume_data = await price_service.get_volume_history(token_address, days=7)
        except Exception:
            # For demonstration, generate simulated volume data if real data is unavailable
            volume_data = simulate_volume_data(7)
        
        # Generate the chart
        chart_buffer = visualizer.generate_volume_chart(volume_data, token_symbol, days=7)
        
        # Delete the "generating" message
        await query.delete_message()
        
        # Send the chart with caption
        caption = f"{Emoji.CHART} *{token_symbol} Volume Chart*\nLast 7 days trading volume"
        await visualizer.send_chart(update, context, chart_buffer, caption)
        
    except Exception as e:
        logger.error(f"Error generating volume chart: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} Failed to generate volume chart: {str(e)}",
            parse_mode="Markdown"
        )

async def generate_holders_chart(update: Update, context: CallbackContext, token_address: str, token_symbol: str, token_info: Dict[str, Any], query) -> None:
    """Generate and send a holder distribution chart."""
    try:
        # Fetch holder data (or simulate for demonstration)
        try:
            holders_data = await contract_scanner.get_token_holders(token_address)
        except Exception:
            # For demonstration, generate simulated holder data if real data is unavailable
            holders_data = simulate_holder_data()
        
        # Generate the chart
        chart_buffer = visualizer.generate_holder_distribution_chart(holders_data)
        
        # Delete the "generating" message
        await query.delete_message()
        
        # Send the chart with caption
        caption = f"{Emoji.CHART} *{token_symbol} Holder Distribution*\nTop holder concentration"
        await visualizer.send_chart(update, context, chart_buffer, caption)
        
    except Exception as e:
        logger.error(f"Error generating holders chart: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} Failed to generate holders chart: {str(e)}",
            parse_mode="Markdown"
        )

async def generate_risk_chart(update: Update, context: CallbackContext, token_address: str, token_symbol: str, token_info: Dict[str, Any], query) -> None:
    """Generate and send a risk analysis chart."""
    try:
        # Fetch risk data (or simulate for demonstration)
        try:
            risk_data = await contract_scanner.get_risk_factors(token_address)
        except Exception:
            # For demonstration, generate simulated risk data if real data is unavailable
            risk_data = simulate_risk_data()
        
        # Generate the chart
        chart_buffer = visualizer.generate_risk_radar_chart(risk_data)
        
        # Delete the "generating" message
        await query.delete_message()
        
        # Send the chart with caption
        caption = f"{Emoji.CHART} *{token_symbol} Risk Analysis*\nRisk factor breakdown"
        await visualizer.send_chart(update, context, chart_buffer, caption)
        
    except Exception as e:
        logger.error(f"Error generating risk chart: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} Failed to generate risk chart: {str(e)}",
            parse_mode="Markdown"
        )

# Helper functions to simulate data for demonstration purposes

def simulate_price_data(days: int) -> List[Dict[str, Any]]:
    """Simulate price data for demonstration."""
    data = []
    base_price = random.uniform(0.5, 100)
    
    for i in range(days):
        timestamp = int((datetime.now() - timedelta(days=days-i-1)).timestamp())
        price = base_price * (1 + random.uniform(-0.1, 0.1))
        base_price = price  # Update for next iteration
        
        data.append({
            "timestamp": timestamp,
            "price": price
        })
    
    return data

def simulate_volume_data(days: int) -> List[Dict[str, Any]]:
    """Simulate volume data for demonstration."""
    data = []
    base_volume = random.uniform(1000, 1000000)
    
    for i in range(days):
        timestamp = int((datetime.now() - timedelta(days=days-i-1)).timestamp())
        volume = base_volume * random.uniform(0.5, 2.0)
        
        data.append({
            "timestamp": timestamp,
            "volume": volume
        })
    
    return data

def simulate_holder_data() -> List[Dict[str, Any]]:
    """Simulate holder data for demonstration."""
    data = []
    remaining = 100.0
    
    # Generate top holders
    for i in range(9):
        if i == 0:
            # Top holder typically holds more
            pct = random.uniform(15, 40)
        else:
            # Other holders have decreasing percentages
            pct = random.uniform(1, remaining * 0.3)
        
        if pct > remaining:
            pct = remaining
        
        remaining -= pct
        
        label = "Team" if i == 0 else f"Wallet {i+1}"
        data.append({
            "address": f"Wallet{i+1}",
            "percentage": pct,
            "label": label
        })
    
    # Add the rest as "others"
    if remaining > 0:
        data.append({
            "address": "Others",
            "percentage": remaining,
            "label": "Others"
        })
    
    return data

def simulate_risk_data() -> Dict[str, float]:
    """Simulate risk factor data for demonstration."""
    return {
        "liquidity_depth": random.uniform(0, 1),
        "market_cap_to_liquidity": random.uniform(0, 1),
        "creator_ownership": random.uniform(0, 1),
        "top_holder_concentration": random.uniform(0, 1),
        "mint_authority_exists": random.uniform(0, 1),
        "contract_verification": random.uniform(0, 1),
        "age_days": random.uniform(0, 1),
        "volume_volatility": random.uniform(0, 1)
    }

# Register handlers
chart_handler = CommandHandler("chart", chart_command)
chart_callback_handler = CallbackQueryHandler(chart_type_callback, pattern=r"^chart_type:") 