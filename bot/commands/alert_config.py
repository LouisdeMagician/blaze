"""
Alert configuration command handlers for Telegram bot.
"""
import logging
from typing import Dict, Any, List, Optional, Union, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import CallbackContext, ConversationHandler, Filters

from src.models.alert import AlertType, AlertSeverity, AlertCategory
from src.models.alert_settings import AlertSettings
from src.services.user_service import user_service
from src.services.alert_service import alert_service

logger = logging.getLogger(__name__)

# Conversation states
SELECTING_SETTING = 1
CONFIGURING_THRESHOLDS = 2
CONFIGURING_TYPES = 3
CONFIGURING_QUIET_HOURS = 4
CONFIGURING_DELIVERY = 5

# Callback data patterns
SETTINGS_PREFIX = "alert_config_"


def alert_config_command(update: Update, context: CallbackContext) -> int:
    """
    Handle the /alert_config command.
    Entry point for alert configuration flow.
    """
    try:
        user_id = str(update.effective_user.id)
        
        # Get user data
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            # Create user if not exists
            db_user = user_service.create_user(user_id, update.effective_user.username)
        
        # Check if user can use alerts
        if not db_user.can_use_feature("alerts"):
            update.effective_message.reply_text(
                "Alert configuration is only available for Basic, Premium, and Enterprise subscribers."
            )
            return ConversationHandler.END
        
        # Show main configuration menu
        keyboard = [
            [
                InlineKeyboardButton("📊 Alert Thresholds", 
                                    callback_data=f"{SETTINGS_PREFIX}thresholds")
            ],
            [
                InlineKeyboardButton("🔔 Alert Types", 
                                    callback_data=f"{SETTINGS_PREFIX}types")
            ],
            [
                InlineKeyboardButton("🔕 Quiet Hours", 
                                    callback_data=f"{SETTINGS_PREFIX}quiet_hours")
            ],
            [
                InlineKeyboardButton("📬 Delivery Preferences", 
                                    callback_data=f"{SETTINGS_PREFIX}delivery")
            ],
            [
                InlineKeyboardButton("✅ Enable All Alerts", 
                                    callback_data=f"{SETTINGS_PREFIX}enable_all"),
                InlineKeyboardButton("❌ Disable All Alerts", 
                                    callback_data=f"{SETTINGS_PREFIX}disable_all")
            ],
            [
                InlineKeyboardButton("✓ Done", 
                                    callback_data=f"{SETTINGS_PREFIX}done")
            ]
        ]
        
        # Store current settings in context
        context.user_data["alert_settings"] = db_user.alert_settings
        
        # Show current settings summary
        message = _format_settings_summary(db_user.alert_settings)
        
        update.effective_message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECTING_SETTING
        
    except Exception as e:
        logger.error(f"Error in alert config command: {e}", exc_info=True)
        update.effective_message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )
        return ConversationHandler.END


