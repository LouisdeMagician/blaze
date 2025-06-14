"""
Telegram bot commands for watchlist management.
Provides commands for users to manage their token watchlists.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple, Union, cast

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters
)

from src.models.user import SubscriptionTier
from src.services.user_service import user_service
from src.services.contract_service import contract_service
from src.services.watchlist_service import watchlist_service
from src.blockchain.utils import is_valid_solana_address, format_address
from src.bot.utils import format_risk_level, paginate_list

logger = logging.getLogger(__name__)

# Conversation states
CHOOSING_ACTION, ADDING_TOKEN, REMOVING_TOKEN, CONFIRMING_CLEAR = range(4)

# Callback data prefixes
PREFIX_VIEW_PAGE = "watchlist_page_"
PREFIX_SORT = "watchlist_sort_"
PREFIX_FILTER = "watchlist_filter_"
PREFIX_TOKEN = "watchlist_token_"
PREFIX_SCAN = "watchlist_scan_"

async def watchlist_command(update: Update, context: CallbackContext) -> int:
    """
    Handle the /watchlist command to view and manage the user's watchlist.
    
    Args:
        update: Telegram update object
        context: Callback context
        
    Returns:
        int: Conversation state
    """
    user = update.effective_user
    telegram_id = str(user.id)
    
    # Get user's watchlist
    watchlist_data = watchlist_service.get_watchlist_paged(
        user_id=telegram_id,
        page=1,
        limit=5
    )
    
    if not watchlist_data["success"] or len(watchlist_data["items"]) == 0:
        # Empty watchlist
        keyboard = [
            [InlineKeyboardButton("➕ Add Token", callback_data="watchlist_add")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Your watchlist is empty. Use the button below to add tokens to your watchlist.",
            reply_markup=reply_markup
        )
        return CHOOSING_ACTION
    
    # Show watchlist items
    items = watchlist_data["items"]
    pagination = watchlist_data["pagination"]
    
    # Create the message text
    text = "*Your Watchlist:*\n\n"
    
    for i, item in enumerate(items, 1):
        name = item.get("name") or "Unknown Token"
        symbol = item.get("symbol") or "???"
        address = item.get("address")
        risk_level = item.get("risk_level", "unknown")
        
        text += f"{i}. *{name} ({symbol})*\n"
        text += f"   Address: `{format_address(address)}`\n"
        text += f"   Risk: {format_risk_level(risk_level)}\n\n"
    
    # Add pagination info
    total_pages = pagination["total_pages"]
    current_page = pagination["current_page"]
    total_items = pagination["total_items"]
    
    if total_pages > 1:
        text += f"\nPage {current_page} of {total_pages} ({total_items} tokens total)"
    
    # Create the keyboard
    keyboard = []
    
    # Pagination buttons
    pagination_row = []
    if current_page > 1:
        pagination_row.append(
            InlineKeyboardButton("◀️ Previous", callback_data=f"{PREFIX_VIEW_PAGE}{current_page-1}")
        )
    if current_page < total_pages:
        pagination_row.append(
            InlineKeyboardButton("Next ▶️", callback_data=f"{PREFIX_VIEW_PAGE}{current_page+1}")
        )
    if pagination_row:
        keyboard.append(pagination_row)
    
    # Action buttons
    keyboard.append([
        InlineKeyboardButton("➕ Add", callback_data="watchlist_add"),
        InlineKeyboardButton("➖ Remove", callback_data="watchlist_remove"),
        InlineKeyboardButton("🔍 Scan All", callback_data="watchlist_scan_all")
    ])
    
    # Filter buttons
    keyboard.append([
        InlineKeyboardButton("🔴 High Risk", callback_data=f"{PREFIX_FILTER}high"),
        InlineKeyboardButton("🔄 Reset Filter", callback_data=f"{PREFIX_VIEW_PAGE}1")
    ])
    
    # Sort buttons
    keyboard.append([
        InlineKeyboardButton("Sort by Risk", callback_data=f"{PREFIX_SORT}risk_level"),
        InlineKeyboardButton("Sort by Name", callback_data=f"{PREFIX_SORT}name")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store current filter and sort in user data
    context.user_data["watchlist_page"] = current_page
    context.user_data["watchlist_sort"] = None
    context.user_data["watchlist_sort_dir"] = "asc"
    context.user_data["watchlist_filter"] = None
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    return CHOOSING_ACTION

async def watchlist_button_handler(update: Update, context: CallbackContext) -> int:
    """
    Handle button presses in the watchlist UI.
    
    Args:
        update: Telegram update object
        context: Callback context
        
    Returns:
        int: Conversation state
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = str(user.id)
    data = query.data
    
    # Get current state from user_data
    page = context.user_data.get("watchlist_page", 1)
    sort_by = context.user_data.get("watchlist_sort", None)
    sort_dir = context.user_data.get("watchlist_sort_dir", "asc")
    filter_risk = context.user_data.get("watchlist_filter", None)
    
    # Handle different button actions
    if data == "watchlist_add":
        await query.edit_message_text(
            "Please send the Solana token/contract address you want to add to your watchlist.\n\n"
            "Or /cancel to go back to your watchlist."
        )
        return ADDING_TOKEN
    
    elif data == "watchlist_remove":
        # Get watchlist to let user choose what to remove
        watchlist_data = watchlist_service.get_watchlist(telegram_id)
        
        if not watchlist_data:
            await query.edit_message_text(
                "Your watchlist is empty. Nothing to remove.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Back to Watchlist", callback_data="watchlist_back")
                ]])
            )
            return CHOOSING_ACTION
        
        keyboard = []
        for item in watchlist_data:
            name = item.get("name") or "Unknown Token"
            symbol = item.get("symbol") or "???"
            address = item.get("address")
            
            # Create button for each token
            display_name = f"{name} ({symbol})"
            keyboard.append([
                InlineKeyboardButton(f"❌ {display_name}", callback_data=f"{PREFIX_TOKEN}{address}")
            ])
        
        # Add cancel button
        keyboard.append([
            InlineKeyboardButton("↩️ Back to Watchlist", callback_data="watchlist_back")
        ])
        
        await query.edit_message_text(
            "Select a token to remove from your watchlist:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return REMOVING_TOKEN
    
    elif data == "watchlist_back":
        # Return to the main watchlist view
        return await refresh_watchlist_view(update, context, query)
    
    elif data == "watchlist_scan_all":
        # Trigger scan for all watchlist items
        await query.edit_message_text("Scanning all tokens in your watchlist... This may take a moment.")
        
        result = watchlist_service.scan_watchlist(telegram_id)
        
        if result["success"]:
            await query.edit_message_text(
                f"{result['message']}\n\nReloading watchlist...",
            )
            # Refresh the watchlist view
            return await refresh_watchlist_view(update, context, query)
        else:
            await query.edit_message_text(
                f"Error scanning watchlist: {result['error']}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Back to Watchlist", callback_data="watchlist_back")
                ]])
            )
            return CHOOSING_ACTION
    
    elif data.startswith(PREFIX_VIEW_PAGE):
        # Handle pagination
        try:
            new_page = int(data[len(PREFIX_VIEW_PAGE):])
            context.user_data["watchlist_page"] = new_page
            return await refresh_watchlist_view(update, context, query)
        except ValueError:
            logger.error(f"Invalid page number: {data}")
            return CHOOSING_ACTION
    
    elif data.startswith(PREFIX_SORT):
        # Handle sorting
        sort_field = data[len(PREFIX_SORT):]
        
        # Toggle sort direction if same field selected again
        if sort_field == sort_by:
            sort_dir = "desc" if sort_dir == "asc" else "asc"
        else:
            sort_dir = "asc"
        
        context.user_data["watchlist_sort"] = sort_field
        context.user_data["watchlist_sort_dir"] = sort_dir
        context.user_data["watchlist_page"] = 1  # Reset to first page
        
        return await refresh_watchlist_view(update, context, query)
    
    elif data.startswith(PREFIX_FILTER):
        # Handle filtering
        filter_value = data[len(PREFIX_FILTER):]
        
        # Toggle filter if same value selected again
        if filter_value == filter_risk:
            filter_risk = None
        else:
            filter_risk = filter_value
        
        context.user_data["watchlist_filter"] = filter_risk
        context.user_data["watchlist_page"] = 1  # Reset to first page
        
        return await refresh_watchlist_view(update, context, query)
    
    elif data.startswith(PREFIX_TOKEN):
        # Handle token selection (for removal or details)
        token_address = data[len(PREFIX_TOKEN):]
        
        # Store the token address for removal confirmation
        context.user_data["selected_token"] = token_address
        
        # Get token details
        contract = contract_service.get_contract(token_address)
        name = contract.name if contract else "Unknown Token"
        symbol = contract.symbol if contract else "???"
        
        # Ask for confirmation
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm Remove", callback_data="watchlist_confirm_remove"),
                InlineKeyboardButton("❌ Cancel", callback_data="watchlist_cancel_remove")
            ]
        ]
        
        await query.edit_message_text(
            f"Are you sure you want to remove *{name} ({symbol})* from your watchlist?\n\n"
            f"Address: `{format_address(token_address)}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CONFIRMING_CLEAR
    
    elif data == "watchlist_confirm_remove":
        # Confirm token removal
        token_address = context.user_data.get("selected_token")
        if not token_address:
            await query.edit_message_text("Error: No token selected for removal.")
            return CHOOSING_ACTION
        
        # Remove token from watchlist
        result = watchlist_service.remove_from_watchlist(telegram_id, token_address)
        
        if result["success"]:
            await query.edit_message_text(
                f"{result['message']}\n\nReloading watchlist..."
            )
            # Clear the selected token
            context.user_data.pop("selected_token", None)
            
            # Refresh the watchlist view
            return await refresh_watchlist_view(update, context, query)
        else:
            await query.edit_message_text(
                f"Error removing token: {result['error']}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Back to Watchlist", callback_data="watchlist_back")
                ]])
            )
            return CHOOSING_ACTION
    
    elif data == "watchlist_cancel_remove":
        # Cancel token removal
        context.user_data.pop("selected_token", None)
        return await refresh_watchlist_view(update, context, query)
    
    elif data.startswith(PREFIX_SCAN):
        # Handle individual token scan
        if data == "watchlist_scan_all":
            # Already handled above
            pass
        else:
            token_address = data[len(PREFIX_SCAN):]
            await query.edit_message_text(f"Scanning token... This may take a moment.")
            
            user = user_service.get_user(telegram_id)
            if not user:
                await query.edit_message_text("Error: User not found.")
                return CHOOSING_ACTION
            
            # Determine scan depth based on subscription tier
            scan_depth = "standard"
            if user.subscription_tier in [SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE]:
                scan_depth = "deep"
            
            try:
                if user.subscription_tier in [SubscriptionTier.BASIC, SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE]:
                    from src.services.advanced_scanner import advanced_scanner
                    scan_result = advanced_scanner.enhanced_scan(token_address, telegram_id, True, scan_depth)
                else:
                    from src.services.scanner import contract_scanner
                    scan_result = contract_scanner.scan_contract(token_address, telegram_id, True)
                
                if scan_result:
                    await query.edit_message_text(
                        f"Scan completed for token: {format_address(token_address)}\n\nReloading watchlist..."
                    )
                else:
                    await query.edit_message_text(
                        f"Error scanning token: Scan failed\n\nReloading watchlist..."
                    )
            except Exception as e:
                logger.error(f"Error scanning token {token_address}: {e}")
                await query.edit_message_text(
                    f"Error scanning token: {str(e)}\n\nReloading watchlist..."
                )
            
            # Refresh the watchlist view
            return await refresh_watchlist_view(update, context, query)
    
    # Default fallback
    return CHOOSING_ACTION

