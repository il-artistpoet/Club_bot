# Пленэрный Клуб Бот - ФИНАЛЬНАЯ ВЕРСИЯ
# Работает на Render и Pydroid 3

import os
import telebot
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request
import time

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv('BOT_TOKEN', '8432420548:AAGX_EqsarA7q_Jx4iNL2zV8j3c_JWd_POU')
CHANNEL_ID = "-1003227241488"
ADMIN_ID = 644037215
TILDA_LINK = "https://pleinairclub.tilda.ws/"

# Реквизиты
SBER_PHONE = "+79043323607"
SBER_CARD = "2202208262152375"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== БАЗА ДАННЫХ ==========
DB_PATH = 'club.db'

def get_db():
    """Простое подключение к базе"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Создание таблиц при старте"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Основная таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            tariff TEXT,
            amount INTEGER DEFAULT 0,
            paid INTEGER DEFAULT 0,
            screenshot_date TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

# ========== ВЕБХУК ДЛЯ RENDER ==========
@app.route('/')
def home():
    return "🎨 Пленэрный Клуб Бот работает!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка вебхуков от Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    logger.info(f"🚀 /start от {user_id}")
    
    # 1. Приветственное сообщение и ОТПРАВКА ФОТО
    try:
        # Вариант 1: Если фото лежит в той же папке на Render
        with open('photo.png', 'rb') as photo:
            bot.send_photo(user_id, photo)
            logger.info(f"📸 Фото отправлено пользователю {user_id}")
            
    except FileNotFoundError:
        # Если файл не найден
        logger.error(f"❌ Файл photo.png не найден!")
        bot.send_message(
            user_id,
            "🎨Приветствую Вас. Оставайтесь на волне созерцания и пленэра!"
        )
        
    except Exception as e:
        # Любая другая ошибка
        logger.error(f"❌ Ошибка при отправке фото: {e}")
        bot.send_message(
            user_id,
            "🎨 Добро пожаловать в Пленэрный Клуб!"
        )
    
    # 3. Основное сообщение с кнопками (остальной код без изменений)
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    
    btn_more = telebot.types.InlineKeyboardButton(
        text="Узнать больше",
        url=TILDA_LINK
    )
    
    btn_club = telebot.types.InlineKeyboardButton(
        text="Хочу в клуб!",
        callback_data="join_club"
    )
    
    markup.add(btn_more, btn_club)
    
    bot.send_message(
        user_id,
        "🎨Приветствую Вас. Оставайтесь на волне созерцания и пленэра!"\n\n"
        "Здесь можно купить подписку и получить доступ в \"Пленэрный Клуб\"!\n\n"
        "Это закрытый телеграм-канал, где все участники могут делиться своим творчеством "
        "и получать от меня обратную связь.",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "join_club")
def show_tariffs(call):
    """Показ тарифов"""
    user_id = call.from_user.id
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    btn_reader = telebot.types.InlineKeyboardButton("🔥 ЧИТАТЕЛЬ — 100₽/месяц", callback_data="tariff_reader")
    btn_member = telebot.types.InlineKeyboardButton("💎 УЧАСТНИК — 500₽/месяц", callback_data="tariff_member")
    markup.add(btn_reader, btn_member)
    
    bot.send_message(
        user_id,
        "🎯 ВЫБЕРИТЕ ТАРИФ:\n\n"
        "🔥 ЧИТАТЕЛЬ — 100₽\n"
        "• Просмотр всех материалов\n"
        "• Без обратной связи\n\n"
        "💎 УЧАСТНИК — 500₽\n"  
        "• Всё из тарифа Читатель\n"
        "• Разбор Ваших работ\n"
        "• Помощь по всем вопросам",
        reply_markup=markup
    )

# В функции handle_tariff ИЗМЕНИ этот блок:

@bot.callback_query_handler(func=lambda call: call.data in ["tariff_reader", "tariff_member"])
def handle_tariff(call):
    """Обработка выбора тарифа с возможностью апгрейда"""
    user_id = call.from_user.id
    
    if call.data == "tariff_reader":
        selected_tariff, selected_amount = "читатель", 100
    else:
        selected_tariff, selected_amount = "участник", 500
    
    # Подключаемся к базе
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем текущие данные пользователя
    cursor.execute("SELECT tariff, amount, paid FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        current_tariff = user['tariff']
        current_amount = user['amount']
        paid = user['paid']
        
        # Если уже оплатил
        if paid == 1:
            # Пользователь уже в клубе - проверяем апгрейд
            if current_tariff == "читатель" and selected_tariff == "участник":
                # ПРЕДЛАГАЕМ АПГРЕЙД
                to_pay = selected_amount - current_amount  # 400₽
                
                markup = telebot.types.InlineKeyboardMarkup()
                btn_upgrade = telebot.types.InlineKeyboardButton(
                    f"💎 ПЕРЕЙТИ (+{to_pay}₽)",
                    callback_data="upgrade_member"
                )
                markup.add(btn_upgrade)
                
                bot.send_message(
                    user_id,
                    f"✅ Вы уже оплатили тариф '{current_tariff.upper()}'!\n\n"
                    f"Хотите перейти на тариф 'УЧАСТНИК'?\n"
                    f"• Ваш тариф: {current_tariff} ({current_amount}₽)\n"
                    f"• Новый тариф: участник ({selected_amount}₽)\n"
                    f"• К доплате: {to_pay}₽\n\n"
                    f"Вы получите:\n"
                    f"• Обратную связь по работам\n"
                    f"• Ответы на вопросы\n"
                    f"• Поддержку от меня",
                    reply_markup=markup
                )
                
                conn.close()
                bot.answer_callback_query(call.id, "Предлагаем апгрейд")
                return
            else:
                # Уже на этом или высшем тарифе
                bot.answer_callback_query(call.id, f"✅ Вы уже на тарифе {current_tariff}")
                bot.send_message(
                    user_id,
                    f"Вы уже на тарифе '{current_tariff.upper()}'!\n\n"
                    f"Для смены тарифа напишите @artistilja"
                )
                conn.close()
                return
    
    # Если пользователя нет ИЛИ не оплатил - сохраняем выбор
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, tariff, amount, updated_at)
        VALUES (?, ?, ?, datetime('now'))
    """, (user_id, selected_tariff, selected_amount))
    
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, f"Выбрали {selected_tariff}")
    
    # Инструкция по оплате
    message_text = f"""Вы выбрали: {selected_tariff.upper()}

Сумма: {selected_amount}₽

Для оплаты:
1. Переведите {selected_amount}₽ на Сбер по номеру {SBER_PHONE}"""
    
    if SBER_CARD:
        message_text += f"\n\nИли на карту: {SBER_CARD}"
    
    message_text += "\n\n2. Отправьте скриншот сюда"
    
    bot.send_message(user_id, message_text)

