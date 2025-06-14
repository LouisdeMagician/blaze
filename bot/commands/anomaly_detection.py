"""
Anomaly detection commands for the Telegram bot.
"""
import logging
import json
from datetime import datetime
import time
from typing import Dict, List, Any, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters
)

from src.analysis.anomaly.anomaly_detector import anomaly_detector
from src.utils.format import format_number, format_percent, escape_markdown_v2
from src.utils.tg_helpers import send_message, send_typing_action

logger = logging.getLogger(__name__)

# Conversation states
SELECTING_METRIC, ENTERING_TIMEFRAME, VIEWING_RESULTS = range(3)

# Callback data patterns
METRIC_PREFIX = "anomaly_metric:"
TIMEFRAME_PREFIX = "anomaly_timeframe:"
BACK_TO_METRICS = "anomaly_back_metrics"
BACK_TO_MAIN = "anomaly_back_main"
VIEW_DETAILS = "anomaly_details:"


@send_typing_action
async def anomaly_command(update: Update, context: CallbackContext) -> int:
    """
    Handle the /anomaly command to start the anomaly detection flow.
    
    Args:
        update: Telegram update
        context: Callback context
        
    Returns:
        int: Conversation state
    """
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    logger.info(f"User {username} ({user_id}) started anomaly detection")
    
    # Get available metrics for anomaly detection
    available_metrics = {
        "price": "Token Price",
        "volume": "Trading Volume",
        "liquidity": "Liquidity",
        "holders": "Holder Count",
        "transactions": "Transaction Count",
        "whales": "Whale Activity"
    }
    
    # Build keyboard for metric selection
    keyboard = []
    row = []
    
    for i, (metric_key, metric_name) in enumerate(available_metrics.items()):
        callback_data = f"{METRIC_PREFIX}{metric_key}"
        row.append(InlineKeyboardButton(metric_name, callback_data=callback_data))
        
        # Two buttons per row
        if (i + 1) % 2 == 0 or i == len(available_metrics) - 1:
            keyboard.append(row)
            row = []
    
    # Add back button
    keyboard.append([InlineKeyboardButton("Cancel", callback_data=BACK_TO_MAIN)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send message
    message = (
        "🔍 *Anomaly Detection*\n\n"
        "Detect unusual patterns and anomalies in blockchain data\\.\n\n"
        "Please select a metric to analyze:"
    )
    
    await send_message(update, context, message, reply_markup=reply_markup)
    
    return SELECTING_METRIC


@send_typing_action
async def select_metric(update: Update, context: CallbackContext) -> int:
    """
    Handle metric selection for anomaly detection.
    
    Args:
        update: Telegram update
        context: Callback context
        
    Returns:
        int: Conversation state
    """
    query = update.callback_query
    await query.answer()
    
    # Extract selected metric
    data = query.data
    if not data.startswith(METRIC_PREFIX):
        return SELECTING_METRIC
    
    metric = data[len(METRIC_PREFIX):]
    
    # Store the selected metric
    context.user_data["anomaly_metric"] = metric
    
    # Build keyboard for timeframe selection
    timeframes = {
        "1h": "Last Hour",
        "24h": "Last 24 Hours",
        "7d": "Last 7 Days",
        "30d": "Last 30 Days"
    }
    
    keyboard = []
    row = []
    
    for i, (key, name) in enumerate(timeframes.items()):
        callback_data = f"{TIMEFRAME_PREFIX}{key}"
        row.append(InlineKeyboardButton(name, callback_data=callback_data))
        
        # Two buttons per row
        if (i + 1) % 2 == 0 or i == len(timeframes) - 1:
            keyboard.append(row)
            row = []
    
    # Add back button
    keyboard.append([InlineKeyboardButton("Back", callback_data=BACK_TO_METRICS)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get display name for metric
    metric_names = {
        "price": "Token Price",
        "volume": "Trading Volume",
        "liquidity": "Liquidity",
        "holders": "Holder Count",
        "transactions": "Transaction Count",
        "whales": "Whale Activity"
    }
    
    metric_display = metric_names.get(metric, metric)
    
    # Send message
    message = (
        f"🔍 *Anomaly Detection: {escape_markdown_v2(metric_display)}*\n\n"
        f"Please select a timeframe for the analysis:"
    )
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    
    return ENTERING_TIMEFRAME


@send_typing_action
async def select_timeframe(update: Update, context: CallbackContext) -> int:
    """
    Handle timeframe selection for anomaly detection.
    
    Args:
        update: Telegram update
        context: Callback context
        
    Returns:
        int: Conversation state
    """
    query = update.callback_query
    await query.answer()
    
    # Extract selected timeframe
    data = query.data
    if not data.startswith(TIMEFRAME_PREFIX):
        return ENTERING_TIMEFRAME
    
    timeframe = data[len(TIMEFRAME_PREFIX):]
    
    # Store the selected timeframe
    context.user_data["anomaly_timeframe"] = timeframe
    
    # Get metric and timeframe
    metric = context.user_data.get("anomaly_metric")
    
    # Calculate analysis key based on metric and timeframe
    analysis_key = f"{metric}_{timeframe}"
    
    # Get anomalies for the selected metric and timeframe
    try:
        # In a real implementation, you would have gathered data over time
        # For now, we'll simulate by generating some sample data
        anomaly_result = await get_anomalies_for_metric(analysis_key)
        
        # Store results
        context.user_data["anomaly_results"] = anomaly_result
        
        # Display results
        await display_anomaly_results(update, context)
        
        return VIEWING_RESULTS
        
    except Exception as e:
        logger.error(f"Error in anomaly detection: {e}", exc_info=True)
        
        message = (
            "❌ *Error*\n\n"
            "An error occurred while analyzing anomalies\\. Please try again later\\."
        )
        
        keyboard = [[InlineKeyboardButton("Back to Main", callback_data=BACK_TO_MAIN)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=message,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        
        return ConversationHandler.END


async def get_anomalies_for_metric(metric_key: str) -> Dict[str, Any]:
    """
    Get anomalies for a specific metric.
    
    Args:
        metric_key: Metric key
        
    Returns:
        Dict: Anomaly detection results
    """
    # Check if we have cached results
    cached = await anomaly_detector.get_anomalies(metric_key)
    
    # For testing/demo purposes - if no cached results, generate some sample data
    if cached.get("status") == "not_found" or not cached.get("anomalies"):
        # Generate some sample data
        now = time.time()
        
        # Simulate adding data points
        if "_1h" in metric_key:
            # Last hour - 60 data points (1 per minute)
            timestamps = [now - (60 - i) * 60 for i in range(60)]
            
            # Generate sample values with a few anomalies
            import numpy as np
            np.random.seed(int(now) % 1000)  # Semi-random seed
            
            values = list(np.random.normal(100, 5, 60))
            
            # Add a few anomalies
            anomaly_indices = [10, 40, 55]
            anomaly_values = [130, 70, 140]
            
            for idx, val in zip(anomaly_indices, anomaly_values):
                values[idx] = val
                
        elif "_24h" in metric_key:
            # Last 24 hours - 24 data points (1 per hour)
            timestamps = [now - (24 - i) * 3600 for i in range(24)]
            
            # Generate sample values
            import numpy as np
            np.random.seed(int(now) % 1000)
            
            values = list(np.random.normal(100, 8, 24))
            
            # Add anomalies
            anomaly_indices = [5, 18]
            anomaly_values = [140, 60]
            
            for idx, val in zip(anomaly_indices, anomaly_values):
                values[idx] = val
                
        else:
            # Default - 30 data points
            timestamps = [now - (30 - i) * 3600 for i in range(30)]
            
            import numpy as np
            np.random.seed(int(now) % 1000)
            
            values = list(np.random.normal(100, 10, 30))
            
            # Add anomalies
            anomaly_indices = [8, 22]
            anomaly_values = [150, 50]
            
            for idx, val in zip(anomaly_indices, anomaly_values):
                values[idx] = val
        
        # Add data points to anomaly detector
        data_points = list(zip(timestamps, values))
        await anomaly_detector.add_multiple_data_points(metric_key, data_points)
        
        # Run detection
        result = await anomaly_detector.detect_anomalies(metric_key)
        return result
    
    return cached


async def display_anomaly_results(update: Update, context: CallbackContext) -> None:
    """
    Display anomaly detection results.
    
    Args:
        update: Telegram update
        context: Callback context
    """
    query = update.callback_query
    
    # Get results
    results = context.user_data.get("anomaly_results", {})
    metric = context.user_data.get("anomaly_metric")
    timeframe = context.user_data.get("anomaly_timeframe")
    
    # Get metric display name
    metric_names = {
        "price": "Token Price",
        "volume": "Trading Volume",
        "liquidity": "Liquidity",
        "holders": "Holder Count",
        "transactions": "Transaction Count",
        "whales": "Whale Activity"
    }
    
    metric_display = metric_names.get(metric, metric)
    
    # Format timeframe
    timeframe_display = {
        "1h": "Last Hour",
        "24h": "Last 24 Hours",
        "7d": "Last 7 Days",
        "30d": "Last 30 Days"
    }.get(timeframe, timeframe)
    
    # Check if anomalies were found
    anomalies = results.get("anomalies", [])
    
    if not anomalies:
        message = (
            f"🔍 *Anomaly Detection Results*\n\n"
            f"Metric: {escape_markdown_v2(metric_display)}\n"
            f"Timeframe: {escape_markdown_v2(timeframe_display)}\n\n"
            f"No anomalies detected\\. The data appears to be within normal ranges\\."
        )
        
        keyboard = [
            [InlineKeyboardButton("Back to Metrics", callback_data=BACK_TO_METRICS)],
            [InlineKeyboardButton("Back to Main", callback_data=BACK_TO_MAIN)]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=message,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
        
        return
    
    # Sort anomalies by confidence score (descending)
    sorted_anomalies = sorted(
        anomalies, 
        key=lambda x: x["confidence_score"], 
        reverse=True
    )
    
    # Limit to top 5 anomalies
    top_anomalies = sorted_anomalies[:5]
    
    # Format the message
    message = (
        f"🚨 *Anomaly Detection Results*\n\n"
        f"Metric: {escape_markdown_v2(metric_display)}\n"
        f"Timeframe: {escape_markdown_v2(timeframe_display)}\n\n"
        f"Detected {len(anomalies)} anomalies\\. Top {len(top_anomalies)} shown below:\n\n"
    )
    
    # Add anomaly details
    for i, anomaly in enumerate(top_anomalies):
        timestamp = anomaly["timestamp"]
        value = anomaly["value"]
        confidence = anomaly["confidence_score"] * 100
        confidence_level = anomaly["confidence_level"]
        
        # Format timestamp
        dt = datetime.fromtimestamp(timestamp)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Format value
        if "price" in metric:
            value_str = f"${format_number(value)}"
        elif "percent" in metric:
            value_str = format_percent(value)
        else:
            value_str = format_number(value)
        
        # Format confidence level
        if confidence_level == "very high":
            confidence_emoji = "🔴"
        elif confidence_level == "high":
            confidence_emoji = "🟠"
        elif confidence_level == "medium":
            confidence_emoji = "🟡"
        else:
            confidence_emoji = "🟢"
        
        # Add to message
        message += (
            f"{i+1}\\. *{escape_markdown_v2(time_str)}*\n"
            f"   Value: {escape_markdown_v2(value_str)}\n"
            f"   Confidence: {confidence_emoji} {format_percent(confidence)} "
            f"\\({escape_markdown_v2(confidence_level)}\\)\n\n"
        )
    
    # Add note about anomaly detection
    message += (
        "*Note:* Anomalies represent unusual patterns in the data that "
        "deviate significantly from normal behavior\\. They may indicate "
        "important events or manipulative activities\\."
    )
    
    # Build keyboard
    keyboard = [
        [InlineKeyboardButton("Back to Metrics", callback_data=BACK_TO_METRICS)],
        [InlineKeyboardButton("Back to Main", callback_data=BACK_TO_MAIN)]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )


@send_typing_action
async def back_to_metrics(update: Update, context: CallbackContext) -> int:
    """
    Handle going back to metric selection.
    
    Args:
        update: Telegram update
        context: Callback context
        
    Returns:
        int: Conversation state
    """
    # Clear previous results
    if "anomaly_results" in context.user_data:
        del context.user_data["anomaly_results"]
    
    if "anomaly_timeframe" in context.user_data:
        del context.user_data["anomaly_timeframe"]
    
    # Go back to metric selection
    return await anomaly_command(update, context)


@send_typing_action
async def back_to_main(update: Update, context: CallbackContext) -> int:
    """
    Handle going back to main menu.
    
    Args:
        update: Telegram update
        context: Callback context
        
    Returns:
        int: End conversation
    """
    query = update.callback_query
    await query.answer()
    
    # Clear user data
    context.user_data.pop("anomaly_metric", None)
    context.user_data.pop("anomaly_timeframe", None)
    context.user_data.pop("anomaly_results", None)
    
    # Send message
    message = "Exited anomaly detection. Use /help to see available commands."
    
    await query.edit_message_text(text=message)
    
    return ConversationHandler.END


# Create conversation handler
anomaly_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("anomaly", anomaly_command)],
    states={
        SELECTING_METRIC: [
            CallbackQueryHandler(select_metric, pattern=f"^{METRIC_PREFIX}"),
            CallbackQueryHandler(back_to_main, pattern=f"^{BACK_TO_MAIN}$")
        ],
        ENTERING_TIMEFRAME: [
            CallbackQueryHandler(select_timeframe, pattern=f"^{TIMEFRAME_PREFIX}"),
            CallbackQueryHandler(back_to_metrics, pattern=f"^{BACK_TO_METRICS}$")
        ],
        VIEWING_RESULTS: [
            CallbackQueryHandler(back_to_metrics, pattern=f"^{BACK_TO_METRICS}$"),
            CallbackQueryHandler(back_to_main, pattern=f"^{BACK_TO_MAIN}$")
        ]
    },
    fallbacks=[CommandHandler("cancel", back_to_main)]
)