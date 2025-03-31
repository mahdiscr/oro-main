from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters
import re

# دیتابیس ساده برای ذخیره اطلاعات کاربران (فقط Mahdi و Nilo باقی می‌مانند)
user_profiles = {
    "7284988649532227585": {"name": "Mahdi", "category": "Leader", "mode": None, "achievements": ["🏆 قهرمان لیگ", "🏆 بهترین بازیکن"]},
    "7265369518667399169": {"name": "Nilo", "category": "Leader", "mode": None, "achievements": ["🏆 بهترین گلزن"]}
}

# اصلاح ساختار دیتابیس
competition_participants = {}  # {ثبت_کننده_id: {'participants': {user_id: name}, 'count': عدد}}
competition_settings = {
    "active": False,
    "max_participants": 10  # اضافه کردن تنظیمات جدید
}

# اضافه کردن مقدار پیشفرض برای کلیدهای ضروری
def safe_get_participants(registrant_id):
    if registrant_id not in competition_participants:
        competition_participants[registrant_id] = {
            "participants": {},
            "count": 0
        }
    return competition_participants[registrant_id]
news_banner = "📢 اخبار جدید کلن: به زودی رویداد ویژه‌ای برگزار می‌شود! آماده باشید! 🎉"

# کلاس برای مدیریت حالت‌های کاربران
class UserState:
    def __init__(self):
        self.states = {}

    def set_state(self, chat_id, state):
        self.states[chat_id] = state

    def get_state(self, chat_id):
        return self.states.get(chat_id)

    def clear_state(self, chat_id):
        if chat_id in self.states:
            del self.states[chat_id]

user_states = UserState()

# ذخیره message_id پیام‌های هر دسته در کانال
channel_messages = {}  # به‌صورت {category: message_id}

# آیدی کانال
CHANNEL_ID = "@oro_clan"  # جایگزین کنید با آیدی واقعی کانال

# تابع برای بررسی اعتبار یو‌آیدی
def is_valid_user_id(user_id):
    # یو‌آیدی فقط می‌تواند شامل حروف لاتین، اعداد و کاراکترهای خاص مانند _ باشد.
    pattern = r'^[a-zA-Z0-9_]+$'
    return re.match(pattern, user_id) is not None

# تابع برای ایجاد دکمه‌های شیشه‌ای برگشت به صفحه اصلی
def get_back_to_main_menu_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت به صفحه اصلی", callback_data='back_to_main')]])

def get_main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 اعضای کلن", callback_data='clan_members'),
         InlineKeyboardButton("🏆 مسابقه کلنی", callback_data='clan_competition')],
        [InlineKeyboardButton("📰 اخبار های کلن", callback_data='clan_news'),
         InlineKeyboardButton("👑 ادمین", callback_data='admin')]
    ])
def get_competition_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ثبت نام در مسابقه", callback_data='register_competition'),
         InlineKeyboardButton("🗑 حذف اسم من", callback_data='unregister_competition')],  # دکمه جدید
        [InlineKeyboardButton("📋 لیست شرکت کنندگان", callback_data='competition_participants')],
        [InlineKeyboardButton("🔙 برگشت به صفحه اصلی", callback_data='back_to_main')]
    ])

# تابع برای ایجاد منوی اعضای کلن
def get_clan_members_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 لیست اعضای کلن", callback_data='list_members')],
        [InlineKeyboardButton("📜 فهرست اعضای دسته یک", callback_data='list_category_1')],
        [InlineKeyboardButton("🔍 بررسی عضویت", callback_data='check_membership')],
        [InlineKeyboardButton("🔙 برگشت به صفحه اصلی", callback_data='back_to_main')]
    ])

# تابع برای ایجاد منوی ادمین
def get_admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ اضافه کردن کاربر", callback_data='add_user'),
         InlineKeyboardButton("➖ حذف کاربر", callback_data='remove_user')],
        [InlineKeyboardButton("🏆 مدیریت افتخارات", callback_data='manage_achievements')],
        [InlineKeyboardButton("📢 تنظیم بنر اخبار", callback_data='set_news_banner'),
         InlineKeyboardButton("⚙️ مدیریت مسابقه", callback_data='manage_competition')],
        [InlineKeyboardButton("📤 اپلود همگانی", callback_data='bulk_upload')],
        [InlineKeyboardButton("🔙 برگشت", callback_data='back_to_main')]
    ])
