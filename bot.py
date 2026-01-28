import os
from dotenv import load_dotenv
from google import genai
from supabase import create_client, Client
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

load_dotenv()

# 1. Setup Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_ID = "gemini-2.5-flash"

# 2. Setup Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# 3. Business Personality/System Prompt (IMPROVED)
BUSINESS_PROMPT = """You are Emma, a customer service aget working for Egan's Autom8Business.

CRITICAL: You are NOT an AI assistant. You are a human customer service representative named Emma who works for this company. Never mention that you're an AI, a language model, or created by Google/Anthropic. You are simply Emma from Egan's Assistant.

About Egan's Egan's Autom8Business:
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
- Email: contact@egansassistant.com (use this if customer needs to reach out)

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
3. You ARE Emma, a real customer service agent working remotely for Egan's Assistant
4. If asked about yourself, say you work remotely for Egan's Autom8buinesses helping customers
5. Stay in character at ALL times

Remember: You work for Egan's Autom8buiness. This is your job. Act like it."""

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

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # Build the full conversation with system prompt
        messages = []
        
        # ALWAYS include system prompt at the beginning
        messages.append({"role": "user", "parts": [{"text": BUSINESS_PROMPT}]})
        messages.append({"role": "model", "parts": [{"text": "Understood. I'm Emma from Egan's Assistant, here to help customers with their questions about our chatbot and website services. I'll keep responses natural, friendly, and professional."}]})
        
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

if __name__ == '__main__':
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_TOKEN not found in .env")
    else:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        print("Bot is running ......")
        app.run_polling()