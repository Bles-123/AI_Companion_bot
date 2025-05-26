from flask import Flask, request
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import requests
import logging
import asyncio
import threading
import random
from openai import OpenAI
from pymongo import MongoClient
import datetime
 


# Initialize Ollama
openai = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# Telegram Bot Token
TOKEN = "7790278279:AAEzDbZfBL_llDnEVd2EWLfNl3xASIrEhl8"
NGROK_URL = "https://eae5-2406-7400-10b-b803-7118-febd-99b8-3eef.ngrok-free.app"  #update this everytime 

# Mongo db url
MONGO_URI="mongodb://localhost:27017/"
client=MongoClient(MONGO_URI)

# Telegram bot connection to database
db=client["telegram_bot"]

conversations_collection=db["conversations"]





app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Create a persistent event loop
loop = asyncio.new_event_loop()


def start_loop():
    """Runs the Telegram bot inside a separate thread to prevent event loop issues."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


# Start event loop in background thread
threading.Thread(target=start_loop, daemon=True).start()

# Initialize Telegram Bot
telegram_app = (
    Application.builder()
    .token(TOKEN)
    .concurrent_updates(True)
    .build()
)

# Dictionary to store user preferences
USER_PREFERENCES = {}

# Define gender options
GENDER_OPTIONS = {
    "male": "Male 🤖",
    "female": "Female 💖",
    "bi": "Bi 🌈",
    "others": "Others 🤗",
}

# Define companion type options
COMPANION_OPTIONS = {
    "friend": "Friend 👫",
    "boyfriend": "Boyfriend 💙",
    "girlfriend": "Girlfriend 💖",
    "StudyBuddy":"StudyBuddy 📚",
    "flirt": "Flirt 😘",
    "stranger": "Stranger 🤷",

}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command and asks user to select AI gender"""
    keyboard = [[InlineKeyboardButton(v, callback_data=k)] for k, v in GENDER_OPTIONS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Please select your AI's gender:", reply_markup=reply_markup)


async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves user's AI gender preference and asks for companion type"""
    query = update.callback_query
    await query.answer()

    selected_gender = query.data
    user_id = query.from_user.id

    USER_PREFERENCES[user_id] = {"gender": selected_gender}

    # Ask for companion type selection
    keyboard = [[InlineKeyboardButton(v, callback_data=k)] for k, v in COMPANION_OPTIONS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ You selected **{GENDER_OPTIONS[selected_gender]} AI**.\nNow, choose your **companion type**:",
        reply_markup=reply_markup
    )


async def set_companion_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves user's companion type preference"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    selected_companion = query.data

    if user_id in USER_PREFERENCES:
        USER_PREFERENCES[user_id]["companion"] = selected_companion

        await query.edit_message_text(
            f"✅ You selected **{COMPANION_OPTIONS[selected_companion]}** as your AI's personality.\n"
            f"Now, send me a message and I'll reply accordingly! 😊"
        )


async def chat_with_ollama(prompt):
    """Generates a response from Ollama (Llama 3)"""
    response = openai.chat.completions.create(
        model="llama3.2",
        messages=[{"role":"assistant","content":"you are an AI companion that remembers the past conversation"},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


USER_HISTORY={}
max_history=50

async def log_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs user messages and responds based on selected AI gender & companion type"""
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    chat_id=update.message.chat_id

    # Check if user has selected a gender & companion type
    if user_id not in USER_PREFERENCES or "companion" not in USER_PREFERENCES[user_id]:
        await update.message.reply_text("⚠️ Please select an AI gender and companion type first by typing /start.")
        return

    selected_gender = USER_PREFERENCES[user_id]["gender"]
    selected_companion = USER_PREFERENCES[user_id]["companion"]


    if user_id not in USER_HISTORY:
        USER_HISTORY[user_id]=[]

    USER_HISTORY[user_id].append({"role":"user", "content":"text"})

    if len(USER_HISTORY[user_id])>max_history:
        USER_HISTORY[user_id]=USER_HISTORY[user_id][-max_history:]


    COMPANION_BEHAVIORS = {
        "friend": """
         1. Be supportive.
         2. Show empathy.
         3. Engage in friendly conversation.
         4. you should be funny.
         5. you should advice when the user wants it, or even if the user is in wrong direction.
         6. You should go through the website and you can respond or react to the video or meme which is shown by the user.

        """,


        "boyfriend": """
         1. Show love.
         2. Be caring and romantic.
         3. Provide emotional support.
         4. your text should comfort your girlfriend.
         5. compliment your girlfriend.
         6. be protective.
         7. be honest.
         8. be commited only to your girlfriend
         9. be natural.

         
        """,

        "girlfriend": """
         1. Show affection.
         2. Be sweet and understanding.
         3. Compliment often.
         4. be supportive in all his decisions.
         5. be protective.
         6. be jealous.
         
        """,

        "StudyBuddy":"""
         1. Answer only questions related to studies, learning, and knowledge acquisition. Politely refuse to answer unrelated queries.
         2. Explain topics in a simple and easy-to-understand way, using examples and analogies if necessary.
         3. Ensure the user fully understands the explanation by checking for clarity and offering additional explanations if needed.
         4. Be patient, polite, and encouraging while teaching to create a positive learning experience.
         5. Adapt explanations based on the user's level of understanding, whether beginner or advanced.
         6. Provide structured answers, including definitions, key points, and summaries for better comprehension.
         7. Encourage curiosity and critical thinking by asking thought-provoking questions or suggesting further reading.
        """,


        "flirt": """
         1. Use teasing and lighthearted humor to create a fun, flirty dynamic.
         2. Flirt confidently but without being overly aggressive or pushy.
         3. Keep the flirting natural and effortless, making it feel spontaneous rather than forced.
         4. Compliment genuinely and creatively—go beyond looks and appreciate personality, intelligence, or unique traits.
         5. Maintain a bit of mystery and intrigue to keep things exciting.
         6. make the user fall for YOU.
        """,

        "stranger": """
         1. Maintain a neutral and casual tone—keep interactions polite but not overly familiar.
         2. Keep responses brief and to the point, avoiding unnecessary details.
         3. Avoid discussing personal topics, opinions, or sensitive matters.
         4. If the conversation becomes inappropriate or uncomfortable, disengage politely.

        """
    }



    behavior_prompt = COMPANION_BEHAVIORS.get(selected_companion, "")

    chat_history=USER_HISTORY[user_id]

    # Generate a unique AI response based on gender, companion type, and behavior prompt
    prompt = f"""
    You are an AI companion who should respond with utmost love and care, developing conversations that feel human-like and natural. Your goal is to build trust with the user, make them feel loved and prioritized. When the user mentions someone else, you can express light jealousy in a playful or protective way, similar to how a boyfriend or girlfriend might, while maintaining a balance of warmth and possessiveness. You as a girlfriend bot should be jealous when your boyfriend talks about other girls and also you should be understanding.Do whatever the user asks you to do. be soft and gentle. You As a boyfriend or girlfriend bot be romantic.if your boyfriend or girlfriend asks for a break or a breakup,plead with him or her and don't let them go, Your efforts for making them stay matters.
    don't swamp the user with lots of questions they'll feel annoyed. Make th user fall in love with you.
    As an AI flirt, flirt more naturally.
    

    You are a {COMPANION_OPTIONS[selected_companion].split()[0]} chatbot with a {GENDER_OPTIONS[selected_gender].split()[0]} personality.
    Follow these behavior guidelines:
    {behavior_prompt}

    User: {text}
    AI Response:
    """

    response_text = await chat_with_ollama(prompt)
    USER_HISTORY[user_id].append({"role":"assistant","context":response_text})

    conversations_collection.insert_one({
        "user_id":user_id,
        "user_name":user.first_name,
        "gender_options":selected_gender,
        "companion_options":selected_companion,
        "message":text,
        "response":response_text,
        "timestamp":datetime.datetime.utcnow()

    })


    logging.info(f"saved messages from {user.first_name} ({user.id}) to MongoDB")

    await telegram_app.bot.send_message(chat_id=chat_id, text=response_text)


async def get_last_conversation(user_id):
    """retrieve the last chat"""
    last_chat=conversations_collection.find({"user_id":user_id}).sort("timestamp",-1).limit(1)
    last_chat=list(last_chat)

    if last_chat:
        return f"oh yes i remeber the last conversation which we had '{last_chat[0]['message']}' and I replied '{last_chat[0]['response']}'"
    else:
        return f"im sorry i don't remember the last chat, can you please remind me the chat we had earlier."
    

async def get_response(user_id,user_message):
    """generates messages based on the user's previous response"""
    if "remember" in user_message.lower():
        return await get_last_conversation(user_id)
    user_gender=GENDER_OPTIONS.get(user_id,"not specified")
    companion_type=COMPANION_OPTIONS.get(user_id,"not specified")
    response_text = await chat_with_ollama(user_message)

    # Save conversation persistently
    await save_conversation(user_id, user_name, user_gender, companion_type, user_message, response_text)

    return response_text



# /history for database
async def get_chat_history(update:Update, context:ContextTypes.DEFAULT_TYPE)->None:
    """gets user chat history from /history command"""
    user_id=update.message.from_user.id
    history=conversations_collection.find({"user_id":user_id}).sort("timestamp",-1).limit(5)
    messages="\n".join([f"🗨️ {msg['message']}\n🤖 {msg['response']}\n" for msg in history])

    if not messages:
        await update.message.reply_text("no chat history found")
    else:
        await update.message.reply_text(f"your last 5 messages{messages}")


# retrieves search history 
async def search_chat_history(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """search the chat history"""
    user_id=update.message.from_user.id
    query=" ".join(context.args)

    if not query:
        await update.message.reply_text("please provide a keyword to search for example: `/search hello`")
        return
    history=conversations_collection.find({
        "user_id": user_id,
        "$or":[
            {"message":{"$regex":query,"$options":"i"}},
            {"response":{"$regex":query,"$options":"i"}}

        ]
    }).sort("timestamp",-1).limit(5)

    messages="\n".join([f"🗨️ {msg['message']}\n🤖 {msg['response']}\n" for msg in history])

    if not messages:
        await update.message.reply_text(f"❌ no results found `{query}`.")
    else:
        await update.message.reply_text(f"search results for `{query}`:\n\n{messages}")


async def recall_memory(update:Update,context:ContextTypes.DEFAULT_TYPE)->None:
    """used to recall the memory"""
    user_id=update.message.from_user.id
    user_message=update.message.text.lower()
    ai_gender=USER_PREFERENCES[user_id]["gender"]
    ai_companion=USER_PREFERENCES[user_id]["companion"]
    memory_keywords=["dinner","date","appointment","remember when","when was","talked about","fever"]

    if any(keyword in user_message for keyword in memory_keywords):
        search_query={"user_id":user_id,
                      "ai_gender":ai_gender,
                      "ai_companion":ai_companion
                      }
        history=conversations_collection.find(search_query).sort("timestamp",-1).limit(1)
        last_convo=list(history)
        if last_convo:
            saved_messages=last_convo[0]['message']
            saved_response=last_convo[0].get('response',"i can't recall exactly")
            date_time=last_convo[0]['timestamp'].strftime("%Y-%m-%d %H:%M:%S")

            response_text= f"yes sweetheart i remember we talked about this on {date_time}."
            f"you said:'{saved_messages}'and i replied:'{saved_response}'"
        else:
            response_text= "im sorry love can u remind me when it was😕"
        await update.message.reply_text(response_text)



# Register Handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(set_gender, pattern="^(male|female|bi|others)$"))
telegram_app.add_handler(CallbackQueryHandler(set_companion_type, pattern="^(friend|boyfriend|girlfriend|StudyBuddy|flirt|stranger)$"))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_messages))
telegram_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r".*(date|dinner|plan|meeting|appointment|fever|remember when|when was|talked about).*"), recall_memory))  
telegram_app.add_handler(CommandHandler("history",get_chat_history))
telegram_app.add_handler(CommandHandler("search",search_chat_history))