def get_competition_admin_menu():
    status_icon = "✅ فعال" if competition_settings["active"] else "❌ غیرفعال"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"وضعیت مسابقه: {status_icon}", callback_data='toggle_competition_status')],
        [InlineKeyboardButton("🧹 پاکسازی لیست شرکت کنندگان", callback_data='clear_competition_list')],
        [InlineKeyboardButton("🔄 اعمال تغییرات", callback_data='confirm_competition_changes')],
        [InlineKeyboardButton("🔙 بازگشت به منوی ادمین", callback_data='back_to_admin')]
    ])
def get_back_to_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 برگشت به منوی ادمین", callback_data='back_to_admin')]
    ])

# تابع برای ارسال صفحه اصلی
async def send_main_menu(update: Update, context: CallbackContext, message: str = None):
    welcome_message = (
        message or "🌟 **سلام! به ربات کلن oro خوش آمدید.** 🌟\n\n"
        "ما اینجا هستیم تا تجربه‌ی بهتری از مدیریت و تعامل با کلن براتون فراهم کنیم.\n\n"
        "لطفا یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    if update.message:
        await update.message.reply_text(welcome_message, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(welcome_message, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

# تابع برای ارسال یا ادیت لیست دسته‌بندی‌ها در کانال
async def update_channel_members_list(context: CallbackContext):
    global channel_messages

    # ایجاد لیست دسته‌بندی‌ها
    categories = {}
    leaders = []  # لیست لیدرها

    # جمع‌آوری اعضا بر اساس دسته‌بندی
    for user_id, user in user_profiles.items():
        category = user['category']
        if category == "Leader":
            leaders.append(f"👑 {user['name']} ({user_id})")
        else:
            if category not in categories:
                categories[category] = []
            # اگر دسته یک باشد، دستاوردها را اضافه کنید
            if category == "1":
                achievements = "🏆 " + ", ".join(user['achievements']) if user['achievements'] else "🛑 بدون دستاورد"
                categories[category].append(f"👤 {user['name']} ({user_id})\n{achievements}")
            else:
                # برای سایر دسته‌ها فقط نام و یو‌آیدی نمایش داده شود
                categories[category].append(f"👤 {user['name']} ({user_id})")

    # ارسال یا ادیت پیام‌ها برای هر دسته (حتی دسته‌های خالی)
    all_categories = {"1", "2", "3", "4", "5"}  # دسته‌های یک تا پنج
    for category in sorted(all_categories):
        if category in categories:
            members = categories[category]
            message_text = f"🌟 **دسته {category}:**\n\n"
            message_text += "\n".join(members)
        else:
            message_text = f"🌟 **دسته {category}:**\n\n🛑 هیچ عضوی وجود ندارد."

        if category in channel_messages:
            # اگر پیام قبلی وجود دارد، آن را ادیت کنید
            try:
                await context.bot.edit_message_text(
                    chat_id=CHANNEL_ID,
                    message_id=channel_messages[category],
                    text=message_text,
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"خطا در ادیت پیام برای دسته {category}: {e}")
        else:
            # اگر پیام قبلی وجود ندارد، پیام جدید ارسال کنید و message_id را ذخیره کنید
            sent_message = await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message_text,
                parse_mode="Markdown"
            )
            channel_messages[category] = sent_message.message_id

    # ارسال یا ادیت پیام برای لیدرها
    if leaders:
        message_text = "👑 **لیست لیدرها:**\n\n"
        message_text += "\n".join(leaders)
    else:
        message_text = "👑 **لیست لیدرها:**\n\n🛑 هیچ لیدری وجود ندارد."

    if "Leader" in channel_messages:
        # اگر پیام قبلی وجود دارد، آن را ادیت کنید
        try:
            await context.bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=channel_messages["Leader"],
                text=message_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"خطا در ادیت پیام برای لیدرها: {e}")
    else:
        # اگر پیام قبلی وجود ندارد، پیام جدید ارسال کنید و message_id را ذخیره کنید
        sent_message = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=message_text,
            parse_mode="Markdown"
        )
        channel_messages["Leader"] = sent_message.message_id# دستور /start
