"""
Keyboard templates for Telegram bot.
Provides standardized keyboard layouts and templates for consistent UX.
"""
from typing import List, Dict, Any, Optional, Union, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.message_templates import Emoji

class KeyboardTemplates:
    """Keyboard templates for consistent UI"""
    
    @staticmethod
    def create_pagination_keyboard(
        current_page: int, 
        total_pages: int, 
        callback_prefix: str,
        include_first_last: bool = True,
        items_per_row: int = 5
    ) -> InlineKeyboardMarkup:
        """
        Create a pagination keyboard.
        
        Args:
            current_page: Current page number
            total_pages: Total pages
            callback_prefix: Prefix for callback data
            include_first_last: Whether to include first/last buttons
            items_per_row: Max buttons per row
            
        Returns:
            InlineKeyboardMarkup: Pagination keyboard
        """
        buttons = []
        
        # First page button
        if include_first_last and current_page > 2:
            buttons.append(InlineKeyboardButton(
                f"{Emoji.FIRST} 1", 
                callback_data=f"{callback_prefix}:1"
            ))
        
        # Previous page button
        if current_page > 1:
            buttons.append(InlineKeyboardButton(
                Emoji.BACK, 
                callback_data=f"{callback_prefix}:{current_page-1}"
            ))
        
        # Current page indicator
        buttons.append(InlineKeyboardButton(
            f"{current_page}/{total_pages}", 
            callback_data="noop"
        ))
        
        # Next page button
        if current_page < total_pages:
            buttons.append(InlineKeyboardButton(
                Emoji.NEXT, 
                callback_data=f"{callback_prefix}:{current_page+1}"
            ))
        
        # Last page button
        if include_first_last and current_page < total_pages - 1:
            buttons.append(InlineKeyboardButton(
                f"{total_pages} {Emoji.LAST}", 
                callback_data=f"{callback_prefix}:{total_pages}"
            ))
        
        # Create keyboard with all buttons in one row
        keyboard = [buttons]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
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
            InlineKeyboardMarkup: Menu keyboard
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
            navigation_row.append(InlineKeyboardButton(
                f"{Emoji.BACK} {back_button[0]}", 
                callback_data=back_button[1]
            ))
        
        if cancel_button:
            navigation_row.append(InlineKeyboardButton(
                f"{cancel_button[0]}", 
                callback_data=cancel_button[1]
            ))
        
        if navigation_row:
            keyboard.append(navigation_row)
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_action_keyboard(
        actions: List[Tuple[str, str]],
        items_per_row: int = 2
    ) -> InlineKeyboardMarkup:
        """
        Create an action keyboard.
        
        Args:
            actions: List of (text, callback_data) tuples
            items_per_row: Number of buttons per row
            
        Returns:
            InlineKeyboardMarkup: Action keyboard
        """
        keyboard = []
        row = []
        
        for i, (text, callback_data) in enumerate(actions, 1):
            row.append(InlineKeyboardButton(text, callback_data=callback_data))
            
            if i % items_per_row == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_wizard_keyboard(
        next_text: str = "Next",
        next_callback: str = "wizard:next",
        back_text: Optional[str] = "Back",
        back_callback: Optional[str] = "wizard:back",
        cancel_text: Optional[str] = "Cancel",
        cancel_callback: Optional[str] = "wizard:cancel"
    ) -> InlineKeyboardMarkup:
        """
        Create a wizard navigation keyboard.
        
        Args:
            next_text: Text for next button
            next_callback: Callback data for next button
            back_text: Text for back button (None to omit)
            back_callback: Callback data for back button
            cancel_text: Text for cancel button (None to omit)
            cancel_callback: Callback data for cancel button
            
        Returns:
            InlineKeyboardMarkup: Wizard keyboard
        """
        buttons = []
        
        if back_text and back_callback:
            buttons.append(InlineKeyboardButton(
                f"{Emoji.BACK} {back_text}", 
                callback_data=back_callback
            ))
        
        buttons.append(InlineKeyboardButton(
            f"{next_text} {Emoji.NEXT}", 
            callback_data=next_callback
        ))
        
        keyboard = [buttons]
        
        if cancel_text and cancel_callback:
            keyboard.append([
                InlineKeyboardButton(
                    f"{cancel_text}", 
                    callback_data=cancel_callback
                )
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_scan_depth_keyboard(is_premium: bool) -> InlineKeyboardMarkup:
        """
        Create scan depth selection keyboard.
        
        Args:
            is_premium: Whether user has premium access
            
        Returns:
            InlineKeyboardMarkup: Scan depth keyboard
        """
        keyboard = [
            [InlineKeyboardButton("Standard", callback_data="scan_depth:standard")]
        ]
        
        # Only offer deep/comprehensive options to premium users
        if is_premium:
            keyboard[0].append(InlineKeyboardButton("Deep", callback_data="scan_depth:deep"))
            keyboard.append([InlineKeyboardButton("Comprehensive", callback_data="scan_depth:comprehensive")])
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="scan:cancel")])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_token_actions_keyboard(token_address: str) -> InlineKeyboardMarkup:
        """
        Create token actions keyboard.
        
        Args:
            token_address: Token address
            
        Returns:
            InlineKeyboardMarkup: Token actions keyboard
        """
        keyboard = [
            [
                InlineKeyboardButton("Deep Scan", callback_data=f"token:scan:{token_address}"),
                InlineKeyboardButton("Add to Watchlist", callback_data=f"token:watchlist_add:{token_address}")
            ],
            [
                InlineKeyboardButton("Set Alerts", callback_data=f"token:alerts:{token_address}"),
                InlineKeyboardButton("Share", callback_data=f"token:share:{token_address}")
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard) 