def alert_config_button_handler(update: Update, context: CallbackContext) -> int:
    """Handle button clicks in the alert configuration flow."""
    try:
        query = update.callback_query
        query.answer()
        
        # Get callback data and user ID
        callback_data = query.data
        user_id = str(update.effective_user.id)
        
        # Get user data
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            query.edit_message_text("User not found. Please try again.")
            return ConversationHandler.END
        
        # Handle main menu options
        if callback_data == f"{SETTINGS_PREFIX}thresholds":
            # Show threshold configuration menu
            return _show_threshold_config(update, context, db_user.alert_settings)
            
        elif callback_data == f"{SETTINGS_PREFIX}types":
            # Show alert types configuration menu
            return _show_alert_types_config(update, context, db_user.alert_settings)
            
        elif callback_data == f"{SETTINGS_PREFIX}quiet_hours":
            # Show quiet hours configuration menu
            return _show_quiet_hours_config(update, context, db_user.alert_settings)
            
        elif callback_data == f"{SETTINGS_PREFIX}delivery":
            # Show delivery preferences configuration menu
            return _show_delivery_config(update, context, db_user.alert_settings)
            
        elif callback_data == f"{SETTINGS_PREFIX}enable_all":
            # Enable all alerts
            settings = db_user.alert_settings
            settings.enabled = True
            settings.notify_price_changes = True
            settings.notify_liquidity_changes = True
            settings.notify_ownership_changes = True
            settings.notify_risk_changes = True
            settings.notify_whale_movements = True
            
            # Save settings
            user_service.update_user(db_user)
            
            # Update message
            query.edit_message_text(
                "✅ All alerts have been enabled.\n\nUse /alert_config to configure more settings.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
            
        elif callback_data == f"{SETTINGS_PREFIX}disable_all":
            # Disable all alerts
            settings = db_user.alert_settings
            settings.enabled = False
            
            # Save settings
            user_service.update_user(db_user)
            
            # Update message
            query.edit_message_text(
                "❌ All alerts have been disabled.\n\nUse /alert_config to re-enable alerts.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
            
        elif callback_data == f"{SETTINGS_PREFIX}done":
            # End the configuration flow
            query.edit_message_text(
                "Alert configuration saved.\n\nUse /alerts to view your current alerts.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
            
        # Handle threshold configuration
        elif callback_data.startswith(f"{SETTINGS_PREFIX}threshold_"):
            # Parse threshold type
            threshold_type = callback_data.replace(f"{SETTINGS_PREFIX}threshold_", "")
            
            # Request threshold value
            if threshold_type == "price":
                query.edit_message_text(
                    "Please enter the minimum price change percentage that should trigger an alert (e.g., 5):",
                    parse_mode=ParseMode.MARKDOWN
                )
                context.user_data["configuring"] = "price_threshold"
                return CONFIGURING_THRESHOLDS
                
            elif threshold_type == "liquidity":
                query.edit_message_text(
                    "Please enter the minimum liquidity change percentage that should trigger an alert (e.g., 10):",
                    parse_mode=ParseMode.MARKDOWN
                )
                context.user_data["configuring"] = "liquidity_threshold"
                return CONFIGURING_THRESHOLDS
                
            elif threshold_type == "whale":
                query.edit_message_text(
                    "Please enter the minimum whale movement percentage that should trigger an alert (e.g., 3):",
                    parse_mode=ParseMode.MARKDOWN
                )
                context.user_data["configuring"] = "whale_threshold"
                return CONFIGURING_THRESHOLDS
                
            elif threshold_type == "back":
                # Return to main menu
                return alert_config_command(update, context)
        
        # Handle alert type configuration
        elif callback_data.startswith(f"{SETTINGS_PREFIX}type_"):
            # Parse alert type
            alert_type = callback_data.replace(f"{SETTINGS_PREFIX}type_", "")
            settings = db_user.alert_settings
            
            if alert_type == "price":
                # Toggle price alerts
                settings.notify_price_changes = not settings.notify_price_changes
            elif alert_type == "liquidity":
                # Toggle liquidity alerts
                settings.notify_liquidity_changes = not settings.notify_liquidity_changes
            elif alert_type == "ownership":
                # Toggle ownership alerts
                settings.notify_ownership_changes = not settings.notify_ownership_changes
            elif alert_type == "risk":
                # Toggle risk alerts
                settings.notify_risk_changes = not settings.notify_risk_changes
            elif alert_type == "whale":
                # Toggle whale alerts
                settings.notify_whale_movements = not settings.notify_whale_movements
            elif alert_type == "back":
                # Return to main menu
                return alert_config_command(update, context)
            
            # Save settings
            user_service.update_user(db_user)
            
            # Show updated menu
            return _show_alert_types_config(update, context, settings)
            
        # Handle quiet hours configuration
        elif callback_data.startswith(f"{SETTINGS_PREFIX}quiet_"):
            # Parse quiet hours setting
            setting = callback_data.replace(f"{SETTINGS_PREFIX}quiet_", "")
            
            if setting == "start":
                query.edit_message_text(
                    "Please enter the hour when quiet hours should start (0-23):",
                    parse_mode=ParseMode.MARKDOWN
                )
                context.user_data["configuring"] = "quiet_start"
                return CONFIGURING_QUIET_HOURS
                
            elif setting == "end":
                query.edit_message_text(
                    "Please enter the hour when quiet hours should end (0-23):",
                    parse_mode=ParseMode.MARKDOWN
                )
                context.user_data["configuring"] = "quiet_end"
                return CONFIGURING_QUIET_HOURS
                
            elif setting == "back":
                # Return to main menu
                return alert_config_command(update, context)
                
        # Handle delivery configuration
        elif callback_data.startswith(f"{SETTINGS_PREFIX}delivery_"):
            # Parse delivery setting
            setting = callback_data.replace(f"{SETTINGS_PREFIX}delivery_", "")
            settings = db_user.alert_settings
            
            if setting == "digest":
                # Toggle digest mode
                settings.daily_digest = not settings.daily_digest
                # Save settings
                user_service.update_user(db_user)
                # Show updated menu
                return _show_delivery_config(update, context, settings)
                
            elif setting == "severity":
                # Cycle through severity levels
                current = settings.minimum_severity
                if current == "low":
                    settings.minimum_severity = "medium"
                elif current == "medium":
                    settings.minimum_severity = "high"
                elif current == "high":
                    settings.minimum_severity = "critical"
                else:
                    settings.minimum_severity = "low"
                
                # Save settings
                user_service.update_user(db_user)
                # Show updated menu
                return _show_delivery_config(update, context, settings)
                
            elif setting == "back":
                # Return to main menu
                return alert_config_command(update, context)
        
        # Default - return to main menu
        return alert_config_command(update, context)
        
    except Exception as e:
        logger.error(f"Error in alert config button handler: {e}", exc_info=True)
        update.effective_message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )
        return ConversationHandler.END


def process_threshold_input(update: Update, context: CallbackContext) -> int:
    """Process user input for threshold configuration."""
    try:
        user_id = str(update.effective_user.id)
        input_text = update.message.text.strip()
        
        # Get user data
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            update.message.reply_text("User not found. Please try again.")
            return ConversationHandler.END
        
        # Get what we're configuring
        configuring = context.user_data.get("configuring", "")
        
        try:
            # Parse input as float
            value = float(input_text)
            
            # Validate input
            if value < 0:
                update.message.reply_text(
                    "Please enter a positive number."
                )
                return CONFIGURING_THRESHOLDS
            
            # Update settings
            if configuring == "price_threshold":
                db_user.alert_settings.price_change_threshold = value
            elif configuring == "liquidity_threshold":
                db_user.alert_settings.liquidity_change_threshold = value
            elif configuring == "whale_threshold":
                db_user.alert_settings.whale_movement_threshold = value
            
            # Save settings
            user_service.update_user(db_user)
            
            # Show confirmation
            update.message.reply_text(
                f"✅ Threshold updated successfully to {value}%."
            )
            
            # Return to thresholds menu
            return _show_threshold_config(update, context, db_user.alert_settings)
            
        except ValueError:
            update.message.reply_text(
                "Please enter a valid number."
            )
            return CONFIGURING_THRESHOLDS
        
    except Exception as e:
        logger.error(f"Error processing threshold input: {e}", exc_info=True)
        update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )
        return ConversationHandler.END


def process_quiet_hours_input(update: Update, context: CallbackContext) -> int:
    """Process user input for quiet hours configuration."""
    try:
        user_id = str(update.effective_user.id)
        input_text = update.message.text.strip()
        
        # Get user data
        db_user = user_service.get_user_by_telegram_id(user_id)
        if not db_user:
            update.message.reply_text("User not found. Please try again.")
            return ConversationHandler.END
        
        # Get what we're configuring
        configuring = context.user_data.get("configuring", "")
        
        try:
            # Parse input as integer
            value = int(input_text)
            
            # Validate input
            if value < 0 or value > 23:
                update.message.reply_text(
                    "Please enter a valid hour (0-23)."
                )
                return CONFIGURING_QUIET_HOURS
            
            # Update settings
            if configuring == "quiet_start":
                db_user.alert_settings.quiet_hours_start = value
            elif configuring == "quiet_end":
                db_user.alert_settings.quiet_hours_end = value
            
            # Save settings
            user_service.update_user(db_user)
            
            # Show confirmation
            update.message.reply_text(
                f"✅ Quiet hours updated successfully."
            )
            
            # Return to quiet hours menu
            return _show_quiet_hours_config(update, context, db_user.alert_settings)
            
        except ValueError:
            update.message.reply_text(
                "Please enter a valid hour (0-23)."
            )
            return CONFIGURING_QUIET_HOURS
        
    except Exception as e:
        logger.error(f"Error processing quiet hours input: {e}", exc_info=True)
        update.message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )
        return ConversationHandler.END


