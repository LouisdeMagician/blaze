"""
Advanced analysis command for Telegram bot.
Provides access to advanced analysis features and visualization.
"""
import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode,
    ChatAction, InputMediaPhoto
)
from telegram.ext import (
    CallbackContext, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, Filters
)

from src.bot.message_templates import Emoji, Templates
from src.bot.keyboard_templates import KeyboardTemplates
from src.services.scanner import contract_scanner
from src.analysis.smart_money.whale_monitor import whale_monitor
from src.analysis.custom_analyzer import custom_analyzer
from src.analysis.visualization.advanced_charts import advanced_chart_generator
from src.utils.validators import validate_solana_address

logger = logging.getLogger(__name__)

# Conversation states
CHOOSING_ANALYSIS_TYPE = 1
ENTERING_TOKEN_ADDRESS = 2
SELECTING_MODULE = 3
SELECTING_COMPARISON_TOKEN = 4
CONFIGURING_SCENARIO = 5
CONFIRMING_ANALYSIS = 6
SHOWING_RESULTS = 7

# Callback data patterns
ANALYSIS_TYPE_PATTERN = "adv_analysis:type:{}"
TOKEN_ACTION_PATTERN = "adv_analysis:action:{}"
MODULE_SELECTION_PATTERN = "adv_analysis:module:{}"
COMPARISON_ACTION_PATTERN = "adv_analysis:compare:{}"
SCENARIO_ACTION_PATTERN = "adv_analysis:scenario:{}"
VISUALIZATION_PATTERN = "adv_analysis:viz:{}"

# User session data keys
SESSION_TOKEN_ADDRESS = "token_address"
SESSION_ANALYSIS_TYPE = "analysis_type"
SESSION_SELECTED_MODULES = "selected_modules"
SESSION_COMPARISON_TOKENS = "comparison_tokens"
SESSION_SCENARIOS = "scenarios"
SESSION_CURRENT_RESULTS = "current_results"

def command_advanced_analysis(update: Update, context: CallbackContext) -> int:
    """
    Handle the /advanced_analysis command to start the advanced analysis flow.
    """
    try:
        # Initialize user session data
        context.user_data.clear()
        
        # Check if the command has an address argument
        if context.args and context.args[0]:
            token_address = context.args[0].strip()
            
            # Validate address format
            if validate_solana_address(token_address):
                # Store token address
                context.user_data[SESSION_TOKEN_ADDRESS] = token_address
                
                # Show analysis type selection
                return show_analysis_type_selection(update, context)
            else:
                # Invalid address format
                update.message.reply_text(
                    f"{Emoji.ERROR} Invalid token address format. Please provide a valid Solana address.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
        
        # No address provided, show welcome message
        update.message.reply_text(
            f"{Emoji.CHART} *Advanced Analysis*\n\n"
            f"This feature provides detailed analysis with advanced visualization options.\n\n"
            f"Please select the type of analysis you want to perform:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Custom Analysis", callback_data=ANALYSIS_TYPE_PATTERN.format("custom")),
                    InlineKeyboardButton("Whale Monitoring", callback_data=ANALYSIS_TYPE_PATTERN.format("whale"))
                ],
                [
                    InlineKeyboardButton("Token Comparison", callback_data=ANALYSIS_TYPE_PATTERN.format("comparison")),
                    InlineKeyboardButton("Scenario Analysis", callback_data=ANALYSIS_TYPE_PATTERN.format("scenario"))
                ],
                [
                    InlineKeyboardButton("Cancel", callback_data=TOKEN_ACTION_PATTERN.format("cancel"))
                ]
            ])
        )
        
        return CHOOSING_ANALYSIS_TYPE
        
    except Exception as e:
        logger.error(f"Error in advanced_analysis command: {e}", exc_info=True)
        update.message.reply_text(
            f"{Emoji.ERROR} An error occurred while processing your request. Please try again later."
        )
        return ConversationHandler.END

