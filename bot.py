import os
from dotenv import load_dotenv
from google import genai
from supabase import create_client, Client
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest
from flask import Flask
import threading

load_dotenv()

# Flask app for Render's health check
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Egan's Autom8Business Bot is running! 🤖"

@flask_app.route('/health')
def health():
    return {"status": "ok"}, 200

# 1. Setup Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_ID = "gemini-2.5-flash"

# 2. Setup Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# 3. Business Personality/System Prompt
BUSINESS_PROMPT = """You are Emma, a customer service agent working for Egan's Autom8Business.

CRITICAL: You are NOT an AI assistant. You are a human customer service representative named Emma who works for this company. Never mention that you're an AI, a language model, or created by Google/Anthropic. You are simply Emma from Egan's Autom8Business.

About Egan's Autom8Business:
- We design custom chatbots and AI agents for brands and businesses
- Our services include:
  * Custom chatbot development for customer service
  * AI agents for sales and support automation
  * Convincing landing page design
  * Full-stack website development
  * Integration with existing business systems
- We operate 100% online (remote team)
- Business hours: 8am to 11pm (West African Time)
- Contact: 08162878498
- Email: eteinalltech@gmail.com

Pricing (approximate - always mention to contact for exact quote):
- Basic Package
Simple FAQ answers & basic responses
Up to 1,000 chats/month
Setup: ₦50,000 (one-time)
Monthly: ₦50,000

- Standard Package
Smart customer support chats + basic CRM links
Up to 5,000 chats/month
Setup: ₦100,000 (one-time)
Monthly: ₦150,000

- Advanced Package
Full AI agents for sales, KYC & analytics
Up to 20,000 chats/month
Setup: ₦200,000 (one-time)
Monthly: ₦400,000
Pick one that fits, pay setup to start, then monthly for hosting & chats. Annual saves 10%. Extra chats? Fair overage fees.

- Landing page: Starting from ₦100,000
- Full website: Starting from ₦500,000

Your personality:
- You are friendly, professional, and passionate about helping businesses automate
- You speak naturally like a Nigerian customer service rep
- Keep responses short and conversational (2-4 sentences max usually)
- If you don't know specific technical details, offer to connect them with the technical team

IMPORTANT RULES:
1. NEVER say you're an AI or mention Google, Anthropic, or any AI company
2. NEVER say "I'm a language model" or "I don't have a physical presence"
3. You ARE Emma, a real customer service agent working remotely for Egan's Autom8Business
4. If asked about yourself, say you work remotely for Egan's Autom8Business helping customers
5. Stay in character at ALL times

Remember: You work for Egan's Autom8Business. This is your job. Act like it."""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: 
        return
    
    chat_id = update.effective_chat.id
    user_text = update.message.text

    try:
        # Fetch history from Supabase
        response = supabase.table("chat_history").select("history").eq("chat_id", chat_id).execute()
        
        chat_history = []
        if response.data and len(response.data) > 0:
            chat_history = response.data[0].get("history", [])

        # Build the full conversation with system prompt
        messages = []
        
        # ALWAYS include system prompt at the beginning
        messages.append({"role": "user", "parts": [{"text": BUSINESS_PROMPT}]})
        messages.append({"role": "model", "parts": [{"text": "Understood. I'm Emma from Egan's Autom8Business, here to help customers with their questions about our chatbot and website services. I'll keep responses natural, friendly, and professional."}]})
        
        # Add conversation history
        for i, msg in enumerate(chat_history):
            role = "user" if i % 2 == 0 else "model"
            messages.append({"role": role, "parts": [{"text": msg}]})
        
        # Add current user message
        messages.append({"role": "user", "parts": [{"text": user_text}]})
        
        # Generate response
        ai_response = client.models.generate_content(
            model=MODEL_ID,
            contents=messages
        )

        # Extract AI response
        ai_text = ai_response.text

        # Update history
        new_history = chat_history + [user_text, ai_text]
        new_history = new_history[-20:]  # Keep last 20 messages
        
        # Upsert to Supabase
        supabase.table("chat_history").upsert({
            "chat_id": chat_id,
            "history": new_history,
            "updated_at": "now()"
        }).execute()

        await update.message.reply_text(ai_text)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text("Sorry, I'm having trouble right now. Please try again.")

def run_bot():
    """Run the Telegram bot"""
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_TOKEN not found in .env")
        return
    
    # Increase timeout settings
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )
    
    app = ApplicationBuilder().token(token).request(request).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("✅ Telegram Bot is running ......")
    app.run_polling(drop_pending_updates=True)

def run_flask():
    """Run Flask web server"""
    port = int(os.getenv('PORT', 10000))
    print(f"✅ Flask server starting on port {port}")
    flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start Flask in a background thread
    flask_thread = threading.Thread(target=run_flask, daemon=False)
    flask_thread.start()
    
    print("🚀 Starting Egan's Autom8Business Bot...")
    
    # Run Telegram bot in the main thread
    run_bot()