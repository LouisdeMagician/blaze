"""
Enhanced scan command handlers for the Telegram bot.
"""
import logging
import re
from typing import Dict, List, Optional, Union

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

from src.services.advanced_scanner import advanced_scanner
from src.models.scan_result import ScanStatus
from src.models.contract import RiskLevel
from src.services.user_service import user_service
from src.bot.message_templates import Templates, Emoji
from src.bot.keyboard_templates import KeyboardTemplates
from src.utils.message_formatter import split_message

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_ADDRESS = 1
WAITING_FOR_SCAN_DEPTH = 2
SCANNING = 3

# Callback data patterns
SCAN_DEPTH_PATTERN = r"scan_depth:(\w+)"

async def command_enhanced_scan(update: Update, context: CallbackContext) -> int:
    """Start the enhanced scan process."""
    user = await user_service.get_user_from_update(update)
    
    if not user:
        await update.message.reply_text(
            "⚠️ You need to /start the bot before using this command."
        )
        return ConversationHandler.END
    
    # Check if user has premium subscription for deep/comprehensive scans
    is_premium = user_service.is_premium_user(user)
    
    await update.message.reply_text(
        f"{Emoji.SHIELD} *Enhanced Contract Scanner*\n\n"
        f"This feature performs in-depth analysis of a Solana contract, "
        f"checking for suspicious patterns, liquidity issues, and more.\n\n"
        f"Please enter the contract address you want to scan:",
        parse_mode="Markdown"
    )
    
    # Store user premium status for later
    context.user_data["is_premium"] = is_premium
    
    return WAITING_FOR_ADDRESS

async def handle_address_input(update: Update, context: CallbackContext) -> int:
    """Handle the address input and request scan depth."""
    address = update.message.text.strip()
    
    # Validate Solana address format (simple check)
    if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
        await update.message.reply_text(
            Templates.INVALID_ADDRESS,
            parse_mode="Markdown"
        )
        return WAITING_FOR_ADDRESS
    
    # Store the address for later
    context.user_data["address_to_scan"] = address
    
    # Get premium status
    is_premium = context.user_data.get("is_premium", False)
    
    # Format message using template
    message_text = Templates.format_scan_depth_selection(address, is_premium)
    
    # Create keyboard for scan depth options
    keyboard = KeyboardTemplates.create_scan_depth_keyboard(is_premium)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    return WAITING_FOR_SCAN_DEPTH

