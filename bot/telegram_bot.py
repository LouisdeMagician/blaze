print("[DEBUG] telegram_bot.py is starting up")
from typing import Dict, Any, List, Optional, Tuple, Union, cast
import logging
import re
import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv
import json
import sys
import threading
import time
from telegram.utils.request import Request
from urllib3.util.retry import Retry

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode,
    InlineQueryResultArticle, InputTextMessageContent, ChatAction
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
    CallbackContext, CallbackQueryHandler, ConversationHandler,
    InlineQueryHandler
)

# Load environment variables
load_dotenv()

from config.config import config
from src.services.scanner import contract_scanner
from src.services.advanced_scanner import advanced_scanner
from src.utils.session_manager import session_manager
from src.bot.commands.enhanced_scan import enhanced_scan_handler
from src.analysis.token_analyzer import token_analyzer, analyze_token_sync
from src.models.analysis_result import AnalysisType
from src.utils.message_formatter import split_message, format_token_info
from src.utils.validators import validate_solana_address
from src.utils.rate_limiter import rate_limiter
from src.services.cache_service import memory_cache
from src.bot.message_templates import Templates, Emoji
from src.bot.keyboard_templates import KeyboardTemplates
from src.bot.commands.chart_command import chart_handler, chart_callback_handler
from src.bot.commands.suggestion_system import suggestion_system
from src.bot.commands.preview_command import preview_handler, preview_callback
from src.bot.commands.preview_command import get_preview_handler
from src.bot.commands.suggestion_system import get_suggestion_handler
from src.bot.commands.advanced_analysis_command import get_advanced_analysis_handler
from src.bot.commands.account_visualization_command import get_account_visualization_handler
from src.bot.commands.defi_analysis_command import get_defi_analysis_handler
from src.bot.help_command import help_command, get_help_handler
from src.services.data_pipeline import DataPipeline
from src.services.deep_scan_orchestrator import DeepScanOrchestrator
from src.bot.formatters.deep_scan_formatter import format_deep_scan_result

logger = logging.getLogger(__name__)

# Conversation states
AWAITING_CONTRACT_ADDRESS = 1
AWAITING_ANALYSIS_TYPE = 2
AWAITING_CONFIRMATION = 3
CHOOSING_SCAN_TYPE = 4
ENTERING_ADDRESS = 5
CONFIRMING_SCAN = 6

# In-memory user context storage
USER_CONTEXTS = {}

# Initialise orchestrator once
deep_scan_orchestrator = DeepScanOrchestrator()

# Bot owner ID for privileged commands
BOT_OWNER_ID = os.getenv('BOT_OWNER_ID')

# Command handlers

def start_command(update: Update, context: CallbackContext) -> None:
    """Handle the /start command."""
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        # Store user context in memory for the session
        user_id = str(user.id)
        if user_id not in USER_CONTEXTS:
            USER_CONTEXTS[user_id] = {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "last_active": datetime.now(),
                "session_data": {}
            }
            is_new_user = True
        else:
            # Update last active time
            USER_CONTEXTS[user_id]["last_active"] = datetime.now()
            is_new_user = False
        # Use template for welcome message
        welcome_text = Templates.WELCOME
        # Add personalized greeting for returning users
        if not is_new_user:
            welcome_text = f"Welcome back, {user.first_name}!\n\n" + welcome_text
        # If we previously sent a start-menu message, delete it to avoid showing stale keyboards
        prev_msg_id = USER_CONTEXTS[user_id].get('last_start_msg_id')
        if prev_msg_id:
            try:
                context.bot.delete_message(chat_id=chat_id, message_id=prev_msg_id)
            except Exception as ex:
                logger.debug(f"Could not delete old start menu ({prev_msg_id}): {ex}")

        # Create menu keyboard with common actions
        keyboard = [
            [
                InlineKeyboardButton("Quick Scan", callback_data="menu:scan"),
                InlineKeyboardButton("Deep Scan", callback_data="menu:deep_scan")
            ],
            [
                InlineKeyboardButton("Generate Chart", callback_data="menu:chart"),
                InlineKeyboardButton("Token Preview", callback_data="menu:preview")
            ],
            [
                InlineKeyboardButton("Advanced Analysis", callback_data="menu:advanced_analysis")
            ]
        ]
        sent = context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Remember this message id so we can delete it next time
        USER_CONTEXTS[user_id]['last_start_msg_id'] = sent.message_id
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="An error occurred while processing your request. Please try again later."
        )