# ========== ДОБАВЬ ЭТУ ФУНКЦИЮ ДЛЯ АПГРЕЙДА ==========
@bot.callback_query_handler(func=lambda call: call.data == "upgrade_member")
def handle_upgrade(call):
    """Обработка апгрейда с читателя на участника"""
    user_id = call.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем текущие данные
    cursor.execute("SELECT tariff, amount FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user or user['tariff'] != "читатель":
        bot.answer_callback_query(call.id, "❌ Нельзя выполнить апгрейд")
        conn.close()
        return
    
    current_tariff, current_amount = user['tariff'], user['amount']
    new_tariff, new_amount = "участник", 500
    to_pay = new_amount - current_amount  # 400₽
    
    # Обновляем тариф в базе (paid остаётся 1)
    cursor.execute("""
        UPDATE users 
        SET tariff = ?, amount = ?, updated_at = datetime('now')
        WHERE user_id = ?
    """, (new_tariff, new_amount, user_id))
    
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ Тариф изменен!")
    
    # Инструкция по доплате
    bot.send_message(
        user_id,
        f"🎉 ВЫ ПЕРЕХОДИТЕ НА 'УЧАСТНИКА'!\n\n"
        f"✅ Новый тариф: {new_tariff.upper()}\n"
        f"💰 К доплате: {to_pay}₽\n\n"
        f"Доплатите {to_pay}₽ на Сбер по номеру:\n"
        f"📱 {SBER_PHONE}\n\n"
        f"И отправьте скриншот в этот чат!\n\n"
        f"После доплаты вы получите:\n"
        f"• Обратную связь по работам\n"
        f"• Ответы на вопросы\n"
        f"• Поддержку от меня"
    )
    
#========ОБРАБОТКА СКРИНШОТОВ=====
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Обработка скриншотов оплаты (с поддержкой апгрейда)"""
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем данные пользователя
    cursor.execute("SELECT tariff, amount, paid FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        bot.reply_to(message, "❌ Сначала выберите тариф!")
        conn.close()
        return
    
    tariff, amount, paid = user['tariff'], user['amount'], user['paid']
    
    # Если уже оплатил - проверяем апгрейд
    if paid == 1:
        # Пользователь уже оплатил - возможно это доплата за апгрейд
        if tariff == "читатель":
            # Предлагаем апгрейд снова
            markup = telebot.types.InlineKeyboardMarkup()
            btn_upgrade = telebot.types.InlineKeyboardButton(
                "💎 ПЕРЕЙТИ НА УЧАСТНИКА (+400₽)",
                callback_data="upgrade_member"
            )
            markup.add(btn_upgrade)
            
            bot.send_message(
                user_id,
                f"✅ Вы уже в клубе на тарифе 'ЧИТАТЕЛЬ'!\n\n"
                f"Хотите перейти на 'УЧАСТНИКА'?\n"
                f"• Доплата: 400₽\n"
                f"• Новый тариф: участник (500₽)\n\n"
                f"Получите обратную связь и поддержку:",
                reply_markup=markup
            )
        else:
            bot.reply_to(message, "🎉 Вы на максимальном тарифе - 'УЧАСТНИК'!")
        
        conn.close()
        return
    
    # Если НЕ оплачивал - обычная логика
    # Обновляем статус оплаты
    cursor.execute("""
        UPDATE users 
        SET paid = 1, screenshot_date = datetime('now') 
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    
    # Создаем ссылку в канал
    try:
        invite = bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        
        bot.send_message(
            user_id,
            f"🎉 ОПЛАТА ПРИНЯТА! ДОБРО ПОЖАЛОВАТЬ!\n\n"
            f"Тариф: {tariff.upper()}\n"
            f"Сумма: {amount}₽\n\n"
            f"Ссылка в канал: {invite.invite_link}\n\n"
            f"Доступ на 30 дней",
            disable_web_page_preview=True
        )  
          
        # В функции handle_photo, после отправки ссылки на канал, добавь:
        bot.send_message(
    user_id,
    "ℹ️ *Вы можете проверить свой тариф в любой момент командой* /mytariff\n\n"
    "Если возникнут вопросы - пишите @artistilja",
    parse_mode='Markdown'
)
        
        # Уведомление админу
        bot.send_message(
            ADMIN_ID,
            f"💰 НОВАЯ ОПЛАТА\n"
            f"Пользователь: {message.from_user.first_name}\n"
            f"ID: {user_id}\n"
            f"Тариф: {tariff}\n"
            f"Сумма: {amount}₽"
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания ссылки: {e}")
        bot.send_message(user_id, "✅ Оплата принята! Ссылка будет скоро.")
    
    conn.close()
    
#============ПРОВЕРКА ТАРИФА====== 
 
@bot.message_handler(commands=['mytariff'])
def my_tariff(message):
    """Показать свой тариф"""
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT tariff, amount, paid, screenshot_date FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        bot.reply_to(message, "❌ Вы еще не выбирали тариф")
        return
    
    tariff, amount, paid, screenshot_date = user['tariff'], user['amount'], user['paid'], user['screenshot_date']
    
    status = "✅ ОПЛАЧЕНО" if paid == 1 else "⏳ ОЖИДАЕТ ОПЛАТЫ"
    
    response = f"📋 ВАШ ТАРИФ:\n\n"
    response += f"🎯 Тариф: {tariff.upper() if tariff else 'не выбран'}\n"
    response += f"💰 Сумма: {amount}₽\n"
    response += f"📊 Статус: {status}\n"
    
    if paid == 1 and screenshot_date:
        response += f"🕒 Оплачено: {screenshot_date}\n"
    
    # Если читатель - предлагаем апгрейд
    if paid == 1 and tariff == "читатель":
        markup = telebot.types.InlineKeyboardMarkup()
        btn_upgrade = telebot.types.InlineKeyboardButton(
            "💎 ПЕРЕЙТИ НА УЧАСТНИКА (+400₽)",
            callback_data="upgrade_member"
        )
        markup.add(btn_upgrade)
        
        response += f"\n⚠️ На вашем тарифе нет обратной связи\n"
        response += f"Хотите получить разборы работ и ответы на вопросы?"
        
        bot.send_message(user_id, response, reply_markup=markup)
    else:
        bot.reply_to(message, response)
        
# ========== КОМАНДЫ АДМИНА ==========
@bot.message_handler(commands=['remind'])
def remind_all(message):
    """РУЧНАЯ команда - напомнить всем об оплате"""
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Находим всех, кто оплатил больше 30 дней назад
    cursor.execute("""
        SELECT user_id, tariff, screenshot_date 
        FROM users 
        WHERE paid = 1 
        AND screenshot_date IS NOT NULL
        AND julianday('now') - julianday(screenshot_date) > 30
    """)
    
    users = cursor.fetchall()
    
    if not users:
        bot.reply_to(message, "✅ Все подписки активны!")
        conn.close()
        return
    
    count = 0
    for user in users:
        try:
            bot.send_message(
                user['user_id'],
                f"🔔 ВАША ПОДПИСКА ЗАКОНЧИЛАСЬ!\n\n"
                f"Прошло более 30 дней с последней оплаты.\n"
                f"Для продления напишите /start"
            )
            count += 1
        except:
            pass
    
    bot.reply_to(message, f"📨 Отправлено напоминаний: {count}")
    conn.close()

@bot.message_handler(commands=['stats'])
def stats(message):
    """Статистика"""
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE paid = 1")
    paid = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM users WHERE paid = 1")
    income = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE tariff = 'читатель' AND paid = 1")
    readers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE tariff = 'участник' AND paid = 1")
    members = cursor.fetchone()[0]
    
    conn.close()
    
    stats_text = f"""
📊 СТАТИСТИКА:

👥 Всего в базе: {total}
💰 Оплатили: {paid}
💵 Доход: {income}₽
📖 Читатели: {readers}
💎 Участники: {members}

🔔 Для напоминаний: /remind
"""
    
    bot.reply_to(message, stats_text)

@bot.message_handler(commands=['test'])
def test(message):
    """Тестовая команда"""
    bot.reply_to(message, f"✅ Бот работает! Ваш ID: {message.from_user.id}")

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    # Инициализация базы
    init_db()
    logger.info("🤖 Бот запускается...")
    
    # Проверяем, на Render ли мы
    is_render = os.getenv('RENDER', False)
    
    if is_render:
        # НА RENDER: используем вебхуки
        logger.info("🚀 Запуск на Render (вебхуки)")
        
        # Получаем URL
        render_url = os.getenv('RENDER_EXTERNAL_URL', '')
        if render_url:
            # Устанавливаем вебхук
            bot.remove_webhook()
            time.sleep(1)
            webhook_url = f"{render_url}/webhook"
            bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Вебхук установлен: {webhook_url}")
        
        # Запускаем Flask
        port = int(os.getenv('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
        
    else:
        # НА ТЕЛЕФОНЕ: используем polling
        logger.info("📱 Запуск на телефоне (polling)")
        
        # Удаляем вебхук если был
        bot.remove_webhook()
        time.sleep(1)
        
        # Запускаем polling
        logger.info("✅ Бот готов к работе...")
        bot.polling(none_stop=True)