def show_analysis_type_selection(update: Update, context: CallbackContext) -> int:
    """
    Show analysis type selection for a specific token address.
    """
    token_address = context.user_data.get(SESSION_TOKEN_ADDRESS)
    
    # Get basic token info
    update.message.chat.send_action(action=ChatAction.TYPING)
    token_info = contract_scanner.get_token_info(token_address)
    
    token_name = "Unknown Token"
    token_symbol = "???"
    
    if token_info and token_info.get("success"):
        token_data = token_info.get("token_info", {})
        token_name = token_data.get("name", "Unknown Token")
        token_symbol = token_data.get("symbol", "???")
    
    # Show message with token info and analysis types
    message = update.message.reply_text(
        f"{Emoji.CHART} *Advanced Analysis for {token_name} ({token_symbol})*\n\n"
        f"Token Address: `{token_address}`\n\n"
        f"Please select the type of analysis you want to perform:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Custom Analysis", callback_data=ANALYSIS_TYPE_PATTERN.format("custom")),
                InlineKeyboardButton("Whale Monitoring", callback_data=ANALYSIS_TYPE_PATTERN.format("whale"))
            ],
            [
                InlineKeyboardButton("Token Comparison", callback_data=ANALYSIS_TYPE_PATTERN.format("comparison")),
                InlineKeyboardButton("Scenario Analysis", callback_data=ANALYSIS_TYPE_PATTERN.format("scenario"))
            ],
            [
                InlineKeyboardButton("Cancel", callback_data=TOKEN_ACTION_PATTERN.format("cancel"))
            ]
        ])
    )
    
    return CHOOSING_ANALYSIS_TYPE

