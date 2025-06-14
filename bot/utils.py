"""
Utility functions for the Telegram bot.
Provides helper functions for message formatting and UI.
"""
import math
from typing import List, Dict, Any, Optional, Union, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def format_risk_level(risk_level: str) -> str:
    """
    Format a risk level for display.
    
    Args:
        risk_level: Risk level string
        
    Returns:
        str: Formatted risk level
    """
    risk_level = risk_level.lower()
    
    if risk_level == "low":
        return "🟢 Low"
    elif risk_level == "medium":
        return "🟡 Medium"
    elif risk_level == "high":
        return "🔴 High"
    elif risk_level == "critical":
        return "⚠️ Critical"
    else:
        return "❓ Unknown"

def format_address(address: str, max_length: int = 20) -> str:
    """
    Format a blockchain address for display (truncate if needed).
    
    Args:
        address: Blockchain address
        max_length: Maximum length before truncating
        
    Returns:
        str: Formatted address
    """
    if not address:
        return ""
    
    if len(address) <= max_length:
        return address
    
    # Truncate in the middle
    start_chars = max_length // 2 - 2
    end_chars = max_length - start_chars - 3
    
    return f"{address[:start_chars]}...{address[-end_chars:]}"

def paginate_list(items: List[Any], page: int = 1, items_per_page: int = 5) -> Tuple[List[Any], Dict[str, int]]:
    """
    Paginate a list of items.
    
    Args:
        items: List of items to paginate
        page: Current page number (starting at 1)
        items_per_page: Number of items per page
        
    Returns:
        Tuple with paginated items and pagination info
    """
    total_items = len(items)
    total_pages = math.ceil(total_items / items_per_page)
    
    # Ensure valid page number
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    
    # Get items for current page
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_items = items[start_idx:end_idx]
    
    pagination_info = {
        "current_page": page,
        "items_per_page": items_per_page,
        "total_items": total_items,
        "total_pages": total_pages
    }
    
    return page_items, pagination_info

def create_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    items_per_row: int = 3,
    include_first_last: bool = True
) -> List[List[InlineKeyboardButton]]:
    """
    Create a pagination keyboard.
    
    Args:
        current_page: Current page number
        total_pages: Total number of pages
        callback_prefix: Prefix for callback data
        items_per_row: Number of buttons per row
        include_first_last: Whether to include first/last buttons
        
    Returns:
        List of keyboard rows
    """
    keyboard = []
    buttons = []
    
    # First page button
    if include_first_last and current_page > 2:
        buttons.append(InlineKeyboardButton("« 1", callback_data=f"{callback_prefix}1"))
    
    # Previous page button
    if current_page > 1:
        buttons.append(InlineKeyboardButton("◀️", callback_data=f"{callback_prefix}{current_page-1}"))
    
    # Current page indicator
    buttons.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop"))
    
    # Next page button
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton("▶️", callback_data=f"{callback_prefix}{current_page+1}"))
    
    # Last page button
    if include_first_last and current_page < total_pages - 1:
        buttons.append(InlineKeyboardButton(f"{total_pages} »", callback_data=f"{callback_prefix}{total_pages}"))
    
    # Split buttons into rows
    while buttons:
        row = buttons[:items_per_row]
        buttons = buttons[items_per_row:]
        keyboard.append(row)
    
    return keyboard

def create_menu_keyboard(
    options: List[Tuple[str, str]], 
    back_button: Optional[Tuple[str, str]] = None,
    cancel_button: Optional[Tuple[str, str]] = None,
    items_per_row: int = 2
) -> InlineKeyboardMarkup:
    """
    Create a menu keyboard with options.
    
    Args:
        options: List of (text, callback_data) tuples
        back_button: Optional (text, callback_data) for back button
        cancel_button: Optional (text, callback_data) for cancel button
        items_per_row: Number of buttons per row
        
    Returns:
        InlineKeyboardMarkup
    """
    keyboard = []
    row = []
    
    for i, (text, callback_data) in enumerate(options, 1):
        row.append(InlineKeyboardButton(text, callback_data=callback_data))
        
        if i % items_per_row == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    # Add back/cancel buttons if provided
    navigation_row = []
    
    if back_button:
        navigation_row.append(InlineKeyboardButton(back_button[0], callback_data=back_button[1]))
    
    if cancel_button:
        navigation_row.append(InlineKeyboardButton(cancel_button[0], callback_data=cancel_button[1]))
    
    if navigation_row:
        keyboard.append(navigation_row)
    
    return InlineKeyboardMarkup(keyboard) 