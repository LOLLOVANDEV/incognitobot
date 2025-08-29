import os

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN",
                      "8283369012:AAEATY_DE5c_JIthvc2tIZJ2sLWgkfjNED0")
CHANNEL_ID = -1002970823092
CHANNEL_LINK = "https://t.me/+Wk0o0EGVFps4ZjBk"

# Hugging Face configuration
HF_TOKEN = "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"
HF_MODEL = "bilalRahib/TinyLLama-NSFW-Chatbot"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# Chat configuration
FREE_MESSAGES_LIMIT = 2
CREDITS_PER_MESSAGE = 2

# Messages in Italian
MESSAGES = {
    "not_subscribed": "❎ Per utilizzare il bot unisciti a questi canali:",
    "welcome": "Utente Anonimo, benvenuto nel bot",
    "checking": "Controllo iscrizione...",
    "error": "Si è verificato un errore. Riprova più tardi."
}

# Button labels
BUTTONS = {
    "channel": "1️⃣ Canale",
    "refresh": "♻️ Aggiorna",
    "new_chat": "✅ Nuova Chat",
    "profile": "👤 Profilo",
    "buy_credits": "🪙 Compra crediti"
}
