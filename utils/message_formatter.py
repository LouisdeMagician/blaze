"""
Message formatting utilities for Blaze Analyst.
Handles formatting and splitting of messages for Telegram.
"""
import logging
from typing import List, Tuple, Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

# Maximum message length for Telegram
MAX_MESSAGE_LENGTH = 4096

def split_message(message: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Split a long message into multiple parts to fit Telegram message limits.
    Tries to split at paragraph breaks or sentence boundaries.
    
    Args:
        message: The message to split
        max_length: Maximum length of each part (default: Telegram's limit)
        
    Returns:
        List[str]: List of message parts
    """
    if len(message) <= max_length:
        return [message]
    
    parts = []
    remaining = message
    
    while len(remaining) > 0:
        if len(remaining) <= max_length:
            parts.append(remaining)
            break
        
        # Try to find a good split point
        # First preference: paragraph break
        split_point = remaining[:max_length].rfind('\n\n')
        
        if split_point == -1 or split_point < max_length // 2:
            # Second preference: line break
            split_point = remaining[:max_length].rfind('\n')
        
        if split_point == -1 or split_point < max_length // 2:
            # Third preference: sentence boundary
            sentences = re.finditer(r'[.!?]\s+', remaining[:max_length])
            sentence_ends = [m.end() for m in sentences]
            
            if sentence_ends:
                split_point = sentence_ends[-1] - 1  # -1 to get position of the punctuation
            else:
                # Last resort: Just split at max_length, being careful with markdown
                split_point = max_length - 20  # Leave some margin for safety
        
        # Extract the part
        part = remaining[:split_point + 1].strip()
        parts.append(part)
        
        # Update remaining text
        remaining = remaining[split_point + 1:].strip()
        
        # Ensure proper markdown balancing by checking for unclosed formatting
        if '`' in part:
            # Count backticks and ensure they're balanced
            if part.count('`') % 2 != 0:
                # If unbalanced, add a backtick to close current code block
                parts[-1] += '`'
                # And add one to open the next section
                remaining = '`' + remaining
        
        # Same for bold formatting
        if '*' in part:
            # Count asterisks and ensure they're balanced (for bold formatting)
            if part.count('*') % 2 != 0:
                # If unbalanced, add asterisk to close current bold and open next
                parts[-1] += '*'
                remaining = '*' + remaining
    
    # Add part numbering for clarity
    for i in range(len(parts)):
        if len(parts) > 1:
            parts[i] = f"[Part {i+1}/{len(parts)}]\n\n{parts[i]}"
    
    return parts

def format_token_info(contract: Any, analysis_result: Any) -> str:
    """
    Format token information for display in Telegram.
    
    Args:
        contract: Contract object
        analysis_result: Analysis result object
        
    Returns:
        str: Formatted message
    """
    # Basic contract information
    token_name = contract.name or "Unknown Token"
    token_symbol = contract.symbol or "???"
    
    # Format response
    response = (
        f"*Token Analysis: {token_name} ({token_symbol})*\n\n"
        f"*Address:* `{contract.address}`\n"
        f"*Type:* {contract.contract_type.value.capitalize()}\n"
    )
    
    if contract.total_supply is not None:
        # Format with proper decimals
        if contract.decimals:
            formatted_supply = contract.total_supply / (10 ** contract.decimals)
            response += f"*Total Supply:* {formatted_supply:,.2f}\n"
        else:
            response += f"*Total Supply:* {contract.total_supply:,}\n"
    
    response += f"*Risk Level:* {contract.risk_level.value.upper()}\n\n"
    
    # Add analysis summary
    response += f"*Summary:*\n{analysis_result.summary}\n\n"
    
    # Add risk factors if available
    if analysis_result.risk_factors:
        response += "*Risk Factors:*\n"
        for factor, score in sorted(analysis_result.risk_factors.items(), key=lambda x: x[1], reverse=True)[:5]:
            if score > 0:
                # Format the factor name to be more readable
                formatted_factor = factor.replace("_", " ").capitalize()
                response += f"• {formatted_factor}: {score:.2f}\n"
        response += "\n"
    
    # Add recommendations
    if analysis_result.recommendations:
        response += "*Recommendations:*\n"
        for recommendation in analysis_result.recommendations[:3]:  # Limit to top 3
            response += f"• {recommendation}\n"
    
    return response

def format_analysis_export(contract: Any, analysis_result: Any, export_format: str = "text") -> Tuple[str, str]:
    """
    Format analysis results for export.
    
    Args:
        contract: Contract object
        analysis_result: Analysis result object
        export_format: Format to export in ("text" or "json")
        
    Returns:
        Tuple[str, str]: (filename, formatted_content)
    """
    token_name = contract.name or "Unknown"
    token_symbol = contract.symbol or "UNK"
    safe_name = f"{token_name}_{token_symbol}".replace(" ", "_")
    
    if export_format == "json":
        import json
        
        # Create a JSON representation
        export_data = {
            "token": {
                "name": token_name,
                "symbol": token_symbol,
                "address": contract.address,
                "type": contract.contract_type.value,
                "total_supply": contract.total_supply,
                "decimals": contract.decimals,
                "risk_level": contract.risk_level.value
            },
            "analysis": {
                "summary": analysis_result.summary,
                "risk_factors": analysis_result.risk_factors,
                "scores": analysis_result.scores,
                "recommendations": analysis_result.recommendations,
                "timestamp": analysis_result.timestamp.isoformat() if hasattr(analysis_result, "timestamp") else None
            }
        }
        
        filename = f"{safe_name}_analysis.json"
        content = json.dumps(export_data, indent=2)
        
    else:  # Default to text
        # Format as plain text with basic structure
        content = f"BLAZE ANALYST - TOKEN ANALYSIS\n"
        content += f"==============================\n\n"
        content += f"Token: {token_name} ({token_symbol})\n"
        content += f"Address: {contract.address}\n"
        content += f"Type: {contract.contract_type.value.capitalize()}\n"
        
        if contract.total_supply is not None:
            if contract.decimals:
                formatted_supply = contract.total_supply / (10 ** contract.decimals)
                content += f"Total Supply: {formatted_supply:,.2f}\n"
            else:
                content += f"Total Supply: {contract.total_supply:,}\n"
        
        content += f"Risk Level: {contract.risk_level.value.upper()}\n\n"
        
        # Add analysis summary
        content += f"SUMMARY\n"
        content += f"-------\n"
        content += f"{analysis_result.summary}\n\n"
        
        # Add risk factors
        content += f"RISK FACTORS\n"
        content += f"-----------\n"
        if analysis_result.risk_factors:
            for factor, score in sorted(analysis_result.risk_factors.items(), key=lambda x: x[1], reverse=True):
                if score > 0:
                    formatted_factor = factor.replace("_", " ").capitalize()
                    content += f"• {formatted_factor}: {score:.2f}\n"
        else:
            content += "No significant risk factors detected.\n"
        content += "\n"
        
        # Add recommendations
        content += f"RECOMMENDATIONS\n"
        content += f"---------------\n"
        if analysis_result.recommendations:
            for recommendation in analysis_result.recommendations:
                content += f"• {recommendation}\n"
        else:
            content += "No specific recommendations.\n"
        
        filename = f"{safe_name}_analysis.txt"
    
    return filename, content

def format_message(message: str) -> str:
    """Stub for format_message. Returns the message unchanged."""
    return message 