"""
Message templates for Telegram bot.
Provides standardized message formatting and templates for consistent UX.
"""
from typing import Dict, List, Any, Optional, Union, Tuple
import emoji

# Emoji constants
class Emoji:
    """Emoji constants for consistent usage"""
    FIRE = "🔥"
    ROCKET = "🚀"
    WARNING = "⚠️"
    ERROR = "❌"
    INFO = "ℹ️"
    SUCCESS = "✅"
    SEARCH = "🔍"
    CHART = "📊"
    MONEY = "💰"
    LOCK = "🔒"
    UNLOCK = "🔓"
    STAR = "⭐"
    PREMIUM = "💎"
    CLOCK = "⏱️"
    SHIELD = "🛡️"
    ALERT = "🚨"
    
    # Risk level indicators
    RISK_LOW = "🟢"
    RISK_MEDIUM = "🟡"
    RISK_HIGH = "🔴"
    RISK_CRITICAL = "⚠️"
    RISK_UNKNOWN = "❓"
    
    # Navigation
    BACK = "◀️"
    NEXT = "▶️"
    FIRST = "⏮️"
    LAST = "⏭️"
    
    # Categories
    TOKEN = "🪙"
    CONTRACT = "📝"
    LIQUIDITY = "💧"
    OWNERSHIP = "👑"
    TRADING = "📈"
    SOCIAL = "👥"
    
    @staticmethod
    def for_risk_level(risk_level: str) -> str:
        """Get emoji for risk level"""
        risk_level = risk_level.lower()
        if risk_level == "low":
            return Emoji.RISK_LOW
        elif risk_level == "medium":
            return Emoji.RISK_MEDIUM
        elif risk_level == "high":
            return Emoji.RISK_HIGH
        elif risk_level == "critical":
            return Emoji.RISK_CRITICAL
        else:
            return Emoji.RISK_UNKNOWN

# Message Templates
class Templates:
    """Message templates for consistent UI"""
    
    # Updated welcome with new menu-driven workflow
    WELCOME = f"""{Emoji.FIRE} *Welcome to Blaze Analyst!* {Emoji.FIRE}

I'm your Solana token-analysis assistant. Use the menu buttons below for the most common actions:

{Emoji.SEARCH} *Quick Scan*  – rapid basic metrics
{Emoji.SEARCH} *Deep Scan*   – full multi-module analysis
{Emoji.CHART} *Generate Chart*  – price chart & history
{Emoji.TOKEN} *Token Preview*  – rich preview card
{Emoji.SHIELD} *Advanced Analysis*  – advanced on-chain insights

Or use slash commands:
• `/scan <mint>` – quick scan
• `/scandeep <mint>` – deep scan
• `/chart <mint>` – chart image
• `/preview <mint>` – preview card
• `/help` – full help

What would you like to do today?"""

    # Help message
    HELP = f"""*Blaze Analyst Commands* {Emoji.INFO}

{Emoji.SEARCH} `/scan <mint>` – Quick token scan (basic metrics)
{Emoji.SEARCH} `/scandeep <mint>` – Deep scan (all analyzers)
{Emoji.CHART} `/chart <mint>` – Price chart image
{Emoji.TOKEN} `/preview <mint>` – Token preview card
{Emoji.INFO} `/help` – This help message
{Emoji.ERROR} `/stop` – Shut down bot (owner only)

Most users can simply press the menu buttons after `/start`.
"""

    # Scan in progress
    SCAN_IN_PROGRESS = f"""{Emoji.SEARCH} *Scanning token...*

Please wait while I analyze the token. This may take a few moments."""

    # Invalid address
    INVALID_ADDRESS = f"""{Emoji.ERROR} *Invalid Address*

The address you provided is not a valid Solana address. Please check and try again.

Example: Use `/scan TokenAddress123`"""

    # Scan failed
    SCAN_FAILED = f"""{Emoji.ERROR} *Scan Failed*

I couldn't complete the scan. {{error_message}}

Please try again later or try a different token address."""

    # Premium required
    PREMIUM_REQUIRED = f"""{Emoji.PREMIUM} *Premium Feature*

This feature requires a premium subscription.

Upgrade to premium to access:
• Deep and comprehensive scans
• More watchlist slots
• Advanced alert configuration
• Priority processing"""

    @staticmethod
    def format_token_scan_result(analyzer_result: Dict[str, Any], contract_scan_result: Any, token_address: str) -> str:
        """Format token scan results from both the real-data analyzer and contract scan."""
        # Analyzer summary
        summary = analyzer_result.get("summary", "No summary available.")
        metrics = analyzer_result.get("metrics", {})
        risk_factors = analyzer_result.get("risk_factors", [])
        recommendations = analyzer_result.get("recommendations", [])
        risk_level = metrics.get("risk_level", "unknown").lower()
        risk_emoji = Emoji.for_risk_level(risk_level)
        
        result = f"*Token Scan Results*\n\n"
        result += f"*Address:* `{token_address}`\n"
        result += f"*Risk Level:* {risk_level.upper()} {risk_emoji}\n"
        if summary:
            result += f"\n{summary}\n"
        if risk_factors:
            result += "\n*Risk Factors:*\n"
            for rf in risk_factors:
                desc = rf["description"] if isinstance(rf, dict) and "description" in rf else str(rf)
                result += f"• {desc}\n"
        if metrics:
            result += "\n*Token Details:*\n"
            for k, v in metrics.items():
                if k != "risk_level":
                    result += f"• {k.replace('_', ' ').title()}: {v}\n"
        if recommendations:
            result += "\n*Recommendations:*\n"
            for rec in recommendations:
                if isinstance(rec, dict):
                    result += f"• {rec.get('text', str(rec))}\n"
                else:
                    result += f"• {rec}\n"
        # Contract scan details (legacy)
        if contract_scan_result and hasattr(contract_scan_result, 'basic_info'):
            result += "\n*Contract Scan Details:*\n"
            for k, v in contract_scan_result.basic_info.items():
                result += f"• {k.replace('_', ' ').title()}: {v}\n"
            if hasattr(contract_scan_result, 'risk_factors') and contract_scan_result.risk_factors:
                result += "\n*Legacy Risk Factors:*\n"
                for k, v in contract_scan_result.risk_factors.items():
                    result += f"• {k.replace('_', ' ').title()}: {v}\n"
        result += "\nFor more detailed analysis, use /enhanced_scan command."
        return result
    
    @staticmethod
    def format_scan_depth_selection(address: str, is_premium: bool) -> str:
        """Format scan depth selection message"""
        premium_note = f"\n\n{Emoji.PREMIUM} _Note: Upgrade to premium for deep and comprehensive scans._" if not is_premium else ""
        
        return f"""{Emoji.CHART} *Select scan depth for contract:*
`{address}`

*Scan Types:*
• *Standard*: Basic + activity history and transaction patterns
• *Deep*: Standard + liquidity analysis and code pattern detection
• *Comprehensive*: Deep + related contracts and team reputation{premium_note}"""
    
    @staticmethod
    def format_scan_in_progress(address: str, scan_type: str) -> str:
        """Format scan in progress message"""
        return f"""{Emoji.SEARCH} *Enhanced Scan in Progress*

Contract: `{address}`
Scan Type: *{scan_type.capitalize()}*

Please wait, this may take a while..."""

    @staticmethod
    def paginate_results_header(current_page: int, total_pages: int) -> str:
        """Format pagination header"""
        return f"*Page {current_page}/{total_pages}*\n\n" 