def cancel_config(update: Update, context: CallbackContext) -> int:
    """Cancel the configuration process."""
    update.message.reply_text(
        "Alert configuration cancelled. Your previous settings have been kept."
    )
    return ConversationHandler.END


# Helper functions for showing configuration menus

def _show_threshold_config(update: Update, context: CallbackContext, settings: AlertSettings) -> int:
    """Show threshold configuration menu."""
    message = (
        "*Alert Threshold Configuration*\n\n"
        f"Configure the minimum changes that will trigger alerts.\n\n"
        f"🔹 Price Change: {settings.price_change_threshold}%\n"
        f"🔹 Liquidity Change: {settings.liquidity_change_threshold}%\n"
        f"🔹 Whale Movement: {settings.whale_movement_threshold}%\n"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Price Threshold", 
                                callback_data=f"{SETTINGS_PREFIX}threshold_price")
        ],
        [
            InlineKeyboardButton("💧 Liquidity Threshold", 
                                callback_data=f"{SETTINGS_PREFIX}threshold_liquidity")
        ],
        [
            InlineKeyboardButton("🐋 Whale Movement Threshold", 
                                callback_data=f"{SETTINGS_PREFIX}threshold_whale")
        ],
        [
            InlineKeyboardButton("⬅️ Back", 
                                callback_data=f"{SETTINGS_PREFIX}threshold_back")
        ]
    ]
    
    if update.callback_query:
        update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return SELECTING_SETTING


