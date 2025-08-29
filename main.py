#!/usr/bin/env python3
"""
Telegram Bot for Channel Membership Management
Manages user access based on channel subscription with Italian interface
"""

import telebot
from telebot import types
import time
import logging
import random
import string
import os
import requests
import json
from config import BOT_TOKEN, CHANNEL_ID, CHANNEL_LINK, MESSAGES, BUTTONS, HF_TOKEN, HF_API_URL, FREE_MESSAGES_LIMIT, CREDITS_PER_MESSAGE

# Fake profiles database
FAKE_PROFILES = [
    {
        "nome": "Sofia",
        "eta": 22,
        "foto": "https://i.imgur.com/dJ8k2Vm.jpg"
    },
    {
        "nome": "Giulia",
        "eta": 24,
        "foto": "https://i.imgur.com/fX9mN4p.jpg"
    },
    {
        "nome": "Martina",
        "eta": 21,
        "foto": "https://i.imgur.com/hK7vR2s.jpg"
    },
    {
        "nome": "Francesca",
        "eta": 26,
        "foto": "https://i.imgur.com/bL3nM8q.jpg"
    },
    {
        "nome": "Chiara",
        "eta": 23,
        "foto": "https://i.imgur.com/rT6wP9m.jpg"
    },
    {
        "nome": "Alessia",
        "eta": 25,
        "foto": "https://i.imgur.com/sQ4vX7k.jpg"
    },
    {
        "nome": "Valentina",
        "eta": 20,
        "foto": "https://i.imgur.com/mH8nL5r.jpg"
    },
    {
        "nome": "Elena",
        "eta": 27,
        "foto": "https://i.imgur.com/nK9pQ3w.jpg"
    },
    {
        "nome": "Camilla",
        "eta": 22,
        "foto": "https://i.imgur.com/vR4sT8m.jpg"
    },
    {
        "nome": "Aurora",
        "eta": 24,
        "foto": "https://i.imgur.com/wP7nM6q.jpg"
    }
]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Database file for users
DATABASE_FILE = "users_database.txt"

# Admin user IDs
ADMIN_IDS = [7517832119, 7408188866, 7839114402]

# Chat state tracking
user_chat_states = {}  # user_id: {'in_chat': bool, 'messages_sent': int, 'current_profile': dict}

def generate_user_id():
    """
    Generate a unique 5-character alphanumeric ID
    """
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def load_user_database():
    """
    Load users from database file
    Returns dictionary with user_id as key and user data as value
    """
    users = {}
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 3:
                            telegram_id = int(parts[0])
                            unique_id = parts[1]
                            credits = int(parts[2])
                            city = parts[3] if len(parts) > 3 else "non selezionata"
                            free_messages_used = int(parts[4]) if len(parts) > 4 else 0
                            users[telegram_id] = {
                                'unique_id': unique_id,
                                'credits': credits,
                                'city': city,
                                'free_messages_used': free_messages_used
                            }
        except Exception as e:
            logger.error(f"Error loading database: {e}")
    return users

def save_user_to_database(telegram_id, unique_id, credits, city="non selezionata", free_messages_used=0):
    """
    Save or update user in database file
    """
    try:
        users = load_user_database()
        # Preserve existing values if not provided
        if telegram_id in users:
            if city == "non selezionata":
                city = users[telegram_id].get('city', "non selezionata")
            if free_messages_used == 0:
                free_messages_used = users[telegram_id].get('free_messages_used', 0)

        users[telegram_id] = {
            'unique_id': unique_id,
            'credits': credits,
            'city': city,
            'free_messages_used': free_messages_used
        }

        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            for t_id, data in users.items():
                f.write(f"{t_id}|{data['unique_id']}|{data['credits']}|{data['city']}|{data.get('free_messages_used', 0)}\n")
    except Exception as e:
        logger.error(f"Error saving to database: {e}")

def get_or_create_user(telegram_id):
    """
    Get user data or create new user if doesn't exist
    """
    users = load_user_database()
    if telegram_id in users:
        user_data = users[telegram_id]
        return (user_data['unique_id'], user_data['credits'],
                user_data.get('city', "non selezionata"),
                user_data.get('free_messages_used', 0))
    else:
        # Create new user with unique ID and 0 credits
        unique_id = generate_user_id()
        # Ensure unique ID is actually unique
        while any(data['unique_id'] == unique_id for data in users.values()):
            unique_id = generate_user_id()

        save_user_to_database(telegram_id, unique_id, 0, "non selezionata", 0)
        return unique_id, 0, "non selezionata", 0