def menu_callback_handler(update: Update, context: CallbackContext) -> None:
    """Handle main menu callbacks."""
    query = update.callback_query
    query.answer()
    action = query.data.split(":")[1]
    if action == "scan":
        query.edit_message_text(
            f"{Emoji.SEARCH} *Token Scanner*\n\n"
            f"Please enter a token address to scan:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif action == "deep_scan":
        query.edit_message_text(
            f"{Emoji.SEARCH} *Deep Scan*\nPlease enter a token address to run a deep scan:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif action == "chart":
        query.edit_message_text(
            f"{Emoji.CHART} *Chart Generator*\n\n"
            f"Please enter a token address to generate charts:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif action == "preview":
        query.edit_message_text(
            f"{Emoji.TOKEN} *Token Preview*\n\n"
            f"Please enter a token address to generate a preview card:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif action == "advanced_analysis":
        new_message = update.effective_message.copy(chat_id=update.effective_chat.id)
        new_message.text = "/advanced_analysis"
        new_update = Update(update.update_id, message=new_message)
        from src.bot.commands.advanced_analysis_command import command_advanced_analysis
        command_advanced_analysis(new_update, context)
    else:
        query.edit_message_text(
            f"{Emoji.ERROR} Unknown action: {action}",
            parse_mode=ParseMode.MARKDOWN
        )

def help_command(update: Update, context: CallbackContext) -> None:
    """Handle the /help command."""
    try:
        help_text = Templates.HELP
        keyboard = [
            [
                InlineKeyboardButton("Quick Scan", callback_data="menu:scan"),
                InlineKeyboardButton("Deep Scan", callback_data="menu:deep_scan")
            ],
            [
                InlineKeyboardButton("Generate Chart", callback_data="menu:chart"),
                InlineKeyboardButton("Token Preview", callback_data="menu:preview")
            ]
        ]
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}", exc_info=True)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="An error occurred while processing your request. Please try again later."
        )

def format_scan_result(result: dict) -> str:
    """Formats the analysis result using the BlazeAI layout requested by the user."""
    if not result.get("success"):
        return "❌ Token scan failed. Please check the address and try again."

    m = result.get("metrics", {})
    addr = result.get("contract_address", "N/A")

    # Resolve basic fields - escape special Markdown characters
    token_name = escape_markdown(m.get("name", "Unknown"))
    token_sym = escape_markdown(m.get("symbol", "???"))
    short_addr = f"{addr[:4]}...{addr[-3:]}" if len(addr) > 10 else addr

    # Determine risk level based on risk factors
    risk_level = "🟢 GREEN – LOW RISK"
    if result.get("risk_factors"):
        num_factors = len(result.get("risk_factors", {}))
        if num_factors >= 3:
            risk_level = "🔴 RED – HIGH RISK"
        elif num_factors >= 1:
            risk_level = "🟡 YELLOW – MEDIUM RISK"

    lines: list[str] = []
    lines.append("🧠 *BlazeAI Scan Result*\n")

    lines.extend([
        f"Blockchain:     Solana",
        f"Token Name:  {token_name}",
        f"Ticker:              ${token_sym}",
        f"Contract Address: {short_addr}\n",
    ])

    # Add link placeholders
    lines.append(f"🔗 [Solscan](https://solscan.io/token/{addr}) | [DexScreener](https://dexscreener.com/solana/{addr}) | [Birdeye](https://birdeye.so/token/{addr})\n")

    lines.append(f"🛡 Risk Rating: {risk_level}\n")

    # Token & Contract Overview section (values may be None)
    lines.append("🧩 *Token & Contract Overview*\n")
    created = escape_markdown(str(m.get("created_at", "N/A")))
    
    # Format supply with commas for readability
    total_supply = m.get("supply")
    if isinstance(total_supply, (int, float)):
        total_supply = f"{total_supply:,.6f}".rstrip('0').rstrip('.') if total_supply else "0"
    else:
        total_supply = "N/A"
    total_supply = escape_markdown(str(total_supply))
    
    circ_supply = m.get("circulating")
    if isinstance(circ_supply, (int, float)):
        circ_supply = f"{circ_supply:,.6f}".rstrip('0').rstrip('.') if circ_supply else "0"
    else:
        circ_supply = "N/A"
    circ_supply = escape_markdown(str(circ_supply))
    
    # Format price and market cap
    price = m.get("price_usd")
    if isinstance(price, (int, float)):
        price_str = f"${price:.6f}".rstrip('0').rstrip('.') if price < 0.01 else f"${price:.4f}"
    else:
        price_str = "N/A"
    price_str = escape_markdown(price_str)
    
    mcap = m.get("market_cap")
    if isinstance(mcap, (int, float)) and mcap > 0:
        if mcap >= 1_000_000:
            mcap_str = f"${mcap/1_000_000:.2f}M"
        else:
            mcap_str = f"${mcap:,.2f}"
    else:
        mcap_str = "N/A"
    mcap_str = escape_markdown(mcap_str)
    
    lines.extend([
        f"  *📅 Created:* {created}",
        f"  *💰 Supply:* {total_supply}",
        f"  *💵 Price:* {price_str}",
        f"  *📊 Market Cap:* {mcap_str}\n",
    ])
    
    # Liquidity section
    lines.append("💧 *Liquidity Analysis*\n")
    
    # Format liquidity data
    liquidity = m.get("liquidity_usd")
    if isinstance(liquidity, (int, float)):
        if liquidity >= 1_000_000:
            liq_str = f"${liquidity/1_000_000:.2f}M"
        else:
            liq_str = f"${liquidity:,.2f}"
    else:
        liq_str = "N/A"
    liq_str = escape_markdown(liq_str)
    
    # Get price impact data
    impact_1k = m.get("price_impact_1000_usd")
    impact_10k = m.get("price_impact_10000_usd")
    
    impact_1k_str = f"{impact_1k:.1f}%" if isinstance(impact_1k, (int, float)) else "N/A"
    impact_10k_str = f"{impact_10k:.1f}%" if isinstance(impact_10k, (int, float)) else "N/A"
    
    # Get main DEX info
    main_dex = m.get("main_dex", "Unknown")
    pools_count = m.get("pools_count", 0)
    
    lines.extend([
        f"  *💧 Total Liquidity:* {liq_str}",
        f"  *🏦 Main DEX:* {main_dex}",
        f"  *🔄 DEX Pools:* {pools_count}",
        f"  *📉 Price Impact $1K:* {impact_1k_str}",
        f"  *📉 Price Impact $10K:* {impact_10k_str}\n",
    ])
    
    # Tax section
    lines.append("💸 *Tax Analysis*\n")
    
    # Format tax percentages
    buy_tax = m.get("buy_tax")
    sell_tax = m.get("sell_tax")
    transfer_tax = m.get("transfer_tax")
    
    buy_tax_str = f"{buy_tax:.2f}%" if isinstance(buy_tax, (int, float)) and buy_tax > 0 else "0%"
    sell_tax_str = f"{sell_tax:.2f}%" if isinstance(sell_tax, (int, float)) and sell_tax > 0 else "0%"
    transfer_tax_str = f"{transfer_tax:.2f}%" if isinstance(transfer_tax, (int, float)) and transfer_tax > 0 else "0%"
    
    lines.extend([
        f"  *🛒 Buy Tax:* {buy_tax_str}",
        f"  *💰 Sell Tax:* {sell_tax_str}",
        f"  *🔄 Transfer Tax:* {transfer_tax_str}\n",
    ])
    
    # Holders section
    lines.append("👥 *Holder Analysis*\n")
    
    # Format holder percentages
    top_holder = m.get("top_holder_pct")
    if isinstance(top_holder, (int, float)):
        top_holder = f"{top_holder:.1f}%"
    else:
        top_holder = "N/A%"
        
    top5_pct = m.get("top5_pct")
    if isinstance(top5_pct, (int, float)):
        top5_pct = f"{top5_pct:.1f}%"
    else:
        top5_pct = "N/A%"
    
    lines.extend([
        f"  *👤 Top Holder:* {top_holder}",
        f"  *⚠️ Top 5 Holders Control:* {top5_pct} of total supply",
    ])
    
    # Add ownership info if available
    if "ownership_renounced" in m:
        renounced = "✅ Ownership renounced" if m.get("ownership_renounced") else "❌ No renounced ownership detected"
        lines.append(f"  *🚩 {renounced}*\n")
    else:
        lines.append(f"  *🚩 No renounced ownership detected*\n")

    # Risk factors section
    if result.get("risk_factors"):
        lines.append("⚠️ *Risk Factors Detected:*\n")
        for factor, desc in result.get("risk_factors", {}).items():
            lines.append(f"  • {factor}: {desc}")
        lines.append("")

    lines.append("🧠 *Blaze's Final Verdict:*\n")
    
    # Generate a verdict based on risk level
    if "🔴" in risk_level:
        verdict = "This token shows multiple high risk factors. Exercise extreme caution."
    elif "🟡" in risk_level:
        verdict = "This token shows some risk factors. Proceed with caution and do your own research."
    else:
        verdict = "This token appears to have low risk based on our analysis. Always DYOR."
        
    verdict = escape_markdown(verdict)
    lines.append(f"{verdict}\n")

    lines.append("Not Financial Advice. Always DYOR.")

    # Build message and strip markdown special chars to avoid Telegram parse errors.
    raw_message = "\n".join(lines)
    return raw_message

def escape_markdown(text):
    """Helper function to escape Markdown special characters for Telegram messages.
    
    Properly escapes all special characters that would cause Telegram's Markdown parser to fail.
    
    Args:
        text: Text to escape
        
    Returns:
        str: Text with all Markdown special characters escaped
    """
    if not text:
        return ""
    
    # Characters that need escaping in Telegram Markdown V2
    markdown_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Escape each character
    for char in markdown_chars:
        text = text.replace(char, f"\\{char}")
    
    return text

data_pipeline = DataPipeline()

def scan_command(update: Update, context: CallbackContext) -> None:
    """Handle the /scan command for advanced token scanning (real data, full analysis)."""
    print("[scan_command] scan_command called")
    print("[DEBUG] scan_command is about to call DataPipeline")
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        user_id = str(user.id)
        if user_id not in USER_CONTEXTS:
            USER_CONTEXTS[user_id] = {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "last_active": datetime.now(),
                "session_data": {}
            }
        else:
            USER_CONTEXTS[user_id]["last_active"] = datetime.now()
        if not context.args or not context.args[0]:
            context.bot.send_message(
                chat_id=chat_id,
                text=Templates.INVALID_ADDRESS
            )
            return
        token_address = context.args[0].strip()
        if not validate_solana_address(token_address):
            context.bot.send_message(
                chat_id=chat_id,
                text=Templates.INVALID_ADDRESS
            )
            return
        context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        processing_message = context.bot.send_message(
            chat_id=chat_id,
            text=Templates.SCAN_IN_PROGRESS
        )
        
        # Use DataPipeline for all data fetching
        metadata = data_pipeline.get_token_metadata(token_address)
        holders_data = data_pipeline.get_token_holders(token_address)
        supply_data = data_pipeline.get_token_supply(token_address)
        price_data = data_pipeline.get_current_price(token_address)
        fee_info = data_pipeline.get_fee_info(token_address)
        liquidity_info = data_pipeline.get_liquidity_info(token_address)
        
        # --- 1. Create metrics dict ---
        metrics = {}
        
        # Basic token info
        metrics['name'] = metadata.get('name', 'Unknown Token')
        metrics['symbol'] = metadata.get('symbol', 'UNKN')
        metrics['decimals'] = metadata.get('decimals', supply_data.get('decimals', 9))
        metrics['created_at'] = metadata.get('createdAt', 'N/A')
        
        # Supply data
        if supply_data:
            metrics['supply'] = supply_data.get('ui_amount', 0)
            metrics['decimals'] = supply_data.get('decimals', 9)
        
        # Price data
        if price_data:
            metrics['price_usd'] = price_data.get('price', 0)
            metrics['market_cap'] = price_data.get('price', 0) * metrics.get('supply', 0)
        
        # Liquidity data
        if liquidity_info:
            metrics['liquidity_usd'] = liquidity_info.get('total_liquidity_usd', 0)
            metrics['pools_count'] = liquidity_info.get('pools_count', 0)
            
            # Add price impact metrics
            price_impacts = liquidity_info.get('price_impacts', {})
            for amount, impact in price_impacts.items():
                metrics[f'price_impact_{amount}'] = impact
                
            # Add main pool info if available
            main_pool = liquidity_info.get('main_pool', {})
            if main_pool:
                metrics['main_dex'] = main_pool.get('dex', 'Unknown')
        
        # Process holders data from the new structure
        if holders_data:
            if isinstance(holders_data, dict):
                metrics['holders_count'] = holders_data.get('total', 'N/A')
                metrics['top_holder_pct'] = holders_data.get('top_holder_pct', 'N/A')
                metrics['top5_pct'] = holders_data.get('top5_pct', 'N/A')
                
                # Get individual holders if available
                holders_list = holders_data.get('holders', [])
                if holders_list and len(holders_list) > 0:
                    metrics['top_holder_address'] = holders_list[0].get('address', 'N/A')
            
        # Wallet clustering metric
        cluster_info = data_pipeline.get_wallet_clustering(token_address)
        if cluster_info and 'cluster_count' in cluster_info:
            metrics['cluster_count'] = cluster_info['cluster_count']
            
        # --- 3. Assemble risk factors ---
        risk_factors = {}
        if fee_info and fee_info.get('fee_detected'):
            fee_percent = fee_info.get('fee_percent', 0)
            tax_type = fee_info.get('tax_type', 'Unknown')
            risk_factors['Transfer Fee'] = f"{fee_percent:.2f}% ({tax_type})"
            
            # Add tax info to metrics
            metrics['buy_tax'] = fee_percent if "Buy" in tax_type else 0
            metrics['sell_tax'] = fee_percent if "Sell" in tax_type else 0
            metrics['transfer_tax'] = fee_percent if "Transfer" in tax_type else 0
        
        # Check holder concentration from the new metrics
        top_holder_pct = metrics.get('top_holder_pct')
        if isinstance(top_holder_pct, (int, float)) and top_holder_pct > 20:
            risk_factors['Holder Concentration'] = f"Top holder owns {top_holder_pct:.2f}%"
            
        # Check liquidity-related risk factors
        liquidity_usd = metrics.get('liquidity_usd', 0)
        if liquidity_usd < 10000:
            risk_factors['Low Liquidity'] = f"Only ${liquidity_usd:,.2f} in liquidity"
            
        # Check price impact as risk factor
        price_impact_10k = metrics.get('price_impact_10000_usd', 0)
        if price_impact_10k > 10:
            risk_factors['High Price Impact'] = f"{price_impact_10k:.1f}% impact on $10k swap"

        # --- 4. Assemble the final result for formatting ---
        final_result = {
            "success": True,
            "contract_address": token_address,
            "metrics": metrics,
            "risk_factors": risk_factors,
            "summary": "Analysis complete."
        }
        
        # --- 5. Format and send the message ---
        message = format_scan_result(final_result)
        
        # Delete processing message and send result
        context.bot.delete_message(
            chat_id=chat_id,
            message_id=processing_message.message_id
        )
        
        context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error in scan_command: {e}", exc_info=True)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"An error occurred: {str(e)}"
        )

def advanced_scan_command(update: Update, context: CallbackContext) -> int:
    """Handle the /advancedscan command for interactive scanning."""
    try:
        update.message.reply_text(
            f"{Emoji.SEARCH} *Advanced Token Scanner*\n\n"
            f"This interactive scanner allows you to perform detailed analysis "
            f"on Solana tokens with customizable options.\n\n"
            f"Please select the type of scan you want to perform:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardTemplates.create_menu_keyboard(
                options=[
                    ("Security Scan", "scan_type:security"),
                    ("Liquidity Analysis", "scan_type:liquidity"),
                    ("Ownership Analysis", "scan_type:ownership"),
                    ("Trading Patterns", "scan_type:trading")
                ],
                cancel_button=("Cancel", "scan:cancel")
            )
        )
        return CHOOSING_SCAN_TYPE
    except Exception as e:
        logger.error(f"Error in advanced scan command: {e}", exc_info=True)
        update.message.reply_text("An error occurred. Please try again later.")
        return ConversationHandler.END

