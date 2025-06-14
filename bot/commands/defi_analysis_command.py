"""
DeFi Analysis Command.
Provides commands for analyzing Solana DeFi positions.
"""
import logging
from typing import Dict, List, Any, Optional, Union

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, CallbackContext, ConversationHandler,
    MessageHandler, CallbackQueryHandler, Filters
)
from telegram import ParseMode

from src.services.solana_program_analyzer_service import get_solana_program_analyzer_service
from src.utils.validators import validate_solana_address
from src.utils.message_formatter import format_message
from src.bot.emoji import Emoji

# Define conversation states
SELECTING_ANALYSIS_TYPE = 0
WAITING_FOR_ADDRESS = 1
WAITING_FOR_ADDITIONAL_INFO = 2

# Define callback data prefixes
ANALYSIS_TYPE_PREFIX = "defi_type:"
BACK_TO_MENU = "defi_back_to_menu"

logger = logging.getLogger(__name__)

def defi_analysis(update: Update, context: CallbackContext) -> int:
    """
    Handle the /defi command.
    Starts the DeFi analysis flow.
    """
    keyboard = [
        [
            InlineKeyboardButton(f"{Emoji.LIQUIDITY} Liquidity Pool", 
                               callback_data=f"{ANALYSIS_TYPE_PREFIX}pool"),
            InlineKeyboardButton(f"{Emoji.LENDING} Lending Position", 
                               callback_data=f"{ANALYSIS_TYPE_PREFIX}lending")
        ],
        [
            InlineKeyboardButton(f"{Emoji.STAKING} Staking Position", 
                               callback_data=f"{ANALYSIS_TYPE_PREFIX}staking"),
            InlineKeyboardButton(f"{Emoji.CALCULATOR} Impermanent Loss", 
                               callback_data=f"{ANALYSIS_TYPE_PREFIX}impermanent_loss")
        ],
        [
            InlineKeyboardButton(f"{Emoji.SEARCH} Identify Protocol", 
                               callback_data=f"{ANALYSIS_TYPE_PREFIX}identify")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"{Emoji.DEFI} *Solana DeFi Analysis*\n\n"
        f"Select the type of DeFi analysis you want to perform:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return SELECTING_ANALYSIS_TYPE

def analysis_type_selected(update: Update, context: CallbackContext) -> int:
    """
    Handle analysis type selection.
    """
    query = update.callback_query
    query.answer()
    
    # Extract analysis type from callback data
    analysis_type = query.data.split(":")[1]
    
    # Store the selected type for later use
    context.user_data["analysis_type"] = analysis_type
    
    # Determine next prompt based on type
    if analysis_type == "pool":
        message = f"{Emoji.LIQUIDITY} Please send me the Solana liquidity pool address to analyze"
    elif analysis_type == "lending":
        message = f"{Emoji.LENDING} Please send me the Solana lending position address to analyze"
    elif analysis_type == "staking":
        message = f"{Emoji.STAKING} Please send me the Solana staking position address to analyze"
    elif analysis_type == "identify":
        message = f"{Emoji.SEARCH} Please send me the Solana address to identify which DeFi protocol it belongs to"
    elif analysis_type == "impermanent_loss":
        message = f"{Emoji.CALCULATOR} Please send me the Solana liquidity pool address for impermanent loss calculation"
    else:
        message = "Invalid analysis type selected"
        query.edit_message_text(message)
        return ConversationHandler.END
    
    query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return WAITING_FOR_ADDRESS

def process_address(update: Update, context: CallbackContext) -> int:
    """
    Process the address input from the user.
    """
    address = update.message.text.strip()
    analysis_type = context.user_data.get("analysis_type")
    
    # Validate the address
    if not validate_solana_address(address):
        update.message.reply_text(
            f"{Emoji.ERROR} Invalid Solana address format. Please try again.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAITING_FOR_ADDRESS
    
    # Store the address for later use
    context.user_data["address"] = address
    
    # For impermanent loss, we need additional information
    if analysis_type == "impermanent_loss":
        update.message.reply_text(
            f"{Emoji.CALCULATOR} Now please send me the initial price and current price, "
            f"separated by a comma. For example: `1.5,2.3`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAITING_FOR_ADDITIONAL_INFO
    
    # For other types, proceed with analysis
    process_defi_analysis(update, context)
    
    return ConversationHandler.END

def process_additional_info(update: Update, context: CallbackContext) -> int:
    """
    Process additional information for impermanent loss calculation.
    """
    try:
        # Parse the input
        text = update.message.text.strip()
        parts = text.split(",")
        
        if len(parts) != 2:
            update.message.reply_text(
                f"{Emoji.ERROR} Please provide exactly two numbers separated by a comma.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return WAITING_FOR_ADDITIONAL_INFO
        
        initial_price = float(parts[0].strip())
        current_price = float(parts[1].strip())
        
        if initial_price <= 0 or current_price <= 0:
            update.message.reply_text(
                f"{Emoji.ERROR} Prices must be positive numbers.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return WAITING_FOR_ADDITIONAL_INFO
        
        # Store the prices
        context.user_data["initial_price"] = initial_price
        context.user_data["current_price"] = current_price
        
        # Proceed with impermanent loss calculation
        process_impermanent_loss(update, context)
        
        return ConversationHandler.END
        
    except ValueError:
        update.message.reply_text(
            f"{Emoji.ERROR} Invalid input. Please provide two numbers separated by a comma.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAITING_FOR_ADDITIONAL_INFO

def process_defi_analysis(update: Update, context: CallbackContext) -> None:
    """
    Process the DeFi analysis based on the selected type and address.
    """
    analysis_type = context.user_data.get("analysis_type")
    address = context.user_data.get("address")
    
    # Send processing message
    processing_message = update.message.reply_text(
        f"{Emoji.HOURGLASS} Analyzing... This may take a moment.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    try:
        # Get the analyzer service
        analyzer = get_solana_program_analyzer_service()
        
        if not analyzer:
            update.message.reply_text(
                f"{Emoji.ERROR} Sorry, the analyzer service is not available.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        # Perform the analysis based on type
        if analysis_type == "pool":
            result = analyzer.analyze_liquidity_pool(address)
            title = f"{Emoji.LIQUIDITY} Liquidity Pool Analysis"
        elif analysis_type == "lending":
            result = analyzer.analyze_lending_position(address)
            title = f"{Emoji.LENDING} Lending Position Analysis"
        elif analysis_type == "staking":
            result = analyzer.analyze_staking_position(address)
            title = f"{Emoji.STAKING} Staking Position Analysis"
        elif analysis_type == "identify":
            result = analyzer.identify_defi_protocol(address)
            title = f"{Emoji.SEARCH} Protocol Identification"
        else:
            processing_message.edit_text(
                f"{Emoji.ERROR} Invalid analysis type.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        # Delete processing message
        processing_message.delete()
        
        # Check if the analysis was successful
        if not result.get("success", False):
            update.message.reply_text(
                f"{Emoji.ERROR} Error: {result.get('error', 'Unknown error')}",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        # Format the result as a message
        message = format_defi_result(result, title, address)
        
        # Send the analysis result
        update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN_V2
        )
            
    except Exception as e:
        logger.error(f"Error in DeFi analysis: {e}", exc_info=True)
        processing_message.edit_text(
            f"{Emoji.ERROR} An error occurred: {str(e)}",
            parse_mode=ParseMode.MARKDOWN_V2
        )

def process_impermanent_loss(update: Update, context: CallbackContext) -> None:
    """
    Process impermanent loss calculation.
    """
    address = context.user_data.get("address")
    initial_price = context.user_data.get("initial_price")
    current_price = context.user_data.get("current_price")
    
    # Send processing message
    processing_message = update.message.reply_text(
        f"{Emoji.HOURGLASS} Calculating... This may take a moment.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    try:
        # Get the analyzer service
        analyzer = get_solana_program_analyzer_service()
        
        if not analyzer:
            update.message.reply_text(
                f"{Emoji.ERROR} Sorry, the analyzer service is not available.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        # Calculate impermanent loss
        result = analyzer.calculate_impermanent_loss(address, initial_price, current_price)
        
        # Delete processing message
        processing_message.delete()
        
        # Check if the calculation was successful
        if not result.get("success", False):
            update.message.reply_text(
                f"{Emoji.ERROR} Error: {result.get('error', 'Unknown error')}",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        # Format the result as a message
        title = f"{Emoji.CALCULATOR} Impermanent Loss Calculation"
        message = format_impermanent_loss_result(result, title, address)
        
        # Send the calculation result
        update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN_V2
        )
            
    except Exception as e:
        logger.error(f"Error calculating impermanent loss: {e}", exc_info=True)
        processing_message.edit_text(
            f"{Emoji.ERROR} An error occurred: {str(e)}",
            parse_mode=ParseMode.MARKDOWN_V2
        )

def format_defi_result(result: Dict[str, Any], title: str, address: str) -> str:
    """
    Format DeFi analysis result as a message.
    
    Args:
        result: The analysis result
        title: The title of the analysis
        address: The address analyzed
        
    Returns:
        Formatted message
    """
    message = f"{title}\n\n"
    message += f"*Address:* `{address[:10]}...{address[-4:]}`\n\n"
    
    # Add protocol information if available
    if "protocol" in result:
        protocol = result["protocol"]
        message += f"*Protocol:* {protocol.capitalize()}\n"
    
    # Add type information if available
    if "type" in result:
        analysis_type = result["type"]
        message += f"*Type:* {analysis_type.replace('_', ' ').capitalize()}\n"
    
    # Add note if available
    if "note" in result:
        note = result["note"]
        message += f"\n{note}\n"
    
    # Add is_program if available
    if "is_program" in result:
        is_program = result["is_program"]
        if is_program:
            message += f"\n*This is a program account*\n"
        else:
            message += f"\n*This is a data account*\n"
    
    # Add owner if available
    if "owner" in result:
        owner = result["owner"]
        message += f"*Owner:* `{owner[:10]}...{owner[-4:]}`\n"
    
    return message

def format_impermanent_loss_result(result: Dict[str, Any], title: str, address: str) -> str:
    """
    Format impermanent loss calculation result as a message.
    
    Args:
        result: The calculation result
        title: The title of the calculation
        address: The pool address
        
    Returns:
        Formatted message
    """
    message = f"{title}\n\n"
    message += f"*Pool Address:* `{address[:10]}...{address[-4:]}`\n"
    
    # Add protocol information
    if "protocol" in result:
        protocol = result["protocol"]
        message += f"*Protocol:* {protocol.capitalize()}\n"
    
    # Add pool type if available
    if "pool_type" in result:
        pool_type = result["pool_type"]
        message += f"*Pool Type:* {pool_type.replace('_', ' ').capitalize()}\n\n"
    
    # Add price information
    message += f"*Initial Price:* {result.get('initial_price')}\n"
    message += f"*Current Price:* {result.get('current_price')}\n"
    message += f"*Price Change:* {result.get('price_change_percentage', 0):.2f}%\n\n"
    
    # Add impermanent loss information
    il_percentage = result.get('impermanent_loss_percentage', 0)
    message += f"*Impermanent Loss:* {il_percentage:.2f}%\n"
    
    # Add explanation
    message += "\n*What is impermanent loss?*\n"
    message += "Impermanent loss is the difference between holding tokens versus providing liquidity with them."
    
    return message

def cancel(update: Update, context: CallbackContext) -> int:
    """
    Cancel the conversation.
    """
    update.message.reply_text(
        f"{Emoji.CHECK} DeFi analysis canceled.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return ConversationHandler.END

def get_defi_analysis_handler() -> ConversationHandler:
    """
    Create and return the DeFi analysis conversation handler.
    """
    return ConversationHandler(
        entry_points=[CommandHandler("defi", defi_analysis)],
        states={
            SELECTING_ANALYSIS_TYPE: [
                CallbackQueryHandler(analysis_type_selected, pattern=f"^{ANALYSIS_TYPE_PREFIX}")
            ],
            WAITING_FOR_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command, process_address)
            ],
            WAITING_FOR_ADDITIONAL_INFO: [
                MessageHandler(Filters.text & ~Filters.command, process_additional_info)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ) 