def _show_alert_types_config(update: Update, context: CallbackContext, settings: AlertSettings) -> int:
    """Show alert types configuration menu."""
    # Create status emojis
    price_status = "✅" if settings.notify_price_changes else "❌"
    liquidity_status = "✅" if settings.notify_liquidity_changes else "❌"
    ownership_status = "✅" if settings.notify_ownership_changes else "❌"
    risk_status = "✅" if settings.notify_risk_changes else "❌"
    whale_status = "✅" if settings.notify_whale_movements else "❌"
    
    message = (
        "*Alert Types Configuration*\n\n"
        f"Choose which types of alerts you want to receive.\n\n"
        f"🔹 Price Changes: {price_status}\n"
        f"🔹 Liquidity Changes: {liquidity_status}\n"
        f"🔹 Ownership Changes: {ownership_status}\n"
        f"🔹 Risk Level Changes: {risk_status}\n"
        f"🔹 Whale Movements: {whale_status}\n"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(f"{price_status} Price Changes", 
                                callback_data=f"{SETTINGS_PREFIX}type_price")
        ],
        [
            InlineKeyboardButton(f"{liquidity_status} Liquidity Changes", 
                                callback_data=f"{SETTINGS_PREFIX}type_liquidity")
        ],
        [
            InlineKeyboardButton(f"{ownership_status} Ownership Changes", 
                                callback_data=f"{SETTINGS_PREFIX}type_ownership")
        ],
        [
            InlineKeyboardButton(f"{risk_status} Risk Level Changes", 
                                callback_data=f"{SETTINGS_PREFIX}type_risk")
        ],
        [
            InlineKeyboardButton(f"{whale_status} Whale Movements", 
                                callback_data=f"{SETTINGS_PREFIX}type_whale")
        ],
        [
            InlineKeyboardButton("⬅️ Back", 
                                callback_data=f"{SETTINGS_PREFIX}type_back")
        ]
    ]
    
    if update.callback_query:
        update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return SELECTING_SETTING