def scan_type_callback(update: Update, context: CallbackContext) -> int:
    """Handle scan type selection callback."""
    query = update.callback_query
    query.answer()
    
    # Extract scan type from callback data
    scan_type = query.data.split(":")[1]
    
    # Store the selected scan type
    context.user_data["scan_type"] = scan_type
    
    # Ask for contract address
    query.edit_message_text(
        f"{Emoji.SEARCH} *{scan_type.capitalize()} Scan*\n\n"
        f"Please enter the contract address you want to analyze:",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ENTERING_ADDRESS

def address_input(update: Update, context: CallbackContext) -> int:
    """Handle address input for advanced scan."""
    address = update.message.text.strip()
    
    # Validate Solana address format
    if not validate_solana_address(address):
        update.message.reply_text(
            text=Templates.INVALID_ADDRESS,
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTERING_ADDRESS
    
    # Store the address
    context.user_data["address"] = address
    scan_type = context.user_data.get("scan_type", "security")
    
    # Show confirmation with scan details
    update.message.reply_text(
        f"{Emoji.CHART} *Scan Confirmation*\n\n"
        f"You're about to perform a *{scan_type.capitalize()} Scan* on:\n"
        f"`{address}`\n\n"
        f"Do you want to proceed?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardTemplates.create_menu_keyboard(
            options=[
                ("Proceed", "confirm:yes"),
                ("Change Address", "confirm:change_address"),
                ("Change Scan Type", "confirm:change_type")
            ],
            cancel_button=("Cancel", "scan:cancel")
        )
    )
    
    return CONFIRMING_SCAN

def confirm_scan_callback(update: Update, context: CallbackContext) -> int:
    """Handle scan confirmation callback."""
    query = update.callback_query
    query.answer()
    
    action = query.data.split(":")[1]
    
    if action == "change_address":
        query.edit_message_text(
            f"{Emoji.SEARCH} *Enter New Address*\n\n"
            f"Please enter the contract address you want to analyze:",
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTERING_ADDRESS
    
    elif action == "change_type":
        query.edit_message_text(
            f"{Emoji.SEARCH} *Select Scan Type*\n\n"
            f"Please select the type of scan you want to perform:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardTemplates.create_menu_keyboard(
                options=[
                    ("Security Scan", "scan_type:security"),
                    ("Liquidity Analysis", "scan_type:liquidity"),
                    ("Ownership Analysis", "scan_type:ownership"),
                    ("Trading Patterns", "scan_type:trading")
                ],
                cancel_button=("Cancel", "scan:cancel")
            )
        )
        return CHOOSING_SCAN_TYPE
    
    elif action == "yes":
        # Get scan details
        address = context.user_data.get("address")
        scan_type = context.user_data.get("scan_type", "security")
        # Update message to show scan in progress
        query.edit_message_text(
            f"{Emoji.SEARCH} *{scan_type.capitalize()} Scan in Progress*\n\n"
            f"Contract: `{address}`\n\n"
            f"Please wait, this may take a few moments...",
            parse_mode=ParseMode.MARKDOWN
        )
        # Perform the actual scan
        perform_advanced_scan(query, address, scan_type)
        return ConversationHandler.END
    
    else:
        query.edit_message_text(
            "Scan cancelled. You can start a new scan with /advancedscan."
        )
        return ConversationHandler.END

def perform_advanced_scan(query, address: str, scan_type: str) -> None:
    """Perform the advanced scan and send results."""
    import time
    try:
        time.sleep(3)
        if scan_type == "security":
            scan_result = advanced_scanner.security_scan(address)
        elif scan_type == "liquidity":
            scan_result = advanced_scanner.liquidity_scan(address)
        elif scan_type == "ownership":
            scan_result = advanced_scanner.ownership_scan(address)
        elif scan_type == "trading":
            scan_result = advanced_scanner.trading_pattern_scan(address)
        else:
            scan_result = {"success": False, "error": "Invalid scan type"}
        if not scan_result or not scan_result.get("success"):
            error_message = scan_result.get("error", "Unknown error") if scan_result else "Failed to scan token"
            query.edit_message_text(
                Templates.SCAN_FAILED.format(error_message=error_message),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        result_text = scan_result.get("result", "No result available.")
        if len(result_text) <= 4096:
            query.edit_message_text(
                result_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=KeyboardTemplates.create_token_actions_keyboard(address)
            )
        else:
            query.edit_message_text(
                f"{Emoji.SEARCH} *{scan_type.capitalize()} Scan Complete*\n\n"
                f"Results are being sent in multiple messages due to size...",
                parse_mode=ParseMode.MARKDOWN
            )
            parts = split_message(result_text)
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    query.message.reply_text(
                        part,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=KeyboardTemplates.create_token_actions_keyboard(address)
                    )
                else:
                    query.message.reply_text(
                        part,
                        parse_mode=ParseMode.MARKDOWN
                    )
    except Exception as e:
        logger.error(f"Error in perform_advanced_scan: {e}")
        query.edit_message_text(
            f"{Emoji.ERROR} *Scan Error*\n\n"
            f"An unexpected error occurred: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

def cancel_command(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    update.message.reply_text(
        f"{Emoji.INFO} Operation cancelled. You can start a new request anytime."
    )
    return ConversationHandler.END

def handle_text_message(update: Update, context: CallbackContext) -> None:
    """Handle regular text messages with suggestion system."""
    user_message = update.message.text
    
    # Check for Solana address format and automatically trigger scan
    if validate_solana_address(user_message):
        context.args = [user_message]
        scan_command(update, context)
        return
    
    # Check for command suggestions
    suggestion = suggestion_system.suggest_command(user_message)
    if suggestion:
        command, description = suggestion
        related = suggestion_system.get_related_commands(command[1:])  # Remove slash
        
        # Format suggestion message
        message = suggestion_system.format_suggestion_message(suggestion, related)
        
        # Create keyboard with suggested command button
        keyboard = [[InlineKeyboardButton(f"Use {command}", callback_data=f"use_command:{command}")]]
        
        update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Generic response when no specific suggestion
        update.message.reply_text(
            f"{Emoji.INFO} I'm not sure what you're asking. Try using a command like /help to see what I can do.",
            parse_mode=ParseMode.MARKDOWN
        )

def command_suggestion_callback(update: Update, context: CallbackContext) -> None:
    """Handle command suggestion callbacks."""
    query = update.callback_query
    query.answer()
    suggested_command = query.data.split(":")[1]
    query.edit_message_text(
        f"Executing {suggested_command}...",
        parse_mode=ParseMode.MARKDOWN
    )
    command_parts = suggested_command[1:].split()
    command = command_parts[0]
    if command == "scan" and len(command_parts) > 1:
        context.args = [command_parts[1]]
        scan_command(update, context)
    elif command == "chart" and len(command_parts) > 1:
        context.args = [command_parts[1]]
        chart_command(update, context)
    elif command == "help":
        help_command(update, context)
    elif command == "start":
        start_command(update, context)
    elif command == "enhanced_scan":
        new_message = update.effective_message.copy(chat_id=update.effective_chat.id)
        new_message.text = "/enhanced_scan"
        new_update = Update(update.update_id, message=new_message)
        from src.bot.commands.enhanced_scan import command_enhanced_scan
        command_enhanced_scan(new_update, context)
    elif command == "advancedscan":
        new_message = update.effective_message.copy(chat_id=update.effective_chat.id)
        new_message.text = "/advancedscan"
        new_update = Update(update.update_id, message=new_message)
        advanced_scan_command(new_update, context)
    else:
        query.message.reply_text(
            f"Command {suggested_command} not implemented yet.",
            parse_mode=ParseMode.MARKDOWN
        )

def error_handler(update: Update, context: CallbackContext) -> None:
    """Handle errors in the dispatcher."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    
    try:
        if update and update.effective_message:
            update.effective_message.reply_text(
                f"{Emoji.ERROR} An error occurred while processing your request. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

def cleanup_expired_contexts():
    """Periodically clean up expired user contexts to prevent memory leaks."""
    def cleanup():
        while True:
            try:
                now = datetime.now()
                expired_users = []
                for user_id, context in list(USER_CONTEXTS.items()):
                    if (now - context["last_active"]).total_seconds() > 3600:
                        expired_users.append(user_id)
                for user_id in expired_users:
                    del USER_CONTEXTS[user_id]
                if expired_users:
                    logger.info(f"Cleaned up {len(expired_users)} expired user contexts")
                time.sleep(900)
            except Exception as e:
                logger.error(f"Error in context cleanup: {e}")
                time.sleep(60)
    
    thread = threading.Thread(target=cleanup, daemon=True)
    thread.start()

# Helper function for formatting different scan result types

def format_security_scan_result(scan_result: Dict[str, Any]) -> str:
    """Format security scan results."""
    # Implement detailed formatting here
    # For now, returning a placeholder
    return f"{Emoji.SHIELD} *Security Scan Results*\n\nImplement detailed formatting here"

def format_liquidity_scan_result(scan_result: Dict[str, Any]) -> str:
    """Format liquidity scan results."""
    # Implement detailed formatting here
    # For now, returning a placeholder
    return f"{Emoji.LIQUIDITY} *Liquidity Analysis Results*\n\nImplement detailed formatting here"

def format_ownership_scan_result(scan_result: Dict[str, Any]) -> str:
    """Format ownership scan results."""
    # Implement detailed formatting here
    # For now, returning a placeholder
    return f"{Emoji.OWNERSHIP} *Ownership Analysis Results*\n\nImplement detailed formatting here"

def format_trading_scan_result(scan_result: Dict[str, Any]) -> str:
    """Format trading pattern scan results."""
    # Implement detailed formatting here
    # For now, returning a placeholder
    return f"{Emoji.TRADING} *Trading Pattern Analysis Results*\n\nImplement detailed formatting here"

def about_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("About: Blaze Analyst Telegram Bot. Provides Solana token and contract analysis, DeFi insights, and more.")

def contact_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Contact: support@blazeanalyst.com or use /help for more info.")

def deep_scan_command(update: Update, context: CallbackContext) -> None:
    """Handle /scandeep <token_address> – run full deep scan."""
    try:
        chat_id = update.effective_chat.id
        args = context.args
        if not args:
            context.bot.send_message(chat_id=chat_id, text="Usage: /scandeep <token_address>")
            return

        token_address = args[0].strip()
        if not validate_solana_address(token_address):
            context.bot.send_message(chat_id=chat_id, text="Invalid Solana token address.")
            return

        # Inform user
        msg = context.bot.send_message(chat_id=chat_id, text="🔍 Performing deep scan… this may take up to 20 seconds…")

        # Run orchestrator (synchronous – may take several seconds)
        result = deep_scan_orchestrator.run_deep_scan(token_address, depth="deep")

        # Format and send output
        formatted = format_deep_scan_result(result)
        context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=formatted, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error in deep scan command: {e}", exc_info=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Error performing deep scan. Please try again later.")

def stop_command(update: Update, context: CallbackContext) -> None:
    """Gracefully stop the bot process (owner only)."""
    user_id = str(update.effective_user.id)
    if BOT_OWNER_ID and user_id != BOT_OWNER_ID:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Unauthorized.")
        return

    context.bot.send_message(chat_id=update.effective_chat.id, text="Shutting down…")
    # Give Telegram a moment to send the message, then exit
    def _shutdown():
        time.sleep(1)
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()

def init_bot():
    """Initialize the Telegram bot."""
    try:
        print("[DEBUG] Entered init_bot()")
        logger.info("Initializing Telegram bot...")
        # Get bot token from config
        bot_token = config.get('telegram', {}).get('bot_token', os.getenv('TELEGRAM_BOT_TOKEN'))
        print(f"[DEBUG] Bot token: {bot_token}")
        if not bot_token:
            raise ValueError("Bot token is not set. Please check your .env file.")
        # --- Networking tuning -------------------------------------------------
        connect_timeout = float(os.getenv("TELEGRAM_CONNECT_TIMEOUT", 5))
        read_timeout = float(os.getenv("TELEGRAM_READ_TIMEOUT", 8))

        request_kwargs = {
            "con_pool_size": 8,
            "connect_timeout": connect_timeout,
            "read_timeout": read_timeout,
        }

        updater = Updater(bot_token, request_kwargs=request_kwargs)
        print("[DEBUG] Updater created.")
        # Register all handlers
        register_handlers(updater)
        print("[DEBUG] Handlers registered.")
        # Silence noisy deep library loggers
        logging.getLogger("telegram.ext.updater").setLevel(logging.WARNING)
        logging.getLogger("telegram.vendor.ptb_urllib3").setLevel(logging.WARNING)

        logger.info("Bot initialization complete")
        return updater
    except Exception as e:
        print(f"[DEBUG] Exception in init_bot: {e}")
        logger.error(f"Error initializing bot: {e}", exc_info=True)
        raise

def run_bot():
    print("[DEBUG] Entered run_bot()")
    try:
        print("[run_bot] Entered run_bot()")
        updater = init_bot()
        print("[run_bot] Updater initialized.")
        # Start polling
        logger.info("Starting bot polling...")
        updater.start_polling(allowed_updates=Update.ALL_TYPES)
        print("[run_bot] Started polling.")
        logger.info("Bot started. Press Ctrl+C to stop.")

        # ---------------- Health watchdog ----------------
        def _watchdog():
            consecutive_failures = 0
            while True:
                try:
                    updater.bot.get_me(timeout=5)
                    consecutive_failures = 0
                except Exception:
                    consecutive_failures += 1
                    logger.warning("Watchdog: telegram API unreachable (attempt %s)", consecutive_failures)
                    if consecutive_failures >= 3:
                        logger.error("Watchdog: restarting bot after repeated failures")
                        os._exit(1)
                time.sleep(30)

        threading.Thread(target=_watchdog, daemon=True).start()
    except Exception as e:
        print(f"[DEBUG] Exception in run_bot: {e}")
        logger.error(f"Error running bot: {e}", exc_info=True)
        raise

def register_handlers(updater: Updater) -> None:
    """Register all command and message handlers."""
    # Command handlers
    updater.dispatcher.add_handler(CommandHandler("start", start_command))
    updater.dispatcher.add_handler(CommandHandler("scan", scan_command))
    updater.dispatcher.add_handler(CommandHandler("about", about_command))
    updater.dispatcher.add_handler(CommandHandler("contact", contact_command))
    updater.dispatcher.add_handler(CommandHandler("scandeep", deep_scan_command))
    
    # Menu callback handler
    updater.dispatcher.add_handler(CallbackQueryHandler(menu_callback_handler, pattern="^menu:"))
    
    # Chart handlers
    updater.dispatcher.add_handler(CommandHandler("chart", chart_handler))
    updater.dispatcher.add_handler(CallbackQueryHandler(chart_callback_handler, pattern="^chart:"))
    
    # Preview handlers
    updater.dispatcher.add_handler(get_preview_handler())
    updater.dispatcher.add_handler(CallbackQueryHandler(preview_callback, pattern="^preview:"))
    
    # Enhanced scan handler
    updater.dispatcher.add_handler(enhanced_scan_handler)
    
    # Help handler
    updater.dispatcher.add_handler(get_help_handler())
    
    # Advanced analysis handler
    updater.dispatcher.add_handler(get_advanced_analysis_handler())
    
    # Account visualization handler
    updater.dispatcher.add_handler(get_account_visualization_handler())
    
    # DeFi analysis handler
    updater.dispatcher.add_handler(get_defi_analysis_handler())
    
    # Suggestion system handlers
    updater.dispatcher.add_handler(get_suggestion_handler())
    updater.dispatcher.add_handler(CallbackQueryHandler(command_suggestion_callback, pattern="^suggest:"))
    
    # Default message handler
    updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text_message))
    
    # Error handler
    updater.dispatcher.add_error_handler(error_handler)
    
    # Start context cleanup task
    cleanup_expired_contexts()

    # Add stop command handler
    updater.dispatcher.add_handler(CommandHandler("stop", stop_command))

if __name__ == "__main__":
    try:
        run_bot()  # or your main bot startup function
    except Exception as e:
        logging.exception("Fatal error in main loop")
        sys.exit(1) 