def analysis_type_callback(update: Update, context: CallbackContext) -> int:
    """
    Handle analysis type selection callback.
    """
    query = update.callback_query
    query.answer()
    
    # Extract the selected analysis type
    analysis_type = query.data.split(":")[-1]
    
    # Store analysis type
    context.user_data[SESSION_ANALYSIS_TYPE] = analysis_type
    
    # Check if we already have a token address
    if SESSION_TOKEN_ADDRESS not in context.user_data:
        # No token address, ask for it
        query.edit_message_text(
            f"{Emoji.SEARCH} *Enter Token Address*\n\n"
            f"Please enter the token address you want to analyze:",
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTERING_TOKEN_ADDRESS
    
    # We have a token address, continue with the flow
    if analysis_type == "custom":
        return show_module_selection(update, context)
    elif analysis_type == "whale":
        return show_whale_analysis(update, context)
    elif analysis_type == "comparison":
        return start_comparison_analysis(update, context)
    elif analysis_type == "scenario":
        return start_scenario_analysis(update, context)
    else:
        # Unknown analysis type
        query.edit_message_text(
            f"{Emoji.ERROR} Unknown analysis type: {analysis_type}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

def token_address_input(update: Update, context: CallbackContext) -> int:
    """
    Handle token address input.
    """
    token_address = update.message.text.strip()
    
    # Validate address format
    if not validate_solana_address(token_address):
        update.message.reply_text(
            f"{Emoji.ERROR} Invalid token address format. Please provide a valid Solana address.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ENTERING_TOKEN_ADDRESS
    
    # Store token address
    context.user_data[SESSION_TOKEN_ADDRESS] = token_address
    
    # Continue with the flow based on analysis type
    analysis_type = context.user_data.get(SESSION_ANALYSIS_TYPE)
    
    if analysis_type == "custom":
        return show_module_selection(update, context)
    elif analysis_type == "whale":
        return show_whale_analysis(update, context)
    elif analysis_type == "comparison":
        return start_comparison_analysis(update, context)
    elif analysis_type == "scenario":
        return start_scenario_analysis(update, context)
    else:
        # Unknown analysis type
        update.message.reply_text(
            f"{Emoji.ERROR} Unknown analysis type: {analysis_type}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

# Custom Analysis Implementation

def show_module_selection(update: Update, context: CallbackContext) -> int:
    """
    Show module selection for custom analysis.
    """
    query = update.callback_query
    
    # Initialize selected modules
    if SESSION_SELECTED_MODULES not in context.user_data:
        context.user_data[SESSION_SELECTED_MODULES] = []
    
    # Available modules
    modules = [
        ("token", "Token Info"),
        ("liquidity", "Liquidity Analysis"),
        ("risk", "Risk Analysis"),
        ("smart_money", "Smart Money Analysis"),
        ("whale", "Whale Activity"),
        ("volume", "Volume Analysis"),
        ("fees", "Fee Analysis")
    ]
    
    # Create keyboard
    keyboard = []
    for module_id, module_name in modules:
        is_selected = module_id in context.user_data[SESSION_SELECTED_MODULES]
        status = "✅" if is_selected else ""
        keyboard.append([
            InlineKeyboardButton(f"{module_name} {status}", 
                               callback_data=MODULE_SELECTION_PATTERN.format(module_id))
        ])
    
    # Add confirmation and cancel buttons
    keyboard.append([
        InlineKeyboardButton("Run Analysis", callback_data=TOKEN_ACTION_PATTERN.format("run_analysis")),
        InlineKeyboardButton("Cancel", callback_data=TOKEN_ACTION_PATTERN.format("cancel"))
    ])
    
    # Show selection message
    token_address = context.user_data.get(SESSION_TOKEN_ADDRESS)
    
    message = (
        f"{Emoji.CHART} *Custom Analysis Configuration*\n\n"
        f"Token: `{token_address}`\n\n"
        f"Select the analysis modules you want to include:"
    )
    
    if query:
        query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    return SELECTING_MODULE

def module_selection_callback(update: Update, context: CallbackContext) -> int:
    """
    Handle module selection callback.
    """
    query = update.callback_query
    query.answer()
    
    # Extract selected module
    module_id = query.data.split(":")[-1]
    
    # Toggle module selection
    selected_modules = context.user_data.get(SESSION_SELECTED_MODULES, [])
    
    if module_id in selected_modules:
        selected_modules.remove(module_id)
    else:
        selected_modules.append(module_id)
    
    context.user_data[SESSION_SELECTED_MODULES] = selected_modules
    
    # Show updated module selection
    return show_module_selection(update, context)

def run_custom_analysis(update: Update, context: CallbackContext) -> int:
    """
    Run custom analysis with selected modules.
    """
    query = update.callback_query
    query.answer()
    
    # Get token address and selected modules
    token_address = context.user_data.get(SESSION_TOKEN_ADDRESS)
    selected_modules = context.user_data.get(SESSION_SELECTED_MODULES, [])
    
    # Show processing message
    query.edit_message_text(
        f"{Emoji.SEARCH} *Running Custom Analysis*\n\n"
        f"Token: `{token_address}`\n"
        f"Selected Modules: {', '.join(selected_modules)}\n\n"
        f"Please wait, this analysis may take some time...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Run the analysis
    try:
        result = custom_analyzer.run_custom_analysis(
            token_address=token_address,
            analysis_modules=selected_modules
        )
        
        # Store results for visualizations
        context.user_data[SESSION_CURRENT_RESULTS] = result
        
        # Format result message
        summary = result.get("summary", {})
        
        # Create summary message
        risk_score = summary.get("risk_score", 0)
        risk_emoji = "🟢" if risk_score < 3 else "🟡" if risk_score < 7 else "🔴"
        
        token_info = result.get("token_info", {})
        token_name = token_info.get("name", "Unknown Token")
        token_symbol = token_info.get("symbol", "???")
        
        message = (
            f"{Emoji.CHART} *Custom Analysis Results*\n\n"
            f"*{token_name} ({token_symbol})*\n"
            f"Address: `{token_address}`\n\n"
            f"*Risk Score:* {risk_score}/10 {risk_emoji}\n\n"
        )
        
        # Add highlights
        if summary.get("highlights"):
            message += "*Highlights:*\n"
            for highlight in summary["highlights"]:
                message += f"• {highlight}\n"
            message += "\n"
        
        # Add warnings
        if summary.get("warnings"):
            message += "*Warnings:*\n"
            for warning in summary["warnings"]:
                message += f"• {warning}\n"
            message += "\n"
        
        # Add opportunities
        if summary.get("opportunities"):
            message += "*Opportunities:*\n"
            for opportunity in summary["opportunities"]:
                message += f"• {opportunity}\n"
            message += "\n"
        
        # Add visualization buttons
        keyboard = []
        available_visualizations = []
        
        if "risk" in selected_modules:
            available_visualizations.append(("risk", "Risk Analysis Chart"))
        
        if "whale" in selected_modules:
            available_visualizations.append(("whale", "Whale Activity Chart"))
        
        if len(selected_modules) >= 2:
            available_visualizations.append(("metrics", "Metrics Comparison"))
        
        # Add buttons for visualizations
        for viz_id, viz_name in available_visualizations:
            keyboard.append([
                InlineKeyboardButton(viz_name, callback_data=VISUALIZATION_PATTERN.format(viz_id))
            ])
        
        # Add done button
        keyboard.append([
            InlineKeyboardButton("Done", callback_data=TOKEN_ACTION_PATTERN.format("done"))
        ])
        
        # Send result message
        query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SHOWING_RESULTS
        
    except Exception as e:
        logger.error(f"Error running custom analysis: {e}", exc_info=True)
        query.edit_message_text(
            f"{Emoji.ERROR} *Analysis Error*\n\n"
            f"An error occurred while analyzing the token: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

# Whale Monitoring Implementation

def show_whale_analysis(update: Update, context: CallbackContext) -> int:
    """
    Show whale activity analysis.
    """
    query = update.callback_query
    
    # Get token address
    token_address = context.user_data.get(SESSION_TOKEN_ADDRESS)
    
    # Show processing message
    processing_message = (
        f"{Emoji.SEARCH} *Analyzing Whale Activity*\n\n"
        f"Token: `{token_address}`\n\n"
        f"Please wait, fetching whale transaction data..."
    )
    
    if query:
        query.edit_message_text(
            processing_message,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        update.message.reply_text(
            processing_message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Run whale activity analysis
    try:
        whale_data = whale_monitor.get_token_whale_activity(token_address)
        
        # Store results for visualizations
        context.user_data[SESSION_CURRENT_RESULTS] = whale_data
        
        # Get token info
        token_name = whale_data.get("token_name", "Unknown Token")
        token_symbol = whale_data.get("token_symbol", "???")
        
        # Format result message
        transaction_count = whale_data.get("transaction_count", 0)
        total_volume = whale_data.get("total_volume_usd", 0)
        buy_pressure = whale_data.get("buy_pressure", 0)
        sell_pressure = whale_data.get("sell_pressure", 0)
        smart_money_percentage = whale_data.get("smart_money_percentage", 0)
        
        # Determine market sentiment
        sentiment = "Neutral"
        sentiment_emoji = "↔️"
        if buy_pressure > 65:
            sentiment = "Bullish"
            sentiment_emoji = "🟢"
        elif sell_pressure > 65:
            sentiment = "Bearish"
            sentiment_emoji = "🔴"
        
        message = (
            f"{Emoji.MONEY} *Whale Activity Analysis*\n\n"
            f"*{token_name} ({token_symbol})*\n"
            f"Address: `{token_address}`\n\n"
            f"*Transaction Count:* {transaction_count}\n"
            f"*Total Volume:* ${total_volume:,.2f}\n"
            f"*Buy Pressure:* {buy_pressure:.1f}%\n"
            f"*Sell Pressure:* {sell_pressure:.1f}%\n"
            f"*Smart Money Involvement:* {smart_money_percentage:.1f}%\n"
            f"*Market Sentiment:* {sentiment} {sentiment_emoji}\n\n"
        )
        
        # Add recent transactions if available
        recent_transactions = whale_data.get("recent_transactions", [])
        if recent_transactions:
            message += "*Recent Transactions:*\n"
            for i, tx in enumerate(recent_transactions[:5]):  # Show only top 5
                direction = tx.get("direction", "neutral").capitalize()
                amount = tx.get("amount_usd", 0)
                is_smart = "👑 " if tx.get("is_smart_money", False) else ""
                message += f"{i+1}. {is_smart}{direction} ${amount:,.2f}\n"
        
        # Add visualization buttons
        keyboard = [
            [InlineKeyboardButton("Whale Activity Chart", callback_data=VISUALIZATION_PATTERN.format("whale"))],
            [InlineKeyboardButton("Done", callback_data=TOKEN_ACTION_PATTERN.format("done"))]
        ]
        
        # Send result message
        if query:
            query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        return SHOWING_RESULTS
        
    except Exception as e:
        logger.error(f"Error analyzing whale activity: {e}", exc_info=True)
        error_message = (
            f"{Emoji.ERROR} *Analysis Error*\n\n"
            f"An error occurred while analyzing whale activity: {str(e)}"
        )
        
        if query:
            query.edit_message_text(
                error_message,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            update.message.reply_text(
                error_message,
                parse_mode=ParseMode.MARKDOWN
            )
        
        return ConversationHandler.END

# Visualization Handlers

def handle_visualization_request(update: Update, context: CallbackContext) -> int:
    """
    Handle visualization request callback.
    """
    query = update.callback_query
    query.answer()
    
    # Extract the visualization type
    viz_type = query.data.split(":")[-1]
    
    # Show generating message
    query.message.reply_text(
        f"{Emoji.CHART} Generating visualization...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Get current results
    results = context.user_data.get(SESSION_CURRENT_RESULTS, {})
    token_address = context.user_data.get(SESSION_TOKEN_ADDRESS)
    
    try:
        # Generate visualization based on type
        if viz_type == "risk":
            # Generate risk analysis chart
            chart_buffer = advanced_chart_generator.generate_risk_analysis_chart(
                token_address, results.get("modules", {}).get("risk", {})
            )
            
            # Send the chart
            query.message.reply_photo(
                photo=chart_buffer,
                caption=f"Risk Analysis Chart for {results.get('token_info', {}).get('symbol', token_address[:8])}",
                parse_mode=ParseMode.MARKDOWN
            )
            
        elif viz_type == "whale":
            # Generate whale activity chart
            whale_data = results
            if context.user_data.get(SESSION_ANALYSIS_TYPE) == "custom":
                whale_data = results.get("modules", {}).get("whale", {})
            
            recent_transactions = whale_data.get("recent_transactions", [])
            
            chart_buffer = advanced_chart_generator.generate_whale_activity_chart(
                f"Whale Activity: {whale_data.get('token_symbol', token_address[:8])}",
                recent_transactions
            )
            
            # Send the chart
            query.message.reply_photo(
                photo=chart_buffer,
                caption=f"Whale Activity Chart for {whale_data.get('token_symbol', token_address[:8])}",
                parse_mode=ParseMode.MARKDOWN
            )
            
        elif viz_type == "metrics":
            # Generate metrics comparison chart for custom analysis
            selected_modules = context.user_data.get(SESSION_SELECTED_MODULES, [])
            
            # Prepare metrics data
            metrics_data = {}
            
            # Define time series data (placeholders for demo)
            current_time = datetime.now()
            for module in selected_modules:
                if module in ["liquidity", "volume", "risk"]:
                    # Create example time series for this module
                    data_points = []
                    for i in range(10):
                        # Example value with some randomness
                        value = 50 + (i * 5) + (hash(module + str(i)) % 20)
                        data_points.append((
                            current_time - timedelta(days=9-i),
                            value
                        ))
                    metrics_data[module.capitalize()] = data_points
            
            chart_buffer = advanced_chart_generator.generate_multi_metric_chart(
                f"Metrics Comparison: {results.get('token_info', {}).get('symbol', token_address[:8])}",
                metrics_data
            )
            
            # Send the chart
            query.message.reply_photo(
                photo=chart_buffer,
                caption=f"Metrics Comparison for {results.get('token_info', {}).get('symbol', token_address[:8])}",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return SHOWING_RESULTS
            
    except Exception as e:
        logger.error(f"Error generating visualization: {e}", exc_info=True)
        query.message.reply_text(
            f"{Emoji.ERROR} Error generating visualization: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return SHOWING_RESULTS

# Token Comparison (Placeholder)

def start_comparison_analysis(update: Update, context: CallbackContext) -> int:
    """
    Start token comparison analysis flow.
    """
    query = update.callback_query
    
    # Simple placeholder response
    message = (
        f"{Emoji.INFO} Token comparison analysis is not yet implemented in this version.\n\n"
        f"This feature will allow comparing multiple tokens side by side."
    )
    
    if query:
        query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

# Scenario Analysis (Placeholder)

def start_scenario_analysis(update: Update, context: CallbackContext) -> int:
    """
    Start scenario analysis flow.
    """
    query = update.callback_query
    
    # Simple placeholder response
    message = (
        f"{Emoji.INFO} Scenario analysis is not yet implemented in this version.\n\n"
        f"This feature will allow simulating different market conditions."
    )
    
    if query:
        query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

# Common Handlers

def cancel_command(update: Update, context: CallbackContext) -> int:
    """
    Cancel the conversation.
    """
    query = update.callback_query
    
    if query:
        query.answer()
        query.edit_message_text(
            f"{Emoji.INFO} Advanced analysis canceled.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        update.message.reply_text(
            f"{Emoji.INFO} Advanced analysis canceled.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

def done_command(update: Update, context: CallbackContext) -> int:
    """
    End the conversation with success.
    """
    query = update.callback_query
    query.answer()
    
    query.edit_message_text(
        f"{Emoji.SUCCESS} Advanced analysis completed.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ConversationHandler.END

def get_advanced_analysis_handler():
    """
    Get the conversation handler for advanced analysis.
    """
    return ConversationHandler(
        entry_points=[CommandHandler("advanced_analysis", command_advanced_analysis)],
        states={
            CHOOSING_ANALYSIS_TYPE: [
                CallbackQueryHandler(analysis_type_callback, pattern=f"^{ANALYSIS_TYPE_PATTERN.format('.*')}$"),
                CallbackQueryHandler(cancel_command, pattern=f"^{TOKEN_ACTION_PATTERN.format('cancel')}$")
            ],
            ENTERING_TOKEN_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command, token_address_input)
            ],
            SELECTING_MODULE: [
                CallbackQueryHandler(module_selection_callback, pattern=f"^{MODULE_SELECTION_PATTERN.format('.*')}$"),
                CallbackQueryHandler(run_custom_analysis, pattern=f"^{TOKEN_ACTION_PATTERN.format('run_analysis')}$"),
                CallbackQueryHandler(cancel_command, pattern=f"^{TOKEN_ACTION_PATTERN.format('cancel')}$")
            ],
            SHOWING_RESULTS: [
                CallbackQueryHandler(handle_visualization_request, pattern=f"^{VISUALIZATION_PATTERN.format('.*')}$"),
                CallbackQueryHandler(done_command, pattern=f"^{TOKEN_ACTION_PATTERN.format('done')}$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CallbackQueryHandler(cancel_command, pattern=f"^{TOKEN_ACTION_PATTERN.format('cancel')}$")
        ],
        name="advanced_analysis",
        persistent=False
    ) 