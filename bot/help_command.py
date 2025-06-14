from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Help: Use /scan to analyze a token, /defi for DeFi analysis, and /contact for support.")

def get_help_handler():
    return CommandHandler("help", help_command) 