async def refresh_watchlist_view(update: Update, context: CallbackContext, query) -> int:
    """
    Refresh the watchlist view with current filters and sorting.
    
    Args:
        update: Telegram update object
        context: Callback context
        query: Callback query
        
    Returns:
        int: Conversation state
    """
    user = update.effective_user
    telegram_id = str(user.id)
    
    # Get current state from user_data
    page = context.user_data.get("watchlist_page", 1)
    sort_by = context.user_data.get("watchlist_sort", None)
    sort_dir = context.user_data.get("watchlist_sort_dir", "asc")
    filter_risk = context.user_data.get("watchlist_filter", None)
    
    # Get user's watchlist with current filters and sorting
    watchlist_data = watchlist_service.get_watchlist_paged(
        user_id=telegram_id,
        page=page,
        limit=5,
        sort_by=sort_by,
        sort_dir=sort_dir,
        filter_risk=filter_risk
    )
    
    if not watchlist_data["success"] or len(watchlist_data["items"]) == 0:
        # Empty watchlist or filter resulted in no items
        if filter_risk:
            text = f"No tokens with risk level '{filter_risk}' found in your watchlist."
            keyboard = [[InlineKeyboardButton("🔄 Reset Filter", callback_data=f"{PREFIX_VIEW_PAGE}1")]]
        else:
            text = "Your watchlist is empty. Use the button below to add tokens to your watchlist."
            keyboard = [[InlineKeyboardButton("➕ Add Token", callback_data="watchlist_add")]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
        return CHOOSING_ACTION
    
    # Show watchlist items
    items = watchlist_data["items"]
    pagination = watchlist_data["pagination"]
    
    # Create the message text
    text = "*Your Watchlist:*\n\n"
    
    # Add active filters/sorting info
    filter_info = []
    if filter_risk:
        filter_info.append(f"Filtered by risk: {filter_risk.upper()}")
    if sort_by:
        sort_info = f"Sorted by {sort_by.replace('_', ' ')} ({sort_dir})"
        filter_info.append(sort_info)
    
    if filter_info:
        text += f"*{' | '.join(filter_info)}*\n\n"
    
    for i, item in enumerate(items, 1):
        name = item.get("name") or "Unknown Token"
        symbol = item.get("symbol") or "???"
        address = item.get("address")
        risk_level = item.get("risk_level", "unknown")
        
        text += f"{i}. *{name} ({symbol})*\n"
        text += f"   Address: `{format_address(address)}`\n"
        text += f"   Risk: {format_risk_level(risk_level)}\n"
        text += f"   [Scan Now](callback_data={PREFIX_SCAN}{address})\n\n"
    
    # Add pagination info
    total_pages = pagination["total_pages"]
    current_page = pagination["current_page"]
    total_items = pagination["total_items"]
    
    if total_pages > 1:
        text += f"\nPage {current_page} of {total_pages} ({total_items} tokens total)"
    
    # Create the keyboard
    keyboard = []
    
    # Pagination buttons
    pagination_row = []
    if current_page > 1:
        pagination_row.append(
            InlineKeyboardButton("◀️ Previous", callback_data=f"{PREFIX_VIEW_PAGE}{current_page-1}")
        )
    if current_page < total_pages:
        pagination_row.append(
            InlineKeyboardButton("Next ▶️", callback_data=f"{PREFIX_VIEW_PAGE}{current_page+1}")
        )
    if pagination_row:
        keyboard.append(pagination_row)
    
    # Action buttons
    keyboard.append([
        InlineKeyboardButton("➕ Add", callback_data="watchlist_add"),
        InlineKeyboardButton("➖ Remove", callback_data="watchlist_remove"),
        InlineKeyboardButton("🔍 Scan All", callback_data="watchlist_scan_all")
    ])
    
    # Filter buttons
    filter_row = []
    risk_levels = ["low", "medium", "high", "critical"]
    for level in risk_levels:
        if level == filter_risk:
            # Show selected filter with a checkmark
            filter_row.append(
                InlineKeyboardButton(f"✓ {level.title()}", callback_data=f"{PREFIX_FILTER}{level}")
            )
        else:
            filter_row.append(
                InlineKeyboardButton(level.title(), callback_data=f"{PREFIX_FILTER}{level}")
            )
    
    # Split into two rows if needed
    if len(filter_row) > 2:
        keyboard.append(filter_row[:2])
        keyboard.append(filter_row[2:])
    else:
        keyboard.append(filter_row)
    
    # Add reset filter button if filtering is active
    if filter_risk or sort_by:
        keyboard.append([
            InlineKeyboardButton("🔄 Reset Filters/Sorting", callback_data=f"{PREFIX_VIEW_PAGE}1")
        ])
    
    # Sort buttons
    sort_fields = [
        ("name", "Name"),
        ("symbol", "Symbol"),
        ("risk_level", "Risk")
    ]
    
    sort_row = []
    for field, label in sort_fields:
        if field == sort_by:
            # Show selected sort with direction indicator
            direction = "▼" if sort_dir == "desc" else "▲"
            sort_row.append(
                InlineKeyboardButton(f"{label} {direction}", callback_data=f"{PREFIX_SORT}{field}")
            )
        else:
            sort_row.append(
                InlineKeyboardButton(label, callback_data=f"{PREFIX_SORT}{field}")
            )
    
    keyboard.append(sort_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    return CHOOSING_ACTION

async def add_token_handler(update: Update, context: CallbackContext) -> int:
    """
    Handle token address input when adding to watchlist.
    
    Args:
        update: Telegram update object
        context: Callback context
        
    Returns:
        int: Conversation state
    """
    user = update.effective_user
    telegram_id = str(user.id)
    
    # Get the token address
    address = update.message.text.strip()
    
    # Check if valid Solana address
    if not is_valid_solana_address(address):
        await update.message.reply_text(
            "Invalid Solana address format. Please try again with a valid address.\n\n"
            "Or /cancel to go back to your watchlist."
        )
        return ADDING_TOKEN
    
    # Add to watchlist
    result = watchlist_service.add_to_watchlist(telegram_id, address)
    
    if result["success"]:
        await update.message.reply_text(f"{result['message']}")
        
        # Show updated watchlist
        context.user_data["watchlist_page"] = 1  # Reset to first page
        
        # Create a fake callback query for refresh_watchlist_view
        class FakeQuery:
            async def edit_message_text(self, *args, **kwargs):
                return await update.message.reply_text(*args, **kwargs)
        
        return await refresh_watchlist_view(update, context, FakeQuery())
    else:
        keyboard = [[InlineKeyboardButton("Try Again", callback_data="watchlist_add")]]
        await update.message.reply_text(
            f"Error adding to watchlist: {result['error']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSING_ACTION

async def watchlist_stats_command(update: Update, context: CallbackContext) -> None:
    """
    Handle the /watchlist_stats command to show statistics about a user's watchlist.
    
    Args:
        update: Telegram update object
        context: Callback context
    """
    user = update.effective_user
    telegram_id = str(user.id)
    
    # Get watchlist statistics
    result = watchlist_service.get_watchlist_stats(telegram_id)
    
    if not result["success"]:
        await update.message.reply_text(f"Error getting watchlist statistics: {result['error']}")
        return
    
    if "message" in result and "stats" not in result:
        await update.message.reply_text(result["message"])
        return
    
    stats = result["stats"]
    
    # Format the statistics message
    text = "*Watchlist Statistics:*\n\n"
    
    # Total tokens
    text += f"*Total Tokens:* {stats['total_tokens']}\n\n"
    
    # Risk distribution
    text += "*Risk Level Distribution:*\n"
    risk_distribution = stats["risk_distribution"]
    
    for level, count in risk_distribution.items():
        if count > 0:
            text += f"• {format_risk_level(level)}: {count} tokens\n"
    
    text += "\n"
    
    # Scan information
    if stats.get("latest_scan"):
        text += f"*Latest Scan:* {stats['latest_scan'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    
    if stats.get("days_since_latest_scan") is not None:
        text += f"*Days Since Last Scan:* {stats['days_since_latest_scan']}\n"
    
    # Add watchlist limits
    limits = watchlist_service.get_watchlist_limits(telegram_id)
    if limits["success"]:
        text += "\n*Watchlist Limits:*\n"
        text += f"• Current Usage: {limits['current_size']} / {limits['max_size']} tokens\n"
        text += f"• Subscription Tier: {limits['subscription_tier']}\n"
        text += f"• Scan Frequency: Every {limits['scan_frequency_hours']} hours\n"
    
    # Add keyboard with actions
    keyboard = [
        [
            InlineKeyboardButton("📋 View Watchlist", callback_data="open_watchlist"),
            InlineKeyboardButton("🔍 Scan All", callback_data="watchlist_scan_all")
        ]
    ]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_command(update: Update, context: CallbackContext) -> int:
    """
    Cancel the current conversation and return to the watchlist.
    
    Args:
        update: Telegram update object
        context: Callback context
        
    Returns:
        int: ConversationHandler.END
    """
    await update.message.reply_text(
        "Cancelled. Use /watchlist to view your watchlist."
    )
    return ConversationHandler.END

def get_watchlist_handlers():
    """
    Get the handlers for watchlist commands.
    
    Returns:
        list: List of handlers
    """
    # Create conversation handler for watchlist
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("watchlist", watchlist_command)],
        states={
            CHOOSING_ACTION: [
                CallbackQueryHandler(watchlist_button_handler)
            ],
            ADDING_TOKEN: [
                MessageHandler(Filters.text & ~Filters.command, add_token_handler),
                CommandHandler("cancel", cancel_command)
            ],
            REMOVING_TOKEN: [
                CallbackQueryHandler(watchlist_button_handler)
            ],
            CONFIRMING_CLEAR: [
                CallbackQueryHandler(watchlist_button_handler)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    
    return [
        conv_handler,
        CommandHandler("watchlist_stats", watchlist_stats_command),
        # Add /watch as an alias for adding to watchlist
        CommandHandler("watch", lambda u, c: add_token_handler(u, c) if u.message.text.split(" ", 1)[1:] else watchlist_command(u, c))
    ] 