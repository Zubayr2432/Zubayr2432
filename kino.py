import asyncio
import os
import logging
import sqlite3
from aiogram import types
from aiohttp import web
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, ForceReply, InputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from datetime import datetime

# Sozlashlar
class Config:
    CHANNEL_USERNAME = "ajoyib_kino_kodlari1"
    CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME}"
    CHANNEL_ID = -1002341118048
    
    CHANNEL_USERNAME_sh = "maxfiy_kino_kanal"
    CHANNEL_LINK_sh = f"https://t.me/{CHANNEL_USERNAME_sh}"
    CHANNEL_ID_sh = -1002537276349
    
    BOT_TOKEN = "7808158374:AAGMY8mkb0HVi--N2aJyRrPxrjotI6rnm7k"
    ADMIN_IDS = [7871012050, 7183540853]

import logging

# Logger sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# Bot obyektlari
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher()

# Foydalanuvchilar ma'lumotlari
user_data = set()  # Ro'yxatdan o'tgan foydalanuvchilar ID lari

# Holatlar
class AdminState(StatesGroup):
    waiting_for_code = State()    # Kino kodi kutilmoqda
    waiting_for_name = State()    # Kino nomi kutilmoqda
    waiting_for_file = State()    # Kino fayli kutilmoqda
    send_ad = State()             # Reklama matni kutilmoqda
    contact_admin = State()       # Admin bilan aloqa xabari kutilmoqda
    waiting_for_movie_code_to_delete = State()  # O'chirish uchun kod kutilmoqda

# Ma'lumotlar bazasi
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('movies.db')
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS kinolar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kod INTEGER UNIQUE,
                nomi TEXT,
                file_id TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def add_user(self, user_id, full_name, username):
        self.execute(
            """INSERT OR IGNORE INTO users (user_id, full_name, username) 
            VALUES (?, ?, ?)""",
            (user_id, full_name, username),
            commit=True
        )
    
    def update_user_activity(self, user_id):
        self.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
            commit=True
        )
    
    def get_movie_by_code(self, code):
        return self.cursor.execute(
            "SELECT nomi, file_id FROM kinolar WHERE kod = ?", 
            (code,)
        ).fetchone()
    
    def add_movie(self, code, name, file_id):
        return self.execute(
            "INSERT INTO kinolar (kod, nomi, file_id) VALUES (?, ?, ?)",
            (code, name, file_id),
            commit=True
        )
    
    def delete_movie(self, code):
        return self.execute(
            "DELETE FROM kinolar WHERE kod = ?",
            (code,),
            commit=True
        )
    
    def get_stats(self):
        total_users = self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = self.cursor.execute(
            "SELECT COUNT(*) FROM users WHERE last_active > datetime('now', '-30 days')"
        ).fetchone()[0]
        total_movies = self.cursor.execute("SELECT COUNT(*) FROM kinolar").fetchone()[0]
        return total_users, active_users, total_movies
    
    def get_all_users(self):
        return self.cursor.execute("SELECT user_id FROM users").fetchall()
    
    def execute(self, query, params=None, commit=False):
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            if commit:
                self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Database error: {e}")
            return False

