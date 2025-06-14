"""
Account Visualization Command.
Provides commands for visualizing Solana account relationships.
"""
import logging
import io
from typing import Dict, List, Any, Optional, Union

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    CommandHandler, CallbackContext, ConversationHandler,
    MessageHandler, CallbackQueryHandler, Filters
)

from src.services.solana_program_analyzer_service import get_solana_program_analyzer_service
from src.utils.validators import validate_solana_address
from src.utils.message_formatter import format_message
from src.bot.emoji import Emoji

# Define conversation states
SELECTING_VISUALIZATION_TYPE = 0
WAITING_FOR_ADDRESS = 1
WAITING_FOR_SIGNATURE = 2

# Define callback data prefixes
VISUALIZE_TYPE_PREFIX = "viz_type:"
VISUALIZE_ACCOUNT_PREFIX = "viz_account:"
BACK_TO_MENU = "viz_back_to_menu"

logger = logging.getLogger(__name__)

def account_visualization(update: Update, context: CallbackContext) -> int:
    """
    Handle the /visualize command.
    Starts the account visualization flow.
    """
    keyboard = [
        [
            InlineKeyboardButton(f"{Emoji.PROGRAM} Program Interactions", 
                               callback_data=f"{VISUALIZE_TYPE_PREFIX}program"),
            InlineKeyboardButton(f"{Emoji.TOKEN} Token Holders", 
                               callback_data=f"{VISUALIZE_TYPE_PREFIX}token")
        ],
        [
            InlineKeyboardButton(f"{Emoji.ACCOUNT} Account Hierarchy", 
                               callback_data=f"{VISUALIZE_TYPE_PREFIX}account"),
            InlineKeyboardButton(f"{Emoji.TRANSACTION} Transaction", 
                               callback_data=f"{VISUALIZE_TYPE_PREFIX}transaction")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"{Emoji.CHART} *Solana Account Visualization*\n\n"
        f"Select the type of visualization you want to generate:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return SELECTING_VISUALIZATION_TYPE

def visualization_type_selected(update: Update, context: CallbackContext) -> int:
    """
    Handle visualization type selection.
    """
    query = update.callback_query
    query.answer()
    
    # Extract visualization type from callback data
    viz_type = query.data.split(":")[1]
    
    # Store the selected type for later use
    context.user_data["viz_type"] = viz_type
    
    # Determine next prompt based on type
    if viz_type == "program":
        message = f"{Emoji.PROGRAM} Please send me the Solana program ID to visualize interactions"
    elif viz_type == "token":
        message = f"{Emoji.TOKEN} Please send me the Solana token mint address to visualize holders"
    elif viz_type == "account":
        message = f"{Emoji.ACCOUNT} Please send me the Solana account address to visualize hierarchy"
    elif viz_type == "transaction":
        message = f"{Emoji.TRANSACTION} Please send me the transaction signature to visualize accounts"
        query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAITING_FOR_SIGNATURE
    else:
        message = "Invalid visualization type selected"
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
    viz_type = context.user_data.get("viz_type")
    
    # Validate the address
    if not validate_solana_address(address):
        update.message.reply_text(
            f"{Emoji.ERROR} Invalid Solana address format. Please try again.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return WAITING_FOR_ADDRESS
    
    # Store the address for later use
    context.user_data["address"] = address
    
    # Send processing message
    processing_message = update.message.reply_text(
        f"{Emoji.HOURGLASS} Generating visualization... This may take a moment.",
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
            return ConversationHandler.END
        
        # Generate the visualization based on type
        if viz_type == "program":
            result = analyzer.visualize_program_interactions(address)
            caption = f"{Emoji.PROGRAM} Program Interactions: `{address[:10]}...`"
        elif viz_type == "token":
            result = analyzer.visualize_token_holders(address)
            caption = f"{Emoji.TOKEN} Token Holders: `{address[:10]}...`"
        elif viz_type == "account":
            result = analyzer.visualize_account_hierarchy(address)
            caption = f"{Emoji.ACCOUNT} Account Hierarchy: `{address[:10]}...`"
        else:
            processing_message.edit_text(
                f"{Emoji.ERROR} Invalid visualization type.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
        
        # Check if the visualization was successful
        if not result.get("success", False):
            processing_message.edit_text(
                f"{Emoji.ERROR} Error generating visualization: {result.get('error', 'Unknown error')}",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
        
        # Delete processing message
        processing_message.delete()
        
        # Send the visualization
        viz_buffer = result.get("visualization")
        if viz_buffer:
            # Create keyboard for further actions
            keyboard = [
                [
                    InlineKeyboardButton(f"{Emoji.BACK} Back to Menu", 
                                      callback_data=BACK_TO_MENU)
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send the image
            update.message.reply_photo(
                photo=viz_buffer,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup
            )
            
            # Wait for user to select next action
            return SELECTING_VISUALIZATION_TYPE
        else:
            update.message.reply_text(
                f"{Emoji.ERROR} Failed to generate visualization.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Error in account visualization: {e}", exc_info=True)
        processing_message.edit_text(
            f"{Emoji.ERROR} An error occurred: {str(e)}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

def process_transaction_signature(update: Update, context: CallbackContext) -> int:
    """
    Process the transaction signature input from the user.
    """
    signature = update.message.text.strip()
    
    # Store the signature for later use
    context.user_data["signature"] = signature
    
    # Send processing message
    processing_message = update.message.reply_text(
        f"{Emoji.HOURGLASS} Generating visualization... This may take a moment.",
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
            return ConversationHandler.END
        
        # Generate the visualization
        result = analyzer.visualize_transaction_accounts(signature)
        
        # Check if the visualization was successful
        if not result.get("success", False):
            processing_message.edit_text(
                f"{Emoji.ERROR} Error generating visualization: {result.get('error', 'Unknown error')}",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
        
        # Delete processing message
        processing_message.delete()
        
        # Send the visualization
        viz_buffer = result.get("visualization")
        if viz_buffer:
            # Create keyboard for further actions
            keyboard = [
                [
                    InlineKeyboardButton(f"{Emoji.BACK} Back to Menu", 
                                      callback_data=BACK_TO_MENU)
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send the image
            update.message.reply_photo(
                photo=viz_buffer,
                caption=f"{Emoji.TRANSACTION} Transaction: `{signature[:10]}...`",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup
            )
            
            # Wait for user to select next action
            return SELECTING_VISUALIZATION_TYPE
        else:
            update.message.reply_text(
                f"{Emoji.ERROR} Failed to generate visualization.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Error in account visualization: {e}", exc_info=True)
        processing_message.edit_text(
            f"{Emoji.ERROR} An error occurred: {str(e)}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

def back_to_menu(update: Update, context: CallbackContext) -> int:
    """
    Handle back to menu button.
    """
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton(f"{Emoji.PROGRAM} Program Interactions", 
                               callback_data=f"{VISUALIZE_TYPE_PREFIX}program"),
            InlineKeyboardButton(f"{Emoji.TOKEN} Token Holders", 
                               callback_data=f"{VISUALIZE_TYPE_PREFIX}token")
        ],
        [
            InlineKeyboardButton(f"{Emoji.ACCOUNT} Account Hierarchy", 
                               callback_data=f"{VISUALIZE_TYPE_PREFIX}account"),
            InlineKeyboardButton(f"{Emoji.TRANSACTION} Transaction", 
                               callback_data=f"{VISUALIZE_TYPE_PREFIX}transaction")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_caption(
        caption=f"{Emoji.CHART} *Solana Account Visualization*\n\n"
               f"Select the type of visualization you want to generate:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return SELECTING_VISUALIZATION_TYPE

def cancel(update: Update, context: CallbackContext) -> int:
    """
    Cancel the conversation.
    """
    update.message.reply_text(
        f"{Emoji.CHECK} Account visualization canceled.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return ConversationHandler.END

def get_account_visualization_handler() -> ConversationHandler:
    """
    Create and return the account visualization conversation handler.
    """
    return ConversationHandler(
        entry_points=[CommandHandler("visualize", account_visualization)],
        states={
            SELECTING_VISUALIZATION_TYPE: [
                CallbackQueryHandler(visualization_type_selected, pattern=f"^{VISUALIZE_TYPE_PREFIX}"),
                CallbackQueryHandler(back_to_menu, pattern=f"^{BACK_TO_MENU}$")
            ],
            WAITING_FOR_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command, process_address)
            ],
            WAITING_FOR_SIGNATURE: [
                MessageHandler(Filters.text & ~Filters.command, process_transaction_signature)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ) 