async def handle_scan_depth_selection(update: Update, context: CallbackContext) -> int:
    """Handle the scan depth selection and start the scan."""
    query = update.callback_query
    await query.answer()
    
    # Check for cancel action
    if query.data == "scan:cancel":
        await query.edit_message_text(
            f"{Emoji.INFO} Scan cancelled. You can start a new scan anytime.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # Extract scan depth from callback data
    match = re.match(SCAN_DEPTH_PATTERN, query.data)
    if not match:
        await query.edit_message_text("⚠️ Invalid selection. Please try again.")
        return ConversationHandler.END
    
    scan_depth = match.group(1)
    address = context.user_data.get("address_to_scan")
    
    if not address:
        await query.edit_message_text("⚠️ No address found. Please try again.")
        return ConversationHandler.END
    
    # Check premium status for deep/comprehensive scans
    is_premium = context.user_data.get("is_premium", False)
    if not is_premium and scan_depth in ["deep", "comprehensive"]:
        await query.edit_message_text(
            Templates.PREMIUM_REQUIRED,
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    # Update message to show scan in progress
    await query.edit_message_text(
        Templates.format_scan_in_progress(address, scan_depth),
        parse_mode="Markdown"
    )
    
    # Get user ID for scan attribution
    user = await user_service.get_user_from_update(update)
    user_id = user.telegram_id if user else None
    
    # Start scan in background so we don't block the bot
    context.application.create_task(
        perform_scan(query, address, scan_depth, user_id)
    )
    
    return SCANNING

async def perform_scan(query, address: str, scan_depth: str, user_id: Optional[str]) -> None:
    """Perform the actual scan and send results."""
    try:
        # Perform the enhanced scan
        scan_result = advanced_scanner.enhanced_scan(
            address, 
            user_id=user_id, 
            scan_depth=scan_depth
        )
        
        if not scan_result:
            await query.edit_message_text(
                Templates.SCAN_FAILED.format(error_message="Invalid address format."),
                parse_mode="Markdown"
            )
            return
        
        if scan_result.status == ScanStatus.FAILED:
            await query.edit_message_text(
                Templates.SCAN_FAILED.format(error_message=scan_result.error_message or "Unknown error"),
                parse_mode="Markdown"
            )
            return
        
        # Format the results
        formatted_result = format_enhanced_scan_result(scan_result, scan_depth)
        
        # Create action keyboard for the results
        keyboard = KeyboardTemplates.create_token_actions_keyboard(address)
        
        # Send results - may need to split into multiple messages if too long
        if len(formatted_result) <= 4096:
            await query.edit_message_text(
                formatted_result,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            # Split into parts
            await query.edit_message_text(
                f"{Emoji.SEARCH} *Enhanced Scan Complete*\n\n"
                f"Results are being sent in multiple messages due to size...",
                parse_mode="Markdown"
            )
            
            # Send result in parts
            parts = split_message(formatted_result)
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Last part
                    await query.message.reply_text(
                        part,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                else:
                    await query.message.reply_text(
                        part,
                        parse_mode="Markdown"
                    )
    
    except Exception as e:
        logger.error(f"Error performing enhanced scan: {e}", exc_info=True)
        await query.edit_message_text(
            f"{Emoji.ERROR} *Scan Error*\n\n"
            f"An unexpected error occurred: {str(e)}",
            parse_mode="Markdown"
        )

def format_enhanced_scan_result(scan_result, scan_depth: str) -> str:
    """Format enhanced scan result for display."""
    # Get risk level emoji
    risk_level = scan_result.risk_level.value.lower() if hasattr(scan_result, 'risk_level') else "unknown"
    risk_emoji = Emoji.for_risk_level(risk_level)
    
    # Format the header
    header = f"{Emoji.SHIELD} *Enhanced Scan Results ({scan_depth.capitalize()})*\n\n"
    
    # Basic token info
    token_info = (
        f"*{scan_result.name}* ({scan_result.symbol})\n"
        f"Address: `{scan_result.address}`\n\n"
        f"*Risk Level: {risk_level.upper()}* {risk_emoji}\n\n"
    )
    
    # Add summary if available
    summary = ""
    if hasattr(scan_result, 'summary') and scan_result.summary:
        summary = f"*Summary:*\n{scan_result.summary}\n\n"
    
    # Risk factors section
    risk_factors = ""
    if hasattr(scan_result, 'risk_factors') and scan_result.risk_factors:
        risk_factors = f"*Risk Factors:*\n"
        for factor in scan_result.risk_factors:
            factor_name = factor.name.replace('_', ' ').title()
            factor_score = factor.score if hasattr(factor, 'score') else 0
            factor_emoji = "🔴" if factor_score > 0.7 else "🟡" if factor_score > 0.4 else "🟢"
            risk_factors += f"{factor_emoji} {factor_name}: {factor.description}\n"
        risk_factors += "\n"
    
    # Security section
    security = ""
    if hasattr(scan_result, 'security_checks') and scan_result.security_checks:
        security = f"*Security Checks:*\n"
        for check in scan_result.security_checks:
            check_name = check.name.replace('_', ' ').title()
            check_emoji = "✅" if check.passed else "❌"
            security += f"{check_emoji} {check_name}\n"
        security += "\n"
    
    # Token details
    details = f"*Token Details:*\n"
    if hasattr(scan_result, 'total_supply'):
        details += f"• Supply: {scan_result.total_supply:,}\n"
    if hasattr(scan_result, 'decimals'):
        details += f"• Decimals: {scan_result.decimals}\n"
    if hasattr(scan_result, 'created_at'):
        details += f"• Created: {scan_result.created_at}\n"
    details += "\n"
    
    # Ownership info
    ownership = ""
    if hasattr(scan_result, 'ownership_info') and scan_result.ownership_info:
        ownership = f"*Ownership:*\n"
        if hasattr(scan_result.ownership_info, 'mint_authority'):
            ownership += f"• Mint Authority: {scan_result.ownership_info.mint_authority}\n"
        if hasattr(scan_result.ownership_info, 'freeze_authority'):
            ownership += f"• Freeze Authority: {scan_result.ownership_info.freeze_authority}\n"
        if hasattr(scan_result.ownership_info, 'upgrade_authority'):
            ownership += f"• Upgrade Authority: {scan_result.ownership_info.upgrade_authority}\n"
        ownership += "\n"
    
    # Recommendations
    recommendations = ""
    if hasattr(scan_result, 'recommendations') and scan_result.recommendations:
        recommendations = f"*Recommendations:*\n"
        for rec in scan_result.recommendations:
            recommendations += f"• {rec}\n"
        recommendations += "\n"
    
    # Combine all sections
    result = header + token_info + summary + risk_factors + security + details + ownership + recommendations
    
    # Add scan details
    result += (
        f"*Scan Details:*\n"
        f"• Scan Type: {scan_depth.capitalize()}\n"
        f"• Scan Time: {scan_result.scan_time if hasattr(scan_result, 'scan_time') else 'N/A'}\n"
    )
    
    return result

async def cancel_enhanced_scan(update: Update, context: CallbackContext) -> int:
    """Cancel the enhanced scan process."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(f"{Emoji.INFO} Scan cancelled. You can start a new scan anytime.")
    else:
        await update.message.reply_text(f"{Emoji.INFO} Scan cancelled. You can start a new scan anytime.")
    
    return ConversationHandler.END

# Create the conversation handler for enhanced scan
enhanced_scan_handler = ConversationHandler(
    entry_points=[CommandHandler("enhanced_scan", command_enhanced_scan)],
    states={
        WAITING_FOR_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, handle_address_input)],
        WAITING_FOR_SCAN_DEPTH: [CallbackQueryHandler(handle_scan_depth_selection, pattern=r"^scan_depth:|^scan:")],
        SCANNING: []  # No handlers needed here as we're doing background processing
    },
    fallbacks=[
        CommandHandler("cancel", cancel_enhanced_scan),
        CallbackQueryHandler(cancel_enhanced_scan, pattern=r"^scan:cancel$")
    ],
    name="enhanced_scan"
) 