# Obuna tekshirish
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(Config.CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Subscription check failed: {e}")
        return False

async def ask_for_subscription(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Kanalga o'tish", url=Config.CHANNEL_LINK)
    builder.button(text="✅ Obuna bo'ldim", callback_data="check_subscription")
    builder.adjust(1)

    await message.answer(
        "🤖 Botdan to'liq foydalanish uchun kanalga obuna bo'ling:\n"
        f"{Config.CHANNEL_LINK}\n\n"
        "Obuna bo'lgach, '✅ Obuna bo'ldim' tugmasini bosing.",
        reply_markup=builder.as_markup(),
        disable_web_page_preview=True
    )

# Start komandasi
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user = message.from_user
    
    db = Database()
    db.add_user(user.id, user.full_name, user.username)
    
    if not await check_subscription(user.id):
        await ask_for_subscription(message)
        return
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="📞 Adminga murojaat")
    builder.adjust(1)
    
    await message.answer(
        f"👋 Salom, {user.full_name}!\n\n"
        "🎥 Kino kodini yuboring (faqat raqamlar):",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@dp.callback_query(F.data == "check_subscription")
async def verify_subscription(query: types.CallbackQuery):
    user = query.from_user
    
    if await check_subscription(user.id):
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Message delete failed: {e}")
        
        await query.answer("✅ Obuna tasdiqlandi!", show_alert=True)
        await start_cmd(query.message)
    else:
        await query.answer("❌ Obuna tasdiqlanmadi!", show_alert=True)
        await ask_for_subscription(query.message)

# Kino yuborish
@dp.message(F.text.regexp(r'^\d+$'))
async def send_movie_by_code(message: types.Message):
    user = message.from_user
    
    if not await check_subscription(user.id):
        await ask_for_subscription(message)
        return
    
    code = int(message.text)
    db = Database()
    
    movie = db.get_movie_by_code(code)
    
    if movie:
        try:
            await bot.copy_message(
                chat_id=user.id,
                from_chat_id=Config.CHANNEL_ID_sh,
                message_id=movie[1],
                caption=f"🎬 {movie[0]}\n\n📢 Bizning asosiy kanal: {Config.CHANNEL_LINK}"
            )
            
            db.update_user_activity(user.id)
        except Exception as e:
            logger.error(f"Movie send error: {e}")
            await message.answer("❌ Kino yuborishda xatolik yuz berdi")
    else:
        await message.answer("❌ Bunday kodli kino topilmadi")

# Admin bilan aloqa
@dp.message(F.text == "📞 Adminga murojaat")
async def contact_admin(message: types.Message, state: FSMContext):
    await message.answer(
        "✍️ Xabaringizni yuboring (matn, rasm, video yoki fayl):\n\n"
        "Adminlar tez orada javob berishadi.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Bekor qilish")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.contact_admin)

@dp.message(AdminState.contact_admin)
async def forward_to_admin(message: types.Message, state: FSMContext):
    if message.text == "◀️ Bekor qilish":
        await state.clear()
        await start_cmd(message)
        return
    
    user = message.from_user
    user_info = (
        f"👤 <b>Foydalanuvchi:</b> {user.full_name}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    )
    
    try:
        if message.text:
            caption = f"{user_info}📝 Xabar: {message.text}"
            content = {'type': 'text', 'text': caption}
        elif message.photo:
            caption = f"{user_info}📷 Rasm"
            content = {'type': 'photo', 'file_id': message.photo[-1].file_id, 'caption': caption}
        elif message.video:
            caption = f"{user_info}🎥 Video"
            content = {'type': 'video', 'file_id': message.video.file_id, 'caption': caption}
        elif message.document:
            caption = f"{user_info}📄 Fayl: {message.document.file_name}"
            content = {'type': 'document', 'file_id': message.document.file_id, 'caption': caption}
        else:
            await message.answer("❌ Qabul qilinmaydigan format")
            return
        
        # Forward to all admins
        for admin_id in Config.ADMIN_IDS:
            try:
                if content['type'] == 'text':
                    await bot.send_message(
                        admin_id,
                        content['text'],
                        reply_markup=ForceReply()
                    )
                else:
                    method = getattr(bot, f"send_{content['type']}")
                    await method(
                        admin_id,
                        content['file_id'],
                        caption=content.get('caption'),
                        reply_markup=ForceReply()
                    )
            except Exception as e:
                logger.error(f"Failed to forward to admin {admin_id}: {e}")
        
        await message.answer(
            "✅ Xabaringiz adminlarga yuborildi. Javobni kuting.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="⬅️ Asosiy menyu")]],
                resize_keyboard=True
            )
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Contact admin error: {e}")
        await message.answer("❌ Xabar yuborishda xatolik")

# Admin reply handler
@dp.message(F.reply_to_message, F.from_user.id.in_(Config.ADMIN_IDS))
async def handle_admin_reply(message: types.Message):
    try:
        original_msg = message.reply_to_message
        if not original_msg.text and not original_msg.caption:
            return
        
        text = original_msg.text or original_msg.caption
        if "👤 Foydalanuvchi:" not in text:
            return
        
        # Extract user ID
        lines = text.split('\n')
        user_id = None
        for line in lines:
            if "🆔 ID:" in line:
                user_id = int(line.split(":")[1].strip().replace('<code>', '').replace('</code>', ''))
                break
        
        if not user_id:
            await message.answer("❌ Foydalanuvchi ID topilmadi")
            return
        
        # Send reply
        reply_text = (
            "📩 <b>Admin javobi:</b>\n\n"
            f"{message.text}\n\n"
            "💬 Qo'shimcha savollar bo'lsa, yozishingiz mumkin."
        )
        
        try:
            await bot.send_message(user_id, reply_text)
            await message.answer("✅ Javob yuborildi!")
        except Exception as e:
            await message.answer(f"❌ Javob yuborish mumkin emas: {e}")
            
    except Exception as e:
        logger.error(f"Admin reply error: {e}")
        await message.answer("❌ Xatolik yuz berdi")

# Admin paneli
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.answer("⛔ Ruxsat yo'q!")
        return
    
    builder = ReplyKeyboardBuilder()
    builder.button(text="📊 Statistika")
    builder.button(text="🎬 Kino qo'shish")
    builder.button(text="🗑️ Kino o'chirish")
    builder.button(text="📢 Reklama yuborish")
    builder.button(text="⬅️ Asosiy menyu")
    builder.adjust(2)
    
    await message.answer(
        "👨‍💻 Admin paneli\n\n"
        "Quyidagi amallardan birini tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Statistika
@dp.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id not in Config.ADMIN_IDS:
        return
    
    db = Database()
    total_users, active_users, total_movies = db.get_stats()
    
    await message.answer(
        f"📊 Statistika\n\n👥 Jami foydalanuvchilar: {total_users}\n"
        f"🔹 Faol foydalanuvchilar (30 kun): {active_users}\n"
        f"🎬 Jami kinolar: {total_movies}"
    )

# Kino qo'shish
@dp.message(F.text == "🎬 Kino qo'shish")
async def start_add_movie(message: types.Message, state: FSMContext):
    if message.from_user.id not in Config.ADMIN_IDS:
        return
    
    await message.answer(
        "🎥 <b>Yangi kino qo'shish</b>\n\n"
        "Kino nomini yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Ortga")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.waiting_for_name)

@dp.message(AdminState.waiting_for_name)
async def get_movie_name(message: types.Message, state: FSMContext):
    if message.text == "◀️ Ortga":
        await state.clear()
        await admin_panel(message)
        return
    
    await state.update_data(nomi=message.text)
    await message.answer(
        "📹 Endi kino videosini yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Ortga")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.waiting_for_file)

@dp.message(AdminState.waiting_for_file, F.video | F.document)
async def process_movie(message: types.Message, state: FSMContext):
    if message.text == "◀️ Ortga":
        await state.clear()
        await admin_panel(message)
        return

    data = await state.get_data()
    nomi = data.get("nomi", "Nomsiz")
    
    # Generate new code
    db = Database()
    result = db.cursor.execute("SELECT MAX(kod) FROM kinolar").fetchone()
    new_code = (result[0] if result[0] else 1000) + 1
    
    try:
        # Post to main channel
        bot_username = (await bot.get_me()).username
        caption = (
            f"🎬 <b>{nomi}</b>\n\n"
            f"🔢 Kodi: <code>{new_code}</code>\n\n"
            f"📥 @{bot_username} orqali yuklab olish mumkin\n"
            f"🔗 Kanal: {Config.CHANNEL_LINK}"
        )
        
        # Send video to channel
        if message.video:
            msg = await bot.send_video(
                chat_id=Config.CHANNEL_ID_sh,
                video=message.video.file_id,
                caption=caption
            )
        else:
            msg = await bot.send_document(
                chat_id=Config.CHANNEL_ID_sh,
                document=message.document.file_id,
                caption=caption
            )
        
        # Save to database
        db.add_movie(new_code, nomi, msg.message_id)
        
        await message.answer(
            f"✅ Kino muvaffaqiyatli qo'shildi!\n\n"
            f"📝 Nomi: {nomi}\n"
            f"🔢 Kodi: <code>{new_code}</code>"
        )
        
    except Exception as e:
        logger.error(f"Movie addition failed: {e}")
        await message.answer(f"❌ Xatolik: {str(e)}")
    
    await state.clear()
    await admin_panel(message)

# Kino o'chirish
@dp.message(F.text == "🗑️ Kino o'chirish")
async def delete_movie_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in Config.ADMIN_IDS:
        return
    
    await message.answer(
        "🔢 O'chirish uchun kino kodini yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Bekor qilish")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.waiting_for_movie_code_to_delete)