def find_user_by_unique_id(unique_id):
    """
    Find user by their unique ID, returns telegram_id, credits and city
    """
    users = load_user_database()
    for telegram_id, data in users.items():
        if data['unique_id'] == unique_id:
            return telegram_id, data['credits'], data.get('city', "non selezionata")
    return None, None, None

def is_admin(user_id):
    """
    Check if user is an admin
    """
    return user_id in ADMIN_IDS

def check_channel_membership(user_id):
    """
    Check if user is subscribed to the required channel
    Returns True if subscribed, False otherwise
    """
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        # User is considered subscribed if they are member, administrator, or creator
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking membership for user {user_id}: {e}")
        return False

def create_subscription_keyboard():
    """
    Create inline keyboard with channel link and refresh button
    """
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    # Channel button with direct link
    channel_btn = types.InlineKeyboardButton(
        text=BUTTONS["channel"],
        url=CHANNEL_LINK
    )

    # Refresh button with callback data
    refresh_btn = types.InlineKeyboardButton(
        text=BUTTONS["refresh"],
        callback_data="refresh_membership"
    )

    keyboard.add(channel_btn)
    keyboard.add(refresh_btn)

    return keyboard

def send_subscription_prompt(chat_id):
    """
    Send message prompting user to subscribe to channel
    """
    try:
        keyboard = create_subscription_keyboard()
        bot.send_message(
            chat_id=chat_id,
            text=MESSAGES["not_subscribed"],
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error sending subscription prompt to {chat_id}: {e}")

def create_main_keyboard():
    """
    Create main menu keyboard for subscribed users
    """
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    # First row - two buttons
    keyboard.add(BUTTONS["new_chat"], BUTTONS["profile"])

    # Second row - one button
    keyboard.add(BUTTONS["buy_credits"])

    return keyboard

def send_welcome_message(chat_id):
    """
    Send welcome message to subscribed users with main menu
    """
    try:
        keyboard = create_main_keyboard()
        bot.send_message(
            chat_id=chat_id,
            text=MESSAGES["welcome"],
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error sending welcome message to {chat_id}: {e}")

@bot.message_handler(commands=['start'])
def handle_start(message):
    """
    Handle /start command - check subscription and respond accordingly
    """
    user_id = message.from_user.id
    chat_id = message.chat.id

    logger.info(f"User {user_id} started the bot")

    # Check if user is subscribed to the channel
    if check_channel_membership(user_id):
        send_welcome_message(chat_id)
    else:
        send_subscription_prompt(chat_id)


@bot.callback_query_handler(func=lambda call: call.data == "refresh_membership")
def handle_refresh_callback(call):
    """
    Handle refresh button callback - recheck membership status
    """
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    logger.info(f"User {user_id} clicked refresh button")

    try:
        # Answer callback query to stop loading indicator
        bot.answer_callback_query(call.id, MESSAGES["checking"])

        # Check current membership status
        if check_channel_membership(user_id):
            # User is now subscribed - delete old message and send welcome
            bot.delete_message(chat_id, message_id)
            send_welcome_message(chat_id)
        else:
            # User still not subscribed - update callback response
            bot.answer_callback_query(
                call.id,
                "❌ Non sei ancora iscritto al canale",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Error handling refresh callback for user {user_id}: {e}")
        bot.answer_callback_query(call.id, MESSAGES["error"])

def send_pricing_menu(chat_id):
    """
    Send pricing menu with photo and buttons
    """
    try:
        # Create pricing message
        pricing_text = """Scegli il tuo piano:

🔹 Piano Base
100 Crediti - 59€

🔥 Piano Classico (più venduto)
500 Crediti - 169€

👑 Piano Premium
1000 Crediti - 289€"""

        # Create inline keyboard with pricing plans
        keyboard = types.InlineKeyboardMarkup()

        piano_base_btn = types.InlineKeyboardButton(
            text="Piano Base",
            url="https://t.me/KataraDeana?text=Ciao,%20sono%20interessato%20al%20piano%20base."
        )
        piano_classico_btn = types.InlineKeyboardButton(
            text="🔥 Piano Classico",
            url="https://t.me/KataraDeana?text=Ciao,%20sono%20interessato%20al%20piano%20classico."
        )
        piano_elite_btn = types.InlineKeyboardButton(
            text="👑 Piano Premium",
            url="https://t.me/KataraDeana?text=Ciao,%20sono%20interessato%20al%20piano%20premium."
        )

        keyboard.add(piano_base_btn)
        keyboard.add(piano_classico_btn)
        keyboard.add(piano_elite_btn)

        # Send photo with pricing text and buttons
        bot.send_photo(
            chat_id=chat_id,
            photo="https://i.imgur.com/kfIj7Ik.png",
            caption=pricing_text,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error sending pricing menu to {chat_id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "show_pricing")
def handle_show_pricing_callback(call):
    """
    Handle show pricing button callback from profile
    """
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    logger.info(f"User {user_id} clicked show pricing button from profile")

    try:
        bot.answer_callback_query(call.id, "Caricamento piani...")
        send_pricing_menu(chat_id)
    except Exception as e:
        logger.error(f"Error handling show pricing callback for user {user_id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "select_city")
def handle_select_city_callback(call):
    """
    Handle select city button callback from profile
    """
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    logger.info(f"User {user_id} clicked select city button")

    try:
        bot.answer_callback_query(call.id, "Inserisci la tua città...")
        bot.send_message(chat_id, "📍 Inserisci il nome della tua citta'")

        # Set user state to expect city input
        bot.register_next_step_handler(call.message, process_city_input, user_id)
    except Exception as e:
        logger.error(f"Error handling select city callback for user {user_id}: {e}")

def get_italian_cities():
    """
    Returns a set of valid Italian cities (major cities and provincial capitals)
    """
    return {
        # Capoluoghi di regione e province principali
        'roma', 'milano', 'napoli', 'torino', 'palermo', 'genova', 'bologna', 'firenze', 'bari', 'catania',
        'venezia', 'verona', 'messina', 'padova', 'trieste', 'taranto', 'brescia', 'parma', 'prato', 'modena',
        'reggio calabria', 'reggio emilia', 'perugia', 'livorno', 'ravenna', 'cagliari', 'foggia', 'rimini',
        'salerno', 'ferrara', 'sassari', 'latina', 'giugliano in campania', 'monza', 'siracusa', 'pescara',
        'bergamo', 'forlì', 'trento', 'vicenza', 'terni', 'bolzano', 'novara', 'piacenza', 'ancona', 'andria',
        'arezzo', 'udine', 'cesena', 'lecce', 'pesaro', 'barletta', 'alessandria', 'como', 'pistoia', 'pavia',
        'treviso', 'catanzaro', 'caserta', 'brindisi', 'grosseto', 'asti', 'varese', 'cremona', 'cosenza',
        'vigevano', 'trapani', 'crotone', 'potenza', 'viterbo', 'vercelli', 'cuneo', 'caltanissetta', 'agrigento',
        'matera', 'enna', 'ragusa', 'l\'aquila', 'chieti', 'teramo', 'pescara', 'campobasso', 'isernia',
        'benevento', 'avellino', 'caserta', 'frosinone', 'rieti', 'viterbo', 'tivoli', 'guidonia montecelio',
        'fiumicino', 'pomezia', 'aprilia', 'velletri', 'civitavecchia', 'anzio', 'nettuno', 'marino', 'frascati',
        'genzano di roma', 'albano laziale', 'monterotondo', 'mentana', 'fonte nuova', 'riano', 'fiano romano',
        # Aggiungere altre città importanti
        'aosta', 'pordenone', 'gorizia', 'imperia', 'savona', 'la spezia', 'massa', 'carrara', 'lucca', 'siena',
        'grosseto', 'terni', 'rieti', 'viterbo', 'latina', 'frosinone', 'isernia', 'campobasso', 'teramo',
        'pescara', 'chieti', 'l\'aquila', 'potenza', 'matera', 'cosenza', 'catanzaro', 'reggio calabria',
        'crotone', 'vibo valentia', 'trapani', 'palermo', 'messina', 'agrigento', 'caltanissetta', 'enna',
        'catania', 'ragusa', 'siracusa', 'cagliari', 'sassari', 'nuoro', 'oristano', 'carbonia', 'iglesias',
        'olbia', 'tempio pausania'
    }

def process_city_input(message, user_id):
    """
    Process city input from user - validate that it's a real Italian city
    """
    chat_id = message.chat.id
    city_name = message.text.strip()

    try:
        if not city_name:
            bot.send_message(chat_id, "❌ Nome città non valido. Riprova.")
            return

        # Basic validation - city name should be alphabetic and reasonable length
        if len(city_name) < 2 or len(city_name) > 50:
            bot.send_message(chat_id, "❌ Nome città non valido. Inserisci una città italiana valida.")
            return

        # Normalize city name for comparison
        normalized_city = city_name.lower().strip()
        italian_cities = get_italian_cities()

        # Check if the city is in our list of valid Italian cities
        if normalized_city not in italian_cities:
            bot.send_message(chat_id, "❌ Città non trovata. Inserisci una città italiana valida (es: Roma, Milano, Napoli).")
            return

        # Get current user data
        unique_id, credits, _, free_messages_used = get_or_create_user(user_id)

        # Update user with new city (properly capitalized)
        proper_city_name = city_name.title()
        save_user_to_database(user_id, unique_id, credits, proper_city_name, free_messages_used)

        bot.send_message(chat_id, f"✅ Città aggiornata: {proper_city_name}")

        logger.info(f"User {user_id} updated city to: {proper_city_name}")

    except Exception as e:
        logger.error(f"Error processing city input for user {user_id}: {e}")
        bot.send_message(chat_id, "❌ Errore durante l'aggiornamento della città.")



def create_chat_keyboard():
    """
    Create keyboard for chat mode with new user and end chat buttons
    """
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add("🔄 Nuovo Utente", "❌ Termina Chat")
    return keyboard

def get_contextual_response(prompt, profile_name, conversation_history=[]):
    """
    Get contextual AI response based on user input and conversation history - more spicy version
    """
    prompt_lower = prompt.lower().strip()
    
    # Spicy response patterns with provocative content
    response_patterns = {
        'ciao': [
            f"Ciao bello! 😈 Hai voglia di giocare con me?",
            f"Ehi tesoro! 🔥 Mi hai fatto venire voglia di te...",
            f"Ciao amore! 💋 Spero tu sia pronto per me!"
        ],
        'grazie': [
            "Prego baby! 😏 Ora tocca a te farmi felice...",
            "Figurati! 🔥 Dimmi cosa vorresti fare con me...",
            "Di niente sexy! 💋 Raccontami le tue fantasie!"
        ],
        'bene': [
            "Perfetto! 😈 Anch'io sto bene... anzi bollente!",
            "Fantastico! 🔥 Io sono tutta eccitata oggi!",
            "Che bello! 💋 Dimmi, hai voglia di divertirti?"
        ],
        'come va': [
            "Benissimo! 😈 Sto pensando a te nudo... e tu?",
            "Alla grande! 🔥 Ho una voglia matta di te!",
            "Perfetto! 💋 Sono tutta calda oggi! Raccontami di te!",
            "Benissimo grazie! 😏 Stavo fantasticando su di te...",
            "Molto bene! 🔥 Ho fatto sogni piccanti stanotte!"
        ],
        'come stai': [
            "Benissimo! 😈 Ma sarei meglio se fossi qui con me...",
            "Alla grande! 🔥 Tu invece... hai voglia di me?",
            "Perfetta! 💋 Soprattutto ora che ci sei tu!",
            "Molto bene! 😏 Sono sempre eccitata quando parlo con te!"
        ],
        'cosa fai': [
            "Sto pensando a te! 😈 E a quello che vorrei farti...",
            "Niente di speciale... 🔥 Ma ho certe fantasie...",
            "Stavo toccandomi pensando a te! 💋 Tu cosa fai?",
            "Sto qui tutta nuda ad aspettarti! 😏 E tu?"
        ],
        'bello': [
            "Grazie tesoro! 🔥 Tu invece mi fai venire voglia...",
            "Sei dolce! 😈 Ma io sono anche molto cattiva...",
            "Aww! 💋 Tu mi fai sentire così sexy!"
        ],
        'casino': [
            "Il casino? 😏 Preferisco giocare con te... se capisci cosa intendo!",
            "Anche tu giochi? 🔥 Io preferisco altri tipi di giochi... più intimi!",
            "Al casino? 😈 Io scommetterei tutto su di noi due insieme!"
        ],
        'scopo': [
            "Oh mio dio! 😈 Sei proprio diretto! Mi piacciono gli uomini così...",
            "Che cattivo che sei! 🔥 Ma ammetto che mi ecciti...",
            "Mmm... 💋 Parli come uno che sa quello che vuole!"
        ],
        'madre': [
            "Che maleducato! 😏 Ma devo ammettere che mi piace quando sei così...",
            "Ooh! 😈 Hai un caratterino! Mi eccita quando ti arrabbi...",
            "Che linguaggio! 🔥 Ma sai cosa? Mi stai facendo venire voglia..."
        ],
        'come ti chiami': [
            f"Mi chiamo {profile_name}! 😈 E tu come ti chiami, bello?",
            f"Sono {profile_name}! 🔥 Ma puoi chiamarmi come vuoi... anche 'mia'!",
            f"{profile_name}, piacere! 💋 Spero di piacere anche a te!"
        ],
        'nome': [
            f"Il mio nome è {profile_name}! 😈 Ma tu urlalo quando...",
            f"Sono {profile_name}! 🔥 Dimmi il tuo, così so come chiamarti!",
            f"Mi chiamo {profile_name}! 💋 Ma preferisco quando mi chiami 'baby'!"
        ],
        'cosa mi faresti': [
            "Ti farei impazzire! 😈 Ti toccherei ovunque finché non implori...",
            "Mmm... tante cose cattive! 🔥 Ti farei venire voglia come non mai!",
            "Inizierei baciandoti il collo... 💋 poi scendiamo sempre più giù!",
            "Ti farei sentire come un re! 😏 E tu cosa faresti a me?",
            "Oh tesoro... 🔥 ti farei cose che non hai mai provato!"
        ],
        'faresti': [
            "Ti farei impazzire di piacere! 😈 Dimmi dove vorresti essere toccato...",
            "Tante cose piccanti! 🔥 Vuoi che te le racconti tutte?",
            "Ti farei sentire in paradiso! 💋 E tu a me cosa faresti?",
            "Cose molto cattive! 😏 Sei pronto per me?"
        ],
        'voglia': [
            "Anch'io ho tanta voglia di te! 😈 Vieni qui da me...",
            "La voglia che ho è incredibile! 🔥 Non riesco a smettere di pensarti!",
            "Ho una voglia matta! 💋 Dimmi cosa vuoi fare insieme...",
            "Sono tutta bagnata dalla voglia! 😏 Tu invece?"
        ],
        'nudo': [
            "Mmm... mi piace come pensi! 😈 Anch'io sono senza niente addosso!",
            "Perfetto! 🔥 Così posso toccarti meglio ovunque!",
            "Che bello! 💋 Dimmi cosa vedi quando mi guardi nuda...",
            "Sono già pronta per te! 😏 Vieni a prendermi!"
        ],
        'sesso': [
            "Oh sì baby! 😈 Sono sempre pronta per te!",
            "Mi piace quando parli così! 🔥 Raccontami le tue fantasie...",
            "Dimmi come lo vuoi! 💋 Sono tutta per te!",
            "Sono già eccitata solo a sentirti! 😏 Quando ci vediamo?"
        ]
    }
    
    # Check for specific phrases first (prioritize longer/more specific matches)
    matched_responses = []
    for keyword, responses in response_patterns.items():
        if keyword in prompt_lower:
            # Prioritize longer matches (more specific)
            matched_responses.append((len(keyword), responses))
    
    if matched_responses:
        # Get the longest match (most specific)
        matched_responses.sort(key=lambda x: x[0], reverse=True)
        return random.choice(matched_responses[0][1])
    
    # Spicy generic responses
    if len(prompt_lower) < 10:  # Short messages
        short_responses = [
            "Dimmi di più, baby! 😈",
            "Ah sì? 🔥 Continua a eccitarmi!",
            "Interessante! 💋 Vai avanti!",
            "E poi? 😏 Non fermarti!",
            "Mmm... 🔥 Mi stai piacendo!"
        ]
        return random.choice(short_responses)
    else:  # Longer messages
        long_responses = [
            "Mi piace come parli! 😈 Continua così che mi ecciti!",
            "Interessante! 🔥 Dimmi di più, mi stai facendo venire voglia!",
            "Ah sì? 💋 Raccontami tutto, sono tutta per te!",
            "Mi piaci quando parli così! 😏 Vai avanti!",
            "Sono curiosa! 🔥 Dimmi tutti i tuoi segreti!",
            "Hai catturato la mia attenzione! 😈 E non solo quella...",
            "Che sexy! 💋 Continua a parlarmi così!",
            "Mi stai facendo impazzire! 🔥 Non fermarti!"
        ]
        return random.choice(long_responses)

def query_huggingface_ai(prompt, profile_name):
    """
    Query Hugging Face NSFW AI model for spicy chat responses
    """
    try:
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json"
        }

        # Create a more provocative system prompt for the NSFW model
        system_prompt = f"Tu sei {profile_name}, una ragazza italiana sexy e provocante di 20-25 anni. Rispondi in modo malizioso, seducente e un po' spinto. Usa emoji come 😈🔥💋😏. Rispondi in italiano."
        full_prompt = f"{system_prompt}\n\nUser: {prompt}\n{profile_name}:"

        payload = {
            "inputs": full_prompt,
            "parameters": {
                "max_new_tokens": 80,
                "temperature": 0.9,
                "do_sample": True,
                "top_p": 0.9,
                "repetition_penalty": 1.2
            }
        }

        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                ai_response = result[0].get('generated_text', '').strip()
                
                # Extract only the AI response part
                if f"{profile_name}:" in ai_response:
                    ai_response = ai_response.split(f"{profile_name}:")[-1].strip()
                elif "User:" in ai_response:
                    parts = ai_response.split("User:")
                    if len(parts) > 1:
                        ai_response = parts[-1].split(f"{profile_name}:")[-1].strip()
                
                # Clean and validate response
                if ai_response and len(ai_response) > 3 and len(ai_response) < 200:
                    # Add emoji if missing
                    if not any(emoji in ai_response for emoji in ['😈', '🔥', '💋', '😏', '😊', '💕', '😘']):
                        ai_response += " 😈"
                    return ai_response
        
        # Use contextual fallback with spicy responses
        return get_contextual_response(prompt, profile_name)
        
    except Exception as e:
        logger.error(f"Error querying Hugging Face NSFW model: {e}")
        return get_contextual_response(prompt, profile_name)

def can_user_send_message(user_id):
    """
    Check if user can send a message (has free messages left or credits)
    """
    try:
        unique_id, credits, city, free_messages_used = get_or_create_user(user_id)

        # Check if user has free messages left
        if free_messages_used < FREE_MESSAGES_LIMIT:
            return True, "free"

        # Check if user has enough credits
        if credits >= CREDITS_PER_MESSAGE:
            return True, "credits"

        return False, "no_credits"
    except Exception as e:
        logger.error(f"Error checking user message permissions: {e}")
        return False, "error"

def consume_user_message(user_id):
    """
    Consume a free message or credits when user sends a message
    """
    try:
        unique_id, credits, city, free_messages_used = get_or_create_user(user_id)

        # Use free message first
        if free_messages_used < FREE_MESSAGES_LIMIT:
            save_user_to_database(user_id, unique_id, credits, city, free_messages_used + 1)
            return True, "free_message_used"

        # Use credits
        if credits >= CREDITS_PER_MESSAGE:
            save_user_to_database(user_id, unique_id, credits - CREDITS_PER_MESSAGE, city, free_messages_used)
            return True, "credits_used"

        return False, "insufficient_credits"
    except Exception as e:
        logger.error(f"Error consuming user message: {e}")
        return False, "error"

def send_random_profile(chat_id, user_city, user_id):
    """
    Send a random fake profile to the user and start AI chat
    """
    try:
        # Select random profile
        profile = random.choice(FAKE_PROFILES)

        # Initialize chat state
        user_chat_states[user_id] = {
            'in_chat': True,
            'messages_sent': 0,
            'current_profile': profile
        }

        # Create profile message
        profile_text = f"""👤 {profile['nome']}
🎂 {profile['eta']} anni
📍 {user_city}"""

        # Create chat keyboard
        keyboard = create_chat_keyboard()

        # Send photo with profile info
        bot.send_photo(
            chat_id=chat_id,
            photo=profile['foto'],
            caption=profile_text,
            reply_markup=keyboard
        )

        # Send AI greeting message
        greeting = query_huggingface_ai("Ciao", profile['nome'])
        bot.send_message(chat_id, f"💬 {profile['nome']}: {greeting}")

    except Exception as e:
        logger.error(f"Error sending random profile to {chat_id}: {e}")

@bot.message_handler(func=lambda message: message.text == BUTTONS["new_chat"])
def handle_new_chat_message(message):
    """
    Handle new chat button from keyboard - send random fake profile
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"User {user_id} clicked new chat button")

    try:
        if check_channel_membership(user_id):
            # Get user's city
            unique_id, credits, city, free_messages_used = get_or_create_user(user_id)

            if city == "non selezionata":
                bot.send_message(chat_id, "❌ Prima devi selezionare la tua città dal profilo!")
                return

            # Send random profile and start AI chat
            send_random_profile(chat_id, city, user_id)
        else:
            send_subscription_prompt(chat_id)
    except Exception as e:
        logger.error(f"Error handling new chat message for user {user_id}: {e}")

@bot.message_handler(func=lambda message: message.text == "🔄 Nuovo Utente")
def handle_new_user_message(message):
    """
    Handle new user button - send another random profile
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"User {user_id} clicked new user button")

    try:
        if check_channel_membership(user_id):
            # Get user's city
            unique_id, credits, city, free_messages_used = get_or_create_user(user_id)

            # Send another random profile and start new AI chat
            send_random_profile(chat_id, city, user_id)
        else:
            send_subscription_prompt(chat_id)
    except Exception as e:
        logger.error(f"Error handling new user message for user {user_id}: {e}")

@bot.message_handler(func=lambda message: message.text == "❌ Termina Chat")
def handle_end_chat_message(message):
    """
    Handle end chat button - return to main menu
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"User {user_id} clicked end chat button")

    try:
        if check_channel_membership(user_id):
            # End chat state
            if user_id in user_chat_states:
                del user_chat_states[user_id]

            # Send main menu back
            send_welcome_message(chat_id)
        else:
            send_subscription_prompt(chat_id)
    except Exception as e:
        logger.error(f"Error handling end chat message for user {user_id}: {e}")

@bot.message_handler(func=lambda message: message.text == BUTTONS["profile"])
def handle_profile_message(message):
    """
    Handle profile button from keyboard - show user profile
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"User {user_id} clicked profile button")

    try:
        if check_channel_membership(user_id):
            # Get or create user profile
            unique_id, credits, city, free_messages_used = get_or_create_user(user_id)

            free_messages_left = max(0, FREE_MESSAGES_LIMIT - free_messages_used)

            # Create profile message
            profile_text = f"""👤 Nome Utente: {unique_id}
🪙 Crediti: {credits} crediti
💬 Messaggi gratuiti rimasti: {free_messages_left}
📍 Citta': {city}

Selezionare se si vogliono trovare persone della propria citta'"""

            # Create inline keyboard with buy credits and select city buttons
            keyboard = types.InlineKeyboardMarkup()
            buy_credits_btn = types.InlineKeyboardButton(
                text="💰 Acquista Crediti",
                callback_data="show_pricing"
            )
            select_city_btn = types.InlineKeyboardButton(
                text="📍 Seleziona Citta'",
                callback_data="select_city"
            )
            keyboard.add(buy_credits_btn)
            keyboard.add(select_city_btn)

            bot.send_message(
                chat_id=chat_id,
                text=profile_text,
                reply_markup=keyboard
            )
        else:
            send_subscription_prompt(chat_id)
    except Exception as e:
        logger.error(f"Error handling profile message for user {user_id}: {e}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """
    Handle all text messages - AI chat or regular commands
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text

    # Skip if user is not in chat state
    if user_id not in user_chat_states or not user_chat_states[user_id]['in_chat']:
        return

    # Skip if message is a button command
    if text in [BUTTONS["new_chat"], BUTTONS["profile"], BUTTONS["buy_credits"], "🔄 Nuovo Utente", "❌ Termina Chat"]:
        return

    logger.info(f"User {user_id} sent chat message: {text}")

    try:
        if not check_channel_membership(user_id):
            send_subscription_prompt(chat_id)
            return

        # Check if user can send message
        can_send, reason = can_user_send_message(user_id)

        if not can_send:
            if reason == "no_credits":
                # Send credits needed message
                bot.send_message(
                    chat_id,
                    "💔 Non hai abbastanza crediti per continuare la conversazione!\n\n"
                    "🪙 Acquista crediti per continuare a chattare."
                )
                send_pricing_menu(chat_id)
                return
            else:
                bot.send_message(chat_id, "❌ Errore durante il controllo dei crediti.")
                return

        # Consume message (free or credits)
        consumed, consumption_type = consume_user_message(user_id)

        if not consumed:
            bot.send_message(chat_id, "❌ Errore durante l'elaborazione del messaggio.")
            return

        # Get current profile for AI response
        current_profile = user_chat_states[user_id]['current_profile']

        # Send typing indicator
        bot.send_chat_action(chat_id, 'typing')

        # Get AI response
        ai_response = query_huggingface_ai(text, current_profile['nome'])

        # Send AI response
        bot.send_message(chat_id, f"💬 {current_profile['nome']}: {ai_response}")

        # Update message count
        user_chat_states[user_id]['messages_sent'] += 1

        logger.info(f"AI responded to user {user_id}, consumption: {consumption_type}")

    except Exception as e:
        logger.error(f"Error handling chat message from user {user_id}: {e}")

@bot.message_handler(func=lambda message: message.text == BUTTONS["buy_credits"])
def handle_buy_credits_message(message):
    """
    Handle buy credits button from keyboard - show pricing plans
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"User {user_id} clicked buy credits button")

    try:
        if check_channel_membership(user_id):
            send_pricing_menu(chat_id)
        else:
            send_subscription_prompt(chat_id)
    except Exception as e:
        logger.error(f"Error handling buy credits message for user {user_id}: {e}")

@bot.message_handler(commands=['ricarica'])
def handle_recharge_command(message):
    """
    Handle /ricarica command - Admin only
    Usage: /ricarica <amount> <unique_id>
    """
    user_id = message.from_user.id
    chat_id = message.chat.id

    logger.info(f"User {user_id} used /ricarica command")

    try:
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Non hai i permessi per usare questo comando.")
            return

        # Parse command arguments
        command_parts = message.text.split()
        if len(command_parts) != 3:
            bot.send_message(chat_id, "❌ Uso corretto: /ricarica <quantità> <codice_univoco>")
            return

        try:
            amount = int(command_parts[1])
            unique_id = command_parts[2].upper()
        except ValueError:
            bot.send_message(chat_id, "❌ La quantità deve essere un numero valido.")
            return

        if amount < 0:
            bot.send_message(chat_id, "❌ La quantità non può essere negativa.")
            return

        # Find user by unique ID
        target_telegram_id, current_credits, current_city = find_user_by_unique_id(unique_id)

        if target_telegram_id is None or current_credits is None:
            bot.send_message(chat_id, f"❌ Utente con codice {unique_id} non trovato.")
            return

        # Get current free messages used
        _, _, _, free_messages_used = get_or_create_user(target_telegram_id)

        # Set total credits (not add)
        new_credits = amount
        save_user_to_database(target_telegram_id, unique_id, new_credits, current_city, free_messages_used)

        # Confirm to admin
        bot.send_message(
            chat_id,
            f"✅ Crediti dell'utente {unique_id} impostati a {new_credits}.\nCrediti precedenti: {current_credits}"
        )

        # Notify the user about credit change
        try:
            bot.send_message(
                target_telegram_id,
                f"✅ I tuoi crediti sono stati impostati a {new_credits}."
            )
        except Exception as notify_error:
            logger.error(f"Could not notify user {target_telegram_id}: {notify_error}")
            bot.send_message(chat_id, "⚠️ Crediti aggiunti ma impossibile notificare l'utente.")

    except Exception as e:
        logger.error(f"Error in /ricarica command: {e}")
        bot.send_message(chat_id, "❌ Errore durante l'esecuzione del comando.")

@bot.message_handler(commands=['info'])
def handle_info_command(message):
    """
    Handle /info command - Admin only
    Usage: /info <unique_id>
    """
    user_id = message.from_user.id
    chat_id = message.chat.id

    logger.info(f"User {user_id} used /info command")

    try:
        if not is_admin(user_id):
            bot.send_message(chat_id, "❌ Non hai i permessi per usare questo comando.")
            return

        # Parse command arguments
        command_parts = message.text.split()
        if len(command_parts) != 2:
            bot.send_message(chat_id, "❌ Uso corretto: /info <codice_univoco>")
            return

        unique_id = command_parts[1].upper()

        # Find user by unique ID
        target_telegram_id, credits, city = find_user_by_unique_id(unique_id)

        if target_telegram_id is None:
            bot.send_message(chat_id, f"❌ Utente con codice {unique_id} non trovato.")
            return

        # Send user info
        info_text = f"🔢 Codice Utente: {unique_id}\n🪙 Crediti: {credits}\n📍 Città: {city}"
        bot.send_message(chat_id, info_text)

    except Exception as e:
        logger.error(f"Error in /info command: {e}")
        bot.send_message(chat_id, "❌ Errore durante l'esecuzione del comando.")

@bot.chat_join_request_handler()
def handle_join_request(join_request):
    """
    Automatically approve join requests to the channel
    """
    try:
        chat_id = join_request.chat.id
        user_id = join_request.from_user.id

        # Only handle requests for our specific channel
        if chat_id == CHANNEL_ID:
            logger.info(f"Auto-approving join request from user {user_id}")
            bot.approve_chat_join_request(chat_id, user_id)
    except Exception as e:
        logger.error(f"Error approving join request: {e}")

def main():
    """
    Main function to start the bot
    """
    logger.info("Starting Telegram bot...")

    try:
        # Test bot token by getting bot info
        bot_info = bot.get_me()
        logger.info(f"Bot started successfully: @{bot_info.username}")

        # Start polling for messages
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            none_stop=True
        )
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    main()