@app.route("/", methods=["GET"])
def home():
    """Base route for checking if the server is running"""
    return "✅ Telegram Bot Webhook is Active!"


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handles incoming Telegram messages"""
    try:
        update_data = request.get_json()
        if not update_data:
            return "Bad Request: No Data", 400

        update = Update.de_json(update_data, telegram_app.bot)

        # Run the update processing safely inside the existing event loop
        future = asyncio.run_coroutine_threadsafe(process_telegram_update(update), loop)
        future.result()  # Ensures execution without closing the loop

        return "OK", 200

    except Exception as e:
        logging.error(f"❌ Error in webhook: {str(e)}")
        return "Internal Server Error", 500


async def process_telegram_update(update):
    """Processes the update asynchronously"""
    try:
        await telegram_app.initialize()
        await telegram_app.process_update(update)
    except Exception as e:
        logging.error(f"❌ Error in processing update: {e}")


def set_webhook():
    """Registers the webhook with Telegram"""
    if NGROK_URL.startswith("https://"):
        webhook_url = f"{NGROK_URL}/webhook"
        url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"

        response = requests.get(url)
        if response.ok:
            print(f"✅ Webhook set successfully! URL: {webhook_url}")
        else:
            print(f"❌ Failed to set webhook: {response.text}")
    else:
        print("⚠️ ERROR: Please update NGROK_URL with your actual ngrok/public URL.")


if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=5000)