@dp.message(AdminState.waiting_for_movie_code_to_delete, F.text.regexp(r'^\d+$'))
async def delete_movie_by_code(message: types.Message, state: FSMContext):
    code = int(message.text)
    db = Database()
    
    # Kino mavjudligini tekshirish
    movie = db.get_movie_by_code(code)
    
    if not movie:
        await message.answer("❌ Bunday kodli kino topilmadi")
        await state.clear()
        return
    
    # Kino o'chirish
    if db.delete_movie(code):
        await message.answer(f"✅ Kino kod {code} muvaffaqiyatli o'chirildi")
    else:
        await message.answer("❌ Kino o'chirishda xatolik yuz berdi")
    
    await state.clear()
    await admin_panel(message)

@dp.message(AdminState.waiting_for_movie_code_to_delete, F.text == "◀️ Bekor qilish")
async def cancel_delete_movie(message: types.Message, state: FSMContext):
    await state.clear()
    await admin_panel(message)

# Reklama yuborish
@dp.message(F.text == "📢 Reklama yuborish")
async def start_advertisement(message: types.Message, state: FSMContext):
    if message.from_user.id not in Config.ADMIN_IDS:
        return
    
    await message.answer(
        "✍️ Reklama uchun matn, rasm, video yoki fayl yuboring:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Bekor qilish")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminState.send_ad)

