"""
Command suggestion system for Telegram bot.
Provides context-aware command suggestions and auto-correction.
"""
import logging
import re
from difflib import get_close_matches
from typing import List, Dict, Any, Optional, Tuple

from src.bot.message_templates import Emoji

logger = logging.getLogger(__name__)

# Main commands with descriptions
COMMANDS = {
    "scan": "Basic token scan",
    "enhanced_scan": "Detailed security analysis",
    "advancedscan": "Interactive token scanning",
    "chart": "Generate token charts",
    "watchlist": "Manage your watchlist",
    "alerts": "Configure alerts",
    "help": "Show all commands",
    "start": "Start the bot",
}

# Command aliases (mapping alternative names to main commands)
COMMAND_ALIASES = {
    "analyse": "scan",
    "analyze": "scan",
    "check": "scan",
    "security": "enhanced_scan",
    "deep": "enhanced_scan",
    "interactive": "advancedscan",
    "graphs": "chart",
    "charts": "chart",
    "visualize": "chart",
    "favorite": "watchlist",
    "favourites": "watchlist",
    "favorites": "watchlist",
    "monitor": "alerts",
    "notify": "alerts",
    "notification": "alerts",
    "info": "help",
    "commands": "help",
    "begin": "start",
    "hello": "start",
}

# Command categories
COMMAND_CATEGORIES = {
    "scanning": ["scan", "enhanced_scan", "advancedscan"],
    "visualization": ["chart"],
    "monitoring": ["watchlist", "alerts"],
    "help": ["help", "start"],
}

# Common tasks and associated commands
COMMON_TASKS = {
    "check token security": "enhanced_scan",
    "analyze contract": "scan",
    "view price chart": "chart",
    "track token": "watchlist",
    "get alerts": "alerts",
    "see commands": "help",
}

class SuggestionSystem:
    """Command suggestion system for Telegram bot"""
    
    @staticmethod
    def suggest_command(user_input: str) -> Optional[Tuple[str, str]]:
        """
        Suggest a command based on user input.
        
        Args:
            user_input: User's message text
            
        Returns:
            Tuple of (command, description) or None if no suggestion
        """
        # Clean up user input
        cleaned_input = user_input.lower().strip()
        
        # Check for direct command matches without the slash
        for cmd, desc in COMMANDS.items():
            if cleaned_input == cmd:
                return f"/{cmd}", desc
        
        # Check for alias matches
        for alias, cmd in COMMAND_ALIASES.items():
            if cleaned_input == alias:
                return f"/{cmd}", COMMANDS[cmd]
        
        # Check for task-related keywords
        for task, cmd in COMMON_TASKS.items():
            if task.lower() in cleaned_input:
                return f"/{cmd}", COMMANDS[cmd]
        
        # Look for token addresses
        if re.search(r'[1-9A-HJ-NP-Za-km-z]{32,44}', cleaned_input):
            # If message contains what looks like a Solana address
            return "/scan", COMMANDS["scan"]
        
        # Check for close matches to commands using fuzzy matching
        possible_commands = list(COMMANDS.keys()) + list(COMMAND_ALIASES.keys())
        words = cleaned_input.split()
        
        for word in words:
            if len(word) > 3:  # Only consider words with more than 3 characters
                matches = get_close_matches(word, possible_commands, n=1, cutoff=0.7)
                if matches:
                    match = matches[0]
                    if match in COMMAND_ALIASES:
                        cmd = COMMAND_ALIASES[match]
                    else:
                        cmd = match
                    return f"/{cmd}", COMMANDS[cmd]
        
        return None
    
    @staticmethod
    def get_related_commands(command: str) -> List[Tuple[str, str]]:
        """
        Get related commands for the current command.
        
        Args:
            command: Current command (without slash)
            
        Returns:
            List of (command, description) tuples
        """
        related = []
        
        # Find the category of the current command
        category = None
        for cat, cmds in COMMAND_CATEGORIES.items():
            if command in cmds:
                category = cat
                break
        
        if category:
            # Suggest other commands in the same category
            for cmd in COMMAND_CATEGORIES[category]:
                if cmd != command:
                    related.append((f"/{cmd}", COMMANDS[cmd]))
        
        # Add common follow-up commands based on current command
        if command == "scan":
            related.append(("/enhanced_scan", COMMANDS["enhanced_scan"]))
            related.append(("/chart", COMMANDS["chart"]))
        elif command == "enhanced_scan":
            related.append(("/chart", COMMANDS["chart"]))
            related.append(("/watchlist", COMMANDS["watchlist"]))
        elif command == "chart":
            related.append(("/scan", COMMANDS["scan"]))
            related.append(("/watchlist", COMMANDS["watchlist"]))
        
        return related
    
    @staticmethod
    def format_suggestion_message(suggestion: Tuple[str, str], related: List[Tuple[str, str]] = None) -> str:
        """
        Format a suggestion message.
        
        Args:
            suggestion: Tuple of (command, description)
            related: Optional list of related commands
            
        Returns:
            Formatted message text
        """
        cmd, desc = suggestion
        
        message = f"{Emoji.INFO} Did you mean to use *{cmd}*? ({desc})"
        
        if related:
            message += "\n\n*Related commands:*"
            for rel_cmd, rel_desc in related[:3]:  # Limit to 3 related commands
                message += f"\n• {rel_cmd} - {rel_desc}"
        
        return message

# Singleton instance
suggestion_system = SuggestionSystem()

def get_suggestion_handler():
    from telegram.ext import MessageHandler, Filters
    def handle_text(update, context):
        # Use the suggestion system to suggest commands
        user_message = update.message.text
        suggestion = suggestion_system.suggest_command(user_message)
        if suggestion:
            command, description = suggestion
            related = suggestion_system.get_related_commands(command[1:])
            message = suggestion_system.format_suggestion_message(suggestion, related)
            update.message.reply_text(message, parse_mode='Markdown')
    return MessageHandler(Filters.text & ~Filters.command, handle_text) 