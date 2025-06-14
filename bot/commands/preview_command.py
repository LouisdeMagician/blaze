"""
Token preview command for Telegram bot.
Generates visual token preview cards.
"""
import logging
import re
from typing import List, Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackContext, CommandHandler, CallbackQueryHandler

from src.bot.message_templates import Emoji
from src.bot.keyboard_templates import KeyboardTemplates
from src.bot.token_preview import token_preview_generator
from src.utils.validators import validate_solana_address

logger = logging.getLogger(__name__)

# Callback patterns
PREVIEW_CALLBACK_PATTERN = r"preview:(\w+):(.+)"
COMPARE_CALLBACK_PATTERN = r"compare:(\w+):(.+)"

async def preview_command(update: Update, context: CallbackContext) -> None:
    """Handle the /preview command for token preview cards."""
    try:
        # Check if command has address argument
        if not context.args or not context.args[0]:
            await update.message.reply_text(
                f"{Emoji.TOKEN} *Token Preview Generator*\n\n"
                f"Please provide a token address to generate a preview card.\n"
                f"Example: `/preview <token_address>`\n\n"
                f"You can also compare two tokens with:\n"
                f"`/preview compare <token1> <token2>`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check if it's a comparison request
        if context.args[0].lower() == "compare" and len(context.args) >= 3:
            token1_address = context.args[1].strip()
            token2_address = context.args[2].strip()
            
            # Validate addresses
            if not validate_solana_address(token1_address) or not validate_solana_address(token2_address):
                await update.message.reply_text(
                    f"{Emoji.ERROR} One or both addresses are invalid. Please provide valid Solana addresses.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Send typing indicator
            await update.message.chat.send_action("typing")
            
            # Generate comparison
            await update.message.reply_text(
                f"{Emoji.CHART} Generating token comparison...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Generate the comparison card
            comparison_buffer = await token_preview_generator.generate_token_comparison(
                token1_address, 
                token2_address
            )
            
            if comparison_buffer:
                # Send the comparison card
                await update.message.reply_photo(
                    photo=comparison_buffer,
                    caption=f"{Emoji.CHART} *Token Comparison*\n\n"
                            f"Compare key metrics between tokens",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"{Emoji.ERROR} Failed to generate comparison. Please try again later.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            return
        
        # Handle single token preview
        token_address = context.args[0].strip()
        
        # Validate the address format
        if not validate_solana_address(token_address):
            await update.message.reply_text(
                f"{Emoji.ERROR} Invalid Solana address. Please provide a valid address.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Send typing indicator
        await update.message.chat.send_action("typing")
        
        # Inform user preview is being generated
        await update.message.reply_text(
            f"{Emoji.TOKEN} Generating token preview...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Generate the preview card
        preview_buffer = await token_preview_generator.generate_token_preview(token_address)
        
        if preview_buffer:
            # Create action buttons
            keyboard = [
                [
                    InlineKeyboardButton("Scan Token", callback_data=f"preview:scan:{token_address}"),
                    InlineKeyboardButton("Show Chart", callback_data=f"preview:chart:{token_address}")
                ],
                [
                    InlineKeyboardButton("Add to Watchlist", callback_data=f"preview:watchlist:{token_address}"),
                    InlineKeyboardButton("Deep Analysis", callback_data=f"preview:analysis:{token_address}")
                ]
            ]
            
            # Send the preview card
            await update.message.reply_photo(
                photo=preview_buffer,
                caption=f"{Emoji.TOKEN} *Token Preview*\n\n"
                        f"Select an action below for more options",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                f"{Emoji.ERROR} Failed to generate preview. Please try again later.",
                parse_mode=ParseMode.MARKDOWN
            )
        
    except Exception as e:
        logger.error(f"Error in preview command: {e}", exc_info=True)
        await update.message.reply_text(
            f"{Emoji.ERROR} An error occurred while processing your request. Please try again later."
        )

async def preview_callback_handler(update: Update, context: CallbackContext) -> None:
    """Handle token preview action callbacks."""
    query = update.callback_query
    await query.answer()
    
    # Extract action and token address from callback data
    match = re.match(PREVIEW_CALLBACK_PATTERN, query.data)
    if not match:
        return
    
    action = match.group(1)
    token_address = match.group(2)
    
    if action == "scan":
        # Simulate scan command
        context.args = [token_address]
        # Create a new update for the scan command
        new_message = query.message.reply_to_message
        if not new_message:
            new_message = query.message
        new_update = Update(update.update_id, message=new_message)
        
        # Run scan command
        from src.bot.telegram_bot import scan_command
        await scan_command(new_update, context)
    
    elif action == "chart":
        # Simulate chart command
        context.args = [token_address]
        # Create a new update for the chart command
        new_message = query.message.reply_to_message
        if not new_message:
            new_message = query.message
        new_update = Update(update.update_id, message=new_message)
        
        # Run chart command
        from src.bot.commands.chart_command import chart_command
        await chart_command(new_update, context)
    
    elif action == "watchlist":
        # Send placeholder message until watchlist command is implemented
        await query.message.reply_text(
            f"{Emoji.STAR} Added to watchlist: {token_address}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif action == "analysis":
        # Simulate enhanced scan command
        # Create a new update for the enhanced scan command
        new_message = query.message.reply_to_message
        if not new_message:
            new_message = query.message
        new_message.text = f"/enhanced_scan {token_address}"
        new_update = Update(update.update_id, message=new_message)
        
        # Run enhanced scan command
        from src.bot.commands.enhanced_scan import command_enhanced_scan
        await command_enhanced_scan(new_update, context)
    
    else:
        await query.message.reply_text(
            f"{Emoji.ERROR} Unknown action: {action}",
            parse_mode=ParseMode.MARKDOWN
        )

def get_preview_handler():
    from telegram.ext import CommandHandler
    return CommandHandler("preview", preview_command)

# Register command handlers
preview_handler = CommandHandler("preview", preview_command)
preview_callback = CallbackQueryHandler(preview_callback_handler, pattern=PREVIEW_CALLBACK_PATTERN) 