@dp.message(AdminState.send_ad)
async def send_advertisement(message: types.Message, state: FSMContext):
    if message.text == "◀️ Bekor qilish":
        await state.clear()
        await admin_panel(message)
        return
    
    db = Database()
    users = db.get_all_users()
    if not users:
        await message.answer("⚠️ Hozircha hech qanday foydalanuvchi yo'q!")
        await state.clear()
        return
    
    total = len(users)
    success = 0
    
    # Progress xabarini yuborish
    progress_msg = await message.answer(f"⏳ Reklama yuborilmoqda... 0/{total}")
    
    for user in users:
        user_id = user[0]
        try:
            if message.text:
                await bot.send_message(user_id, message.text)
            elif message.photo:
                await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                await bot.send_video(user_id, message.video.file_id, caption=message.caption)
            elif message.document:
                await bot.send_document(user_id, message.document.file_id, caption=message.caption)
            success += 1
            
            # Har 10 ta yuborilganda progress yangilash
            if success % 10 == 0 or success == total:
                await progress_msg.edit_text(f"⏳ Reklama yuborilmoqda... {success}/{total}")
                
        except Exception as e:
            logger.error(f"Xabar yuborilmadi (User ID: {user_id}): {e}")
    
    await progress_msg.delete()
    await message.answer(
        f"📢 Reklama yuborish yakunlandi!\n\n"
        f"👥 Jami foydalanuvchilar: {total}\n"
        f"✅ Muvaffaqiyatli yuborildi: {success}\n"
        f"❌ Yuborilmadi: {total - success}"
    )
    await state.clear()
@dp.message(Command("healthcheck"))
async def healthcheck(message: types.Message):
    try:
        # Database connection check
        db = Database()
        db.cursor.execute("SELECT 1")
        
        # Telegram API check
        await bot.get_me()
        
        await message.answer("✅ Bot ishlayapti")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
        
async def healthcheck(request):
    return web.Response(text="OK", status=200)

app = web.Application()
app.router.add_get("/health", healthcheck)

# Asosiy menyuga qaytish
@dp.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main_menu(message: types.Message):
    await start_cmd(message)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