def _show_quiet_hours_config(update: Update, context: CallbackContext, settings: AlertSettings) -> int:
    """Show quiet hours configuration menu."""
    # Format hours
    start_hour = f"{settings.quiet_hours_start:02d}:00"
    end_hour = f"{settings.quiet_hours_end:02d}:00"
    
    message = (
        "*Quiet Hours Configuration*\n\n"
        f"Configure hours when you don't want to receive alerts.\n\n"
        f"🔹 Quiet Hours Start: {start_hour}\n"
        f"🔹 Quiet Hours End: {end_hour}\n"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🌙 Set Start Time", 
                                callback_data=f"{SETTINGS_PREFIX}quiet_start")
        ],
        [
            InlineKeyboardButton("🌅 Set End Time", 
                                callback_data=f"{SETTINGS_PREFIX}quiet_end")
        ],
        [
            InlineKeyboardButton("⬅️ Back", 
                                callback_data=f"{SETTINGS_PREFIX}quiet_back")
        ]
    ]
    
    if update.callback_query:
        update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return SELECTING_SETTING


def _show_delivery_config(update: Update, context: CallbackContext, settings: AlertSettings) -> int:
    """Show delivery preferences configuration menu."""
    # Get status indicators
    digest_status = "✅" if settings.daily_digest else "❌"
    
    message = (
        "*Alert Delivery Configuration*\n\n"
        f"Configure how you want to receive alerts.\n\n"
        f"🔹 Digest Mode: {digest_status}\n"
        f"🔹 Minimum Severity: {settings.minimum_severity.capitalize()}\n"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(f"{'✅' if settings.daily_digest else '❌'} Digest Mode", 
                                callback_data=f"{SETTINGS_PREFIX}delivery_digest")
        ],
        [
            InlineKeyboardButton(f"🚨 Minimum Severity: {settings.minimum_severity.capitalize()}", 
                                callback_data=f"{SETTINGS_PREFIX}delivery_severity")
        ],
        [
            InlineKeyboardButton("⬅️ Back", 
                                callback_data=f"{SETTINGS_PREFIX}delivery_back")
        ]
    ]
    
    if update.callback_query:
        update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return SELECTING_SETTING


def _format_settings_summary(settings: AlertSettings) -> str:
    """Format alert settings summary for display."""
    enabled_status = "✅ Enabled" if settings.enabled else "❌ Disabled"
    
    message = (
        f"*Alert Configuration*\n\n"
        f"Status: {enabled_status}\n\n"
        
        f"*Alert Thresholds:*\n"
        f"• Price Change: {settings.price_change_threshold}%\n"
        f"• Liquidity Change: {settings.liquidity_change_threshold}%\n"
        f"• Whale Movement: {settings.whale_movement_threshold}%\n\n"
        
        f"*Alert Types:*\n"
        f"• Price Changes: {'✅' if settings.notify_price_changes else '❌'}\n"
        f"• Liquidity Changes: {'✅' if settings.notify_liquidity_changes else '❌'}\n"
        f"• Ownership Changes: {'✅' if settings.notify_ownership_changes else '❌'}\n"
        f"• Risk Level Changes: {'✅' if settings.notify_risk_changes else '❌'}\n"
        f"• Whale Movements: {'✅' if settings.notify_whale_movements else '❌'}\n\n"
        
        f"*Delivery Settings:*\n"
        f"• Quiet Hours: {settings.quiet_hours_start:02d}:00 - {settings.quiet_hours_end:02d}:00\n"
        f"• Digest Mode: {'✅' if settings.daily_digest else '❌'}\n"
        f"• Minimum Severity: {settings.minimum_severity.capitalize()}\n\n"
        
        f"Select an option to configure:"
    )
    
    return message


# Get handlers for alert configuration
def get_alert_config_handlers() -> List:
    """Get handlers for alert configuration."""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler
    
    alert_config_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("alert_config", alert_config_command)],
        states={
            SELECTING_SETTING: [
                CallbackQueryHandler(alert_config_button_handler, pattern=f"^{SETTINGS_PREFIX}")
            ],
            CONFIGURING_THRESHOLDS: [
                MessageHandler(Filters.text & ~Filters.command, process_threshold_input)
            ],
            CONFIGURING_QUIET_HOURS: [
                MessageHandler(Filters.text & ~Filters.command, process_quiet_hours_input)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_config)]
    )
    
    return [alert_config_conv_handler] 