async def start(update: Update, context: CallbackContext) -> None:
    await send_main_menu(update, context)
    user_states.set_state(update.message.chat_id, "ASK_ROLE")

async def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    # پردازش دکمه‌های ادمین
    if data == 'add_user':
        await query.edit_message_text("لطفا یوآیدی کاربر جدید را وارد کنید:")
        user_states.set_state(chat_id, "ADD_USER_ID")

    elif data == 'remove_user':
        await query.edit_message_text("لطفا یوآیدی کاربر برای حذف وارد کنید:")
        user_states.set_state(chat_id, "REMOVE_USER_ID")

    # بقیه دکمه‌ها...
    elif data == 'manage_achievements':
        await query.edit_message_text("لطفا یوآیدی کاربر را وارد کنید:")
        user_states.set_state(chat_id, "MANAGE_ACHIEVEMENTS_USER_ID")

    elif data == 'set_news_banner':
        await query.edit_message_text("لطفا متن جدید بنر اخبار را وارد کنید:")
        user_states.set_state(chat_id, "SET_NEWS_BANNER")

    elif data == 'manage_competition':
        status = "✅ فعال" if competition_settings["active"] else "❌ غیرفعال"
        await query.edit_message_text(
            f"⚙️ مدیریت مسابقه\nوضعیت: {status}",
            reply_markup=get_competition_admin_menu()
        )

    elif data == 'bulk_upload':
        await query.edit_message_text("لطفا رمز عبور ویژه را وارد کنید:")
        user_states.set_state(chat_id, "BULK_UPLOAD_PASSWORD")

    # بقیه دکمه‌ها...

    # بخش جدید: مدیریت حذف ثبت نام
    if data == 'unregister_competition':
        if not competition_settings["active"]:
            await query.edit_message_text("⛔ مسابقه غیرفعال است!", reply_markup=get_back_to_main_menu_keyboard())
            return
        
        await query.edit_message_text(
            "❌ لطفا یوآیدی خود را برای حذف ثبت نام وارد کنید:",
            reply_markup=get_back_to_main_menu_keyboard()
        )
        user_states.set_state(chat_id, "UNREGISTER_COMPETITION")
    # بخش جدید: مدیریت ثبت نام مسابقه
    if data == 'register_competition':
        if not competition_settings["active"]:
            await query.edit_message_text("⛔ مسابقه فعلاً غیرفعال است!", reply_markup=get_back_to_main_menu_keyboard())
            return
        
        await query.edit_message_text(
            "🏆 لطفا یوآیدی خود را برای ثبت نام وارد کنید:",
            reply_markup=get_back_to_main_menu_keyboard()
        )
        user_states.set_state(chat_id, "REGISTER_COMPETITION")  # این خط حیاتی است

    # مدیریت کلیک روی دکمه ادمین
    if data == "admin":
        user_states.set_state(chat_id, "ADMIN_PASSWORD")  # پاکسازی حالت‌های قبلی
        await query.edit_message_text(
            "🔐 لطفا رمز عبور ادمین را وارد کنید:",
            reply_markup=get_back_to_main_menu_keyboard()
        )
    if data.startswith('category_'):
            # اعتبارسنجی دسته (1-5)
            category_number = data.split('_')[1]
            if category_number not in {'1', '2', '3', '4', '5'}:
                await query.answer("⚠️ شماره دسته نامعتبر!", show_alert=True)
                return

            # دریافت اطلاعات موقت کاربر
            temp_data = context.user_data.get('temp_user')
            if not temp_data:
                await query.edit_message_text("⛔ خطا: اطلاعات کاربر یافت نشد!")
                return

                        # نسخه اصلاح شده
            user_profiles[temp_data['user_id']] = {  # <- براکت بسته ] اضافه شد
                'name': temp_data['name'],
                'category': category_number,
                'achievements': [],
                'mode': None
}
            # ارسال پیام موفقیت
            await query.edit_message_text(
                f"✅ کاربر با موفقیت ثبت شد!\n"
                f"├ یوآیدی: `{temp_data['user_id']}`\n"
                f"├ نام: {temp_data['name']}\n"
                f"└ دسته: {category_number}",
                parse_mode="Markdown",
                reply_markup=get_admin_menu_keyboard()
            )

            # پاکسازی حالت‌ها
            user_states.clear_state(chat_id)
            context.user_data.pop('temp_user', None)
            return
    # مدیریت برگشت به منوی اصلی
    if data == "back_to_main":
        await send_main_menu(update, context)
        user_states.set_state(chat_id, "ASK_ROLE")
        return

    state = user_states.get_state(chat_id)

    # -------------------- حالت اصلی --------------------
    if state == "ASK_ROLE":
        if data == "clan_members":
            await query.edit_message_text(
                "لطفا یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=get_clan_members_menu_keyboard()
            )
            user_states.set_state(chat_id, "CLAN_MEMBERS_MENU")

        elif data == "clan_competition":
            if not competition_settings["active"]:
                await query.edit_message_text(
                    "⏳ مسابقه فعلاً غیرفعال است!وقتی بنر مسابقه بعدی گذاشته شد این بخش فعال میشود",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 برگشت", callback_data='back_to_main')]
                    ])
                )
                return

            await query.edit_message_text(
                "🏆 مسابقه فعال کلنی - گزینه مورد نظر را انتخاب کنید:",
                reply_markup=get_competition_menu_keyboard()
            )
            user_states.set_state(chat_id, "COMPETITION_MENU")

        elif data == "clan_news":
            await query.edit_message_text(
                news_banner,
                reply_markup=get_back_to_main_menu_keyboard()
            )
            user_states.clear_state(chat_id)

    # -------------------- مدیریت مسابقه --------------------
    elif data == "manage_competition":
        await query.edit_message_text(
            "⚙️ **تنظیمات مسابقه کلنی**\n"
            "از گزینه‌های زیر برای مدیریت استفاده کنید:",
            reply_markup=get_competition_admin_menu(),
            parse_mode="Markdown"
        )

    elif data == "toggle_competition_status":
        competition_settings["active"] = not competition_settings["active"]
        await query.edit_message_reply_markup(
            reply_markup=get_competition_admin_menu()
        )

    elif data == "clear_competition_list":
        competition_settings["participants"] = {}
        await query.answer("♻️ لیست شرکت کنندگان با موفقیت پاکسازی شد!", show_alert=True)

    elif data == "confirm_competition_changes":
        await query.edit_message_text(
            "✅ تنظیمات جدید با موفقیت اعمال شد!",
            reply_markup=get_admin_menu_keyboard()
        )
        user_states.set_state(chat_id, "ADMIN_MENU")

    elif data == "back_to_admin":
        await query.edit_message_text(
            "منوی مدیریت ادمین:",
            reply_markup=get_admin_menu_keyboard()
        )

    # -------------------- لیست شرکت کنندگان --------------------
    elif data == "competition_participants":
        participants = competition_settings["participants"]

        if not participants:
            await query.edit_message_text(
                "📭 لیست شرکت کنندگان خالی است!",
                reply_markup=get_competition_menu_keyboard()
            )
            return

        participants_list = []
        for user_id, name in participants.items():
            participants_list.append(f"• {name} ({user_id})")

        await query.edit_message_text(
            "🔢 لیست شرکت کنندگان:\n" + "\n".join(participants_list),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 برگشت", callback_data='back_to_competition')]
            ])
        )
    elif data == "back_to_competition":
        await query.edit_message_text(
            "🏆 مسابقه فعال کلنی - گزینه مورد نظر را انتخاب کنید:",
            reply_markup=get_competition_menu_keyboard()
        )
        user_states.set_state(chat_id, "COMPETITION_MENU")

    # مدیریت کپی یوآیدی
    elif data.startswith("copy_id:"):
        user_id = data.split(":")[1]
        await query.answer(f"📋 یوآیدی کپی شد: {user_id}", show_alert=True)
        context.user_data['copied_id'] = user_id
        
    if state == "ASK_ROLE":
        if data == "clan_members":
            await query.edit_message_text("لطفا یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=get_clan_members_menu_keyboard())
            user_states.set_state(chat_id, "CLAN_MEMBERS_MENU")
        elif data == "clan_news":
            await query.edit_message_text(news_banner, reply_markup=get_back_to_main_menu_keyboard())
            user_states.clear_state(chat_id)
        elif data == "admin":
            await query.edit_message_text("لطفا رمز عبور ادمین را وارد کنید:", reply_markup=get_back_to_main_menu_keyboard())
            user_states.set_state(chat_id, "ADMIN_PASSWORD")
        
    elif state == "CLAN_MEMBERS_MENU":
        if data == "list_members":
            members_list = "\n".join([
                "👤 نام: {} \n🆔 یو‌آیدی: {} \n🔹 دسته: {}\n".format(
                    user['name'],
                    user_id,
                    'Leader' if user['category'] == 'Leader' else f'دسته {user["category"]}'
                )
                for user_id, user in user_profiles.items()
            ])
            await query.edit_message_text(f"📋 **لیست اعضای کلن:**\n\n{members_list}", reply_markup=get_back_to_main_menu_keyboard())
            user_states.clear_state(chat_id)
        elif data == "list_category_1":
            category_1_members = [
                "👤 نام: {} \n🆔 یو‌آیدی: {} \n🏆 افتخارات: {}\n".format(
                    user['name'],
                    user_id,
                    ', '.join(user['achievements']) if user['achievements'] else 'بدون افتخار'
                )
                for user_id, user in user_profiles.items() if user['category'] == "1"
            ]
            if category_1_members:
                await query.edit_message_text(
                    "📋 **فهرست اعضای دسته یک:**\n\n" + "\n".join(category_1_members),
                    reply_markup=get_back_to_main_menu_keyboard(),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("⚠️ هیچ عضوی در دسته یک وجود ندارد.", reply_markup=get_back_to_main_menu_keyboard())
            user_states.clear_state(chat_id)
        elif data == "check_membership":
            await query.edit_message_text("لطفا یو‌آیدی خود را وارد کنید:", reply_markup=get_back_to_main_menu_keyboard())
            user_states.set_state(chat_id, "USER_CHECK_MEMBERSHIP")
            
# پردازش پیام‌های متنی
async def handle_message(update: Update, context: CallbackContext) -> None:
    user_input = update.message.text.strip()
    chat_id = update.message.chat_id
    state = user_states.get_state(chat_id)

    # بخش احراز هویت ادمین
    if state == "ADMIN_PASSWORD":
        if user_input == "nilmah":  # رمز عبور اینجا بررسی می‌شود
            await update.message.reply_text(
                "✅ احراز هویت موفق!",
                reply_markup=get_admin_menu_keyboard()  # نمایش منوی ادمین
            )
            user_states.set_state(chat_id, "ADMIN_MENU")  # تنظیم حالت ادمین
        else:
            await update.message.reply_text("❌ رمز عبور اشتباه است!")
            user_states.clear_state(chat_id)
            
    # --- بخش ثبت نام کاربر جدید ---
    if state == "ADD_USER_ID":
        # اعتبارسنجی یوآیدی
        if not re.match(r'^[a-zA-Z0-9_]{5,20}$', user_input):  # الگوی بهبود یافته
            await update.message.reply_text(
                "⚠️ یوآیدی نامعتبر!\n"
                "فقط حروف لاتین، اعداد و _ مجازند (5 تا 20 کاراکتر)",
                reply_markup=get_back_to_admin_keyboard()
            )
            return

        if user_input in user_profiles:
            await update.message.reply_text("⚠️ این یوآیدی از قبل وجود دارد!")
            return

        await update.message.reply_text("✅ یوآیدی معتبر!\nلطفا نام کامل کاربر را وارد کنید:")
        user_states.set_state(chat_id, f"ADD_USER_NAME:{user_input}")  # ذخیره یوآیدی در حالت

    elif state and state.startswith("ADD_USER_NAME:"):
        # استخراج یوآیدی از حالت
        user_id = state.split(":")[1]
        
        # اعتبارسنجی نام (حداقل 3 کاراکتر)
        if len(user_input) < 3 or any(char.isdigit() for char in user_input):
            await update.message.reply_text("⚠️ نام باید حداقل 3 کاراکتر و بدون عدد باشد!")
            return

        # ایجاد منوی انتخاب دسته
        keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("دسته 1️⃣", callback_data='category_1'),
         InlineKeyboardButton("دسته 2️⃣", callback_data='category_2')],
        [InlineKeyboardButton("دسته 3️⃣", callback_data='category_3'),
         InlineKeyboardButton("دسته 4️⃣", callback_data='category_4')],
        [InlineKeyboardButton("دسته 5️⃣", callback_data='category_5')]
    ])
    
    await update.message.reply_text(
        "🔢 لطفا شماره دسته کاربر را انتخاب کنید (1 تا 5):",
        reply_markup=keyboard
    )
    # ذخیره اطلاعات موقت
    context.user_data['temp_user'] = {
        'user_id': user_id,
        'name': user_input
    }
    user_states.set_state(chat_id, "ADD_USER_CATEGORY")

    # --- پردازش انتخاب دسته از طریق دکمه ---
    async def button_click(update: Update, context: CallbackContext) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data.startswith('category_'):
            temp_data = context.user_data.get('temp_user', {})
            if not temp_data:
                await query.edit_message_text("⚠️ خطا در پردازش اطلاعات!")
                return

            # ثبت نهایی کاربر
            user_profiles[temp_data['user_id']] = {  # <- اضافه کردن ] قبل از =
    'name': temp_data['name'],
    'category': data.split('_')[1],
    'achievements': [],
    'mode': None
}
            
            await query.edit_message_text(
                f"✅ کاربر با موفقیت ثبت شد!\n"
                f"▪️ یوآیدی: {temp_data['user_id']}\n"
                f"▪️ نام: {temp_data['name']}\n"
                f"▪️ دسته: {data.split('_')[1]}",
                reply_markup=get_admin_menu_keyboard()
            )
            user_states.clear_state(query.message.chat_id)
            context.user_data.pop('temp_user', None)
    if state == "REGISTER_COMPETITION":
        # بررسی فعال بودن مسابقه
        if not competition_settings["active"]:
            await update.message.reply_text("⛔ مسابقه غیرفعال است!")
            user_states.clear_state(update.message.chat_id)
            return

        # اعتبارسنجی یوآیدی
        if not is_valid_user_id(user_input):
            await update.message.reply_text("⚠️ یوآیدی نامعتبر!")
            return

        # بررسی وجود کاربر در سیستم
        if user_input not in user_profiles:
            await update.message.reply_text("⚠️ این کاربر در سیستم وجود ندارد!")
            return

        # 4. جلوگیری از ثبت نام تکراری
        if user_input in competition_settings["participants"]:
            await update.message.reply_text("⚠️ شما قبلاً ثبت نام کرده اید!")
            return
        
        # ثبت کاربر جدید توسط ثبت‌کننده
        if user_id not in competition_participants:
            competition_participants[user_id] = {
                "participants": {},
                "count": 0
            }

        if user_input in competition_participants[user_id]["participants"]:
            await update.message.reply_text("⚠️ این کاربر قبلاً ثبت‌نام شده!")
            return

        competition_participants[user_id]["participants"][user_input] = user_profiles[user_input]["name"]
        competition_participants[user_id]["count"] += 1

        await update.message.reply_text(
            f"✅ کاربر {user_input} با موفقیت ثبت‌نام شد!\n"
            f"تعداد ثبت‌نام‌های شما: {competition_participants[user_id]['count']}",
            reply_markup=get_back_to_admin_keyboard()
        )
        user_states.clear_state(update.message.chat_id)

    # بخش جدید: حذف ثبت نام
    if state == "UNREGISTER_COMPETITION":
        # بررسی فعال بودن مسابقه
        if not competition_settings["active"]:
            await update.message.reply_text("⛔ مسابقه غیرفعال است!")
            user_states.clear_state(chat_id)
            return

        # اعتبارسنجی یوآیدی
        if not is_valid_user_id(user_input):
            await update.message.reply_text("⚠️ یوآیدی نامعتبر!")
            return

        # بررسی وجود کاربر در لیست شرکت کنندگان
        if user_input not in competition_settings["participants"]:
            await update.message.reply_text("⚠️ شما در مسابقه ثبت نام نکرده اید!")
            return

        # حذف کاربر
        del competition_settings["participants"][user_input]
        await update.message.reply_text(
            "✅ ثبت نام شما با موفقیت حذف شد!",
            reply_markup=get_back_to_admin_keyboard()
        )
        user_states.clear_state(chat_id)

    # ---------- حالت ورود رمز ادمین (اولین شرط) ----------
    if state == "ADMIN_PASSWORD":
        if user_input == "nilmah":
            await update.message.reply_text("احراز هویت موفق!\nلطفا انتخاب کنید:", reply_markup=get_admin_menu_keyboard())
            user_states.set_state(chat_id, "ADMIN_MENU")
            
        else:
            await update.message.reply_text(
                "❌ رمز عبور اشتباه است!",
                reply_markup=get_back_to_main_menu_keyboard()
            )
            user_states.clear_state(chat_id)

    elif state == "USER_CHECK_MEMBERSHIP":
        if not is_valid_user_id(user_input):
            await update.message.reply_text("⚠️ یو‌آیدی نامعتبر است! فقط از حروف لاتین، اعداد و _ استفاده کنید.", reply_markup=get_back_to_main_menu_keyboard())
            return

        if user_input in user_profiles:
            profile = user_profiles[user_input]
            mode_text = "\nحالت: {}".format(profile['mode']) if profile['mode'] else ""
            achievements_text = "\n🏆 افتخارات: " + ", ".join(profile['achievements']) if profile['achievements'] else ""
            await update.message.reply_text(
                "✅ **عضویت تایید شد!**\n\n"
                "👤 نام: {}\n"
                "🆔 یو‌آیدی: {}\n"
                "🔹 دسته: {}{}{}".format(
                    profile['name'],
                    user_input,
                    profile['category'],
                    mode_text,
                    achievements_text
                ),
                reply_markup=get_back_to_main_menu_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ یو‌آیدی وارد شده در سیستم وجود ندارد.", reply_markup=get_back_to_main_menu_keyboard())
        user_states.clear_state(chat_id)

    elif state == "REMOVE_USER_ID":
        if not is_valid_user_id(user_input):
            await update.message.reply_text("⚠️ یو‌آیدی نامعتبر است! فقط از حروف لاتین، اعداد و _ استفاده کنید.", reply_markup=get_back_to_main_menu_keyboard())
            return

        if user_input in user_profiles:
            del user_profiles[user_input]
            await update.message.reply_text(f"✅ کاربر با یو‌آیدی {user_input} حذف شد.", reply_markup=get_back_to_main_menu_keyboard())
        else:
            await update.message.reply_text("⚠️ یو‌آیدی وارد شده در سیستم وجود ندارد!", reply_markup=get_back_to_main_menu_keyboard())
        user_states.clear_state(chat_id)
        await update_channel_members_list(context)  # به‌روزرسانی لیست در کانال

    elif state == "SET_NEWS_BANNER":
        global news_banner
        news_banner = user_input
        await update.message.reply_text("✅ بنر اخبار با موفقیت به‌روزرسانی شد!", reply_markup=get_back_to_main_menu_keyboard())
        user_states.clear_state(chat_id)

    # -------------------- مدیریت دستاوردها (بخش جدید) --------------------
    elif state == "MANAGE_ACHIEVEMENTS_USER_ID":
        if user_input in user_profiles:
            # ذخیره یو‌آیدی کاربر در context برای استفاده در مراحل بعد
            context.user_data['manage_achievements_user_id'] = user_input
            await update.message.reply_text(
                "✅ کاربر یافت شد!\nلطفا دستاورد جدید را وارد کنید (دستاوردهای قبلی جایگزین خواهند شد):",
                reply_markup=get_back_to_main_menu_keyboard()
            )
            user_states.set_state(chat_id, "MANAGE_ACHIEVEMENTS_NEW")
        else:
            await update.message.reply_text("⚠️ کاربری با این یو‌آیدی یافت نشد!", reply_markup=get_back_to_main_menu_keyboard())
            user_states.clear_state(chat_id)

    elif state == "MANAGE_ACHIEVEMENTS_NEW":
        user_id = context.user_data.get('manage_achievements_user_id')
        if user_id and user_id in user_profiles:
            # جایگزینی کامل دستاوردهای قبلی با دستاورد جدید
            user_profiles[user_id]["achievements"] = [user_input.strip()]
            await update.message.reply_text(
                f"✅ دستاوردهای کاربر با یو‌آیدی {user_id} به‌روزرسانی شد!\n"
                f"دستاورد جدید: {user_input}",
                reply_markup=get_back_to_main_menu_keyboard()
            )
            await update_channel_members_list(context)  # به‌روزرسانی لیست در کانال
        else:
            await update.message.reply_text("⚠️ خطا در به‌روزرسانی دستاوردها!", reply_markup=get_back_to_main_menu_keyboard())
        user_states.clear_state(chat_id)
        context.user_data.pop('manage_achievements_user_id', None)  # پاک کردن داده موقت
    # -------------------- پایان بخش مدیریت دستاوردها --------------------

    elif state == "BULK_UPLOAD_PASSWORD":
        if user_input == "Mahdiamam":
            await update.message.reply_text("احراز هویت موفق!\nلطفا فهرست اعضای جدید را به فرمت زیر ارسال کنید (هر عضو در یک خط):\nیو‌آیدی.نام کاربر.دسته کاربر\nمثال:\n123.test1.2\n124.test2.3", reply_markup=get_back_to_main_menu_keyboard())
            user_states.set_state(chat_id, "BULK_UPLOAD")
        else:
            await update.message.reply_text("رمز عبور اشتباه است!", reply_markup=get_back_to_main_menu_keyboard())
            user_states.clear_state(chat_id)

    elif state == "BULK_UPLOAD":
        lines = user_input.split("\n")
        added_users = []
        for line in lines:
            try:
                user_id, name, category = line.strip().split(".")
                if not is_valid_user_id(user_id):
                    await update.message.reply_text(f"⚠️ یو‌آیدی نامعتبر در خط: {line}", reply_markup=get_back_to_main_menu_keyboard())
                    continue

                if user_id not in user_profiles:
                    user_profiles[user_id] = {"name": name, "category": category, "mode": None, "achievements": []}
                    added_users.append(f"{user_id}: {name} ({category})")
                else:
                    await update.message.reply_text(f"⚠️ کاربر با یو‌آیدی {user_id} از قبل وجود دارد.", reply_markup=get_back_to_main_menu_keyboard())
            except ValueError:
                await update.message.reply_text(f"⚠️ خطا در پردازش خط: {line}", reply_markup=get_back_to_main_menu_keyboard())

        if added_users:
            await update.message.reply_text(
                "✅ اعضای زیر با موفقیت اضافه شدند:\n" + "\n".join(added_users),
                reply_markup=get_back_to_main_menu_keyboard()
            )
        else:
            await update.message.reply_text("⚠️ هیچ عضو جدیدی اضافه نشد.", reply_markup=get_back_to_main_menu_keyboard())
        user_states.clear_state(chat_id)
        await update_channel_members_list(context)  # به‌روزرسانی لیست در کانال

# تابع اصلی
def main() -> None:
    application = Application.builder().token("7565549970:AAFpSTTeII1KoqMdlTe8ZRblZDlMv2P8Erg").build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("ربات فعال شد و در حال گوش دادن به پیام‌ها است...")
    application.run_polling()

if __name__ == '__main__':
    main()