import os
import json
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Конфигурация
API_TOKEN = '7294480584:AAFLu2aGsdse6H8SQhw_gLftlIXcDMkYJ8E'
SPREADSHEET_ID = '1PN3QycIbiyFBFo0ae5tXfznDytHKI8s3u8nvLpo4DtY'
CREDENTIALS_FILE = 'eco-bot-credentials.json'

# Подключение к Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# Получаем листы
users_sheet = spreadsheet.worksheet('Users')
eco_companion_sheet = spreadsheet.worksheet('EcoCompanion')
facts_sheet = spreadsheet.worksheet('Facts')
sovets_sheet = spreadsheet.worksheet('Sovets')
kviz_sheet = spreadsheet.worksheet('Kviz')

# Хранилище сессий пользователей
user_sessions = {}

class UserSession:
    def __init__(self):
        self.quiz_completed = False
        self.habit_checked = False
        self.last_visit = None
        self.quiz_score = 0
        self.quiz_question_index = 0

def get_user_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession()
    return user_sessions[user_id]

def get_user_from_db(user_id):
    """Получить пользователя из таблицы Users"""
    try:
        users = users_sheet.get_all_values()
        for i, row in enumerate(users[1:], start=2):  # Пропускаем заголовок
            if row[0] == str(user_id):
                return {
                    'row': i,
                    'id': row[0],
                    'date_reg': row[1],
                    'name': row[2],
                    'ball': int(row[3]) if row[3] else 0
                }
        return None
    except Exception as e:
        print(f"Ошибка при получении пользователя: {e}")
        return None

def update_user_balls(user_id, balls):
    """Обновить баллы пользователя"""
    try:
        user = get_user_from_db(user_id)
        if user:
            new_balls = user['ball'] + balls
            users_sheet.update_cell(user['row'], 4, new_balls)
            return new_balls
        return None
    except Exception as e:
        print(f"Ошибка при обновлении баллов: {e}")
        return None

def add_user_to_db(user_id, username):
    """Добавить нового пользователя"""
    try:
        date_reg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        users_sheet.append_row([str(user_id), date_reg, username, 5])
    except Exception as e:
        print(f"Ошибка при добавлении пользователя: {e}")

def get_random_fact():
    """Получить случайный эко-факт"""
    try:
        facts = facts_sheet.col_values(1)[1:]  # Пропускаем заголовок
        return random.choice(facts) if facts else "Эко-факт временно недоступен"
    except Exception as e:
        print(f"Ошибка при получении факта: {e}")
        return "Эко-факт временно недоступен"

def get_random_sovet():
    """Получить случайный эко-совет"""
    try:
        sovets = sovets_sheet.col_values(1)[1:]
        return random.choice(sovets) if sovets else "Эко-совет временно недоступен"
    except Exception as e:
        print(f"Ошибка при получении совета: {e}")
        return "Эко-совет временно недоступен"

def get_random_quiz_questions(count=3):
    """Получить случайные вопросы викторины"""
    try:
        all_questions = kviz_sheet.get_all_values()[1:]  # Пропускаем заголовок
        selected = random.sample(all_questions, min(count, len(all_questions)))
        
        quiz_data = []
        for q in selected:
            quiz_data.append({
                'question': q[0],
                'option1': q[1],
                'option2': q[2],
                'option3': q[3],
                'correct': q[4]
            })
        return quiz_data
    except Exception as e:
        print(f"Ошибка при получении вопросов викторины: {e}")
        return []

def get_eco_points_by_type(waste_type):
    """Получить пункты приема по типу отходов"""
    try:
        all_data = eco_companion_sheet.get_all_values()
        result = []
        
        for row in all_data[1:]:  # Пропускаем заголовок
            if row[0] == waste_type:
                result.append({
                    'type': row[0],
                    'address': row[1],
                    'name': row[2],
                    'time': row[3],
                    'note': row[4] if len(row) > 4 else ''
                })
        
        return result
    except Exception as e:
        print(f"Ошибка при получении пунктов приема: {e}")
        return []

def get_user_rating(user_id):
    """Получить рейтинг пользователя"""
    try:
        users = users_sheet.get_all_values()[1:]
        user_data = [(row[0], row[2], int(row[3]) if row[3] else 0) for row in users]
        user_data.sort(key=lambda x: x[2], reverse=True)
        
        total_users = len(user_data)
        user_balls = 0
        user_rank = 0
        
        for rank, (uid, name, balls) in enumerate(user_data, start=1):
            if str(uid) == str(user_id):
                user_rank = rank
                user_balls = balls
                break
        
        return {
            'balls': user_balls,
            'rank': user_rank,
            'total': total_users
        }
    except Exception as e:
        print(f"Ошибка при получении рейтинга: {e}")
        return {'balls': 0, 'rank': 0, 'total': 0}

def main_menu_keyboard():
    """Клавиатура главного меню"""
    keyboard = [
        [InlineKeyboardButton("🌱 Эко-совет", callback_data='eco_sovet')],
        [InlineKeyboardButton("📍 Найти пункт приема", callback_data='find_point')],
        [InlineKeyboardButton("🎯 Эко-викторина", callback_data='eco_quiz')],
        [InlineKeyboardButton("✅ Чек-лист привычек", callback_data='checklist')],
        [InlineKeyboardButton("🏆 Личный рейтинг", callback_data='rating')]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_to_menu_keyboard():
    """Клавиатура возврата в меню"""
    keyboard = [[InlineKeyboardButton("↩️ Главное меню", callback_data='main_menu')]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user = get_user_from_db(user_id)
    session = get_user_session(user_id)
    
    # Сбрасываем сессию при входе
    session.quiz_completed = False
    session.habit_checked = False
    
    if user is None:
        # Новый пользователь - регистрация
        await update.message.reply_text(
            "Привет! Я твой Eco_Помощник! 🌿\n\n"
            "Я помогу тебе начать жить экологичнее: расскажу факты, дам совет "
            "и подскажу, куда сдать мусор.\n\n"
            "Как тебя зовут?"
        )
        context.user_data['awaiting_name'] = True
    else:
        # Существующий пользователь
        # Проверяем последний визит
        today = datetime.now().date()
        if session.last_visit != today:
            # Начисляем балл за ежедневный визит
            update_user_balls(user_id, 1)
            session.last_visit = today
        
        await update.message.reply_text(f"Привет, {user['name']}! Я рад тебя снова видеть! 😊")
        
        # Показываем факт через 2 секунды
        import asyncio
        await asyncio.sleep(2)
        
        fact = get_random_fact()
        await update.message.reply_text(f"🌍 {fact}")
        
        await asyncio.sleep(2)
        
        # Главное меню
        user_data = get_user_from_db(user_id)
        await update.message.reply_text(
            f"{user_data['name']}! Выбери, что тебя интересует:",
            reply_markup=main_menu_keyboard()
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (для регистрации)"""
    if context.user_data.get('awaiting_name'):
        user_id = update.effective_user.id
        username = update.message.text.strip()
        
        # Сохраняем пользователя
        add_user_to_db(user_id, username)
        context.user_data['awaiting_name'] = False
        
        session = get_user_session(user_id)
        session.last_visit = datetime.now().date()
        
        # Показываем факт
        import asyncio
        await asyncio.sleep(2)
        
        fact = get_random_fact()
        await update.message.reply_text(f"🌍 {fact}")
        
        await asyncio.sleep(2)
        
        # Главное меню
        await update.message.reply_text(
            f"{username}! Выбери, что тебя интересует:",
            reply_markup=main_menu_keyboard()
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = get_user_from_db(user_id)
    session = get_user_session(user_id)
    
    data = query.data
    
    if data == 'main_menu':
        await query.edit_message_text(
            f"{user['name']}! Выбери, что тебя интересует:",
            reply_markup=main_menu_keyboard()
        )
    
    elif data == 'eco_sovet':
        sovet = get_random_sovet()
        await query.edit_message_text(
            f"💡 {sovet}",
            reply_markup=back_to_menu_keyboard()
        )
    
    elif data == 'find_point':
        keyboard = [
            [InlineKeyboardButton("🔋 Батарейки", callback_data='waste_Батарейки')],
            [InlineKeyboardButton("👕 Одежда", callback_data='waste_Одежда')],
            [InlineKeyboardButton("💻 Техника", callback_data='waste_Техника')],
            [InlineKeyboardButton("🥤 Стекло", callback_data='waste_Стекло')],
            [InlineKeyboardButton("♻️ Пластик", callback_data='waste_Пластик')],
            [InlineKeyboardButton("📄 Бумага", callback_data='waste_Бумага')],
            [InlineKeyboardButton("↩️ Главное меню", callback_data='main_menu')]
        ]
        await query.edit_message_text(
            "Какой тип отходов ты хочешь сдать?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('waste_'):
        waste_type = data.replace('waste_', '')
        points = get_eco_points_by_type(waste_type)
        
        if points:
            message = f"📍 Пункты приема ({waste_type}):\n\n"
            for i, point in enumerate(points, 1):
                message += f"{i}. {point['name']}\n"
                message += f"📫 Адрес: {point['address']}\n"
                message += f"🕐 Время работы: {point['time']}\n"
                if point['note']:
                    message += f"ℹ️ {point['note']}\n"
                message += "\n"
        else:
            message = f"К сожалению, пункты приема для типа '{waste_type}' не найдены."
        
        await query.edit_message_text(message, reply_markup=back_to_menu_keyboard())
    
    elif data == 'eco_quiz':
        if session.quiz_completed:
            await query.edit_message_text(
                "Ты уже прошел викторину в этой сессии! ✨\n"
                "Возвращайся позже для новых вопросов!",
                reply_markup=back_to_menu_keyboard()
            )
            return
        
        # Начинаем викторину
        session.quiz_score = 0
        session.quiz_question_index = 0
        context.user_data['quiz_questions'] = get_random_quiz_questions(3)
        
        # Показываем первый вопрос
        await show_quiz_question(query, context, 0)
    
    elif data.startswith('quiz_answer_'):
        parts = data.split('_')
        question_index = int(parts[2])
        answer = parts[3]
        
        quiz_questions = context.user_data.get('quiz_questions', [])
        if not quiz_questions:
            await query.edit_message_text("Ошибка викторины", reply_markup=back_to_menu_keyboard())
            return
        
        current_q = quiz_questions[question_index]
        is_correct = (answer == current_q['correct'])
        
        if is_correct:
            session.quiz_score += 1
            result_text = "✅ Верно!"
        else:
            result_text = "❌ Почти! В другой раз будет успех!"
        
        # Проверяем, есть ли еще вопросы
        next_index = question_index + 1
        if next_index < len(quiz_questions):
            keyboard = [[InlineKeyboardButton(f"Вопрос {next_index + 1}", callback_data=f'quiz_next_{next_index}')]]
            await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            # Викторина завершена
            session.quiz_completed = True
            
            # Начисляем баллы
            balls_earned = max(session.quiz_score, 1)
            new_total = update_user_balls(user_id, balls_earned)
            
            if session.quiz_score == 3:
                final_message = f"{user['name']}! Получено {balls_earned} балла. Ты Эко-герой! 🌟"
            elif session.quiz_score == 2:
                final_message = f"{user['name']}! Получено {balls_earned} балла. Ты на верном пути! 🌿"
            else:
                final_message = f"{user['name']}! Получен {balls_earned} балл. Есть куда стремиться! Начни с малого - читай мои эко-факты! 📚"
            
            await query.edit_message_text(final_message, reply_markup=back_to_menu_keyboard())
    
    elif data.startswith('quiz_next_'):
        question_index = int(data.split('_')[2])
        await show_quiz_question(query, context, question_index)
    
    elif data == 'checklist':
        if session.habit_checked:
            await query.edit_message_text(
                "Ты уже отметил привычку сегодня! 🎉\n"
                "Возвращайся завтра!",
                reply_markup=back_to_menu_keyboard()
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("♻️ Сортирую мусор", callback_data='habit_sort')],
            [InlineKeyboardButton("💧 Экономлю воду", callback_data='habit_water')],
            [InlineKeyboardButton("🛍️ Пользуюсь шопером", callback_data='habit_bag')],
            [InlineKeyboardButton("📦 Сдаю вторсырье", callback_data='habit_recycle')],
            [InlineKeyboardButton("🔋 Сдаю батарейки", callback_data='habit_battery')],
            [InlineKeyboardButton("↩️ Главное меню", callback_data='main_menu')]
        ]
        
        await query.edit_message_text(
            "Отмечай привычки, которые выполнил сегодня! 🌱",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith('habit_'):
        session.habit_checked = True
        new_total = update_user_balls(user_id, 2)
        
        await query.edit_message_text(
            "Супер! Так держать! 🌟\n"
            "Каждая маленькая привычка имеет большое значение для планеты!\n\n"
            "+2 балла",
            reply_markup=back_to_menu_keyboard()
        )
    
    elif data == 'rating':
        rating = get_user_rating(user_id)
        
        await query.edit_message_text(
            f"{user['name']}! У тебя {rating['balls']} баллов. 🏆\n\n"
            f"Всего пользователей: {rating['total']}\n"
            f"Твой личный рейтинг: {rating['rank']}!",
            reply_markup=back_to_menu_keyboard()
        )

async def show_quiz_question(query, context, question_index):
    """Показать вопрос викторины"""
    quiz_questions = context.user_data.get('quiz_questions', [])
    if question_index >= len(quiz_questions):
        return
    
    q = quiz_questions[question_index]
    
    keyboard = [
        [InlineKeyboardButton(q['option1'], callback_data=f"quiz_answer_{question_index}_{q['option1']}")],
        [InlineKeyboardButton(q['option2'], callback_data=f"quiz_answer_{question_index}_{q['option2']}")],
        [InlineKeyboardButton(q['option3'], callback_data=f"quiz_answer_{question_index}_{q['option3']}")]
    ]
    
    await query.edit_message_text(
        f"❓ Вопрос {question_index + 1}/3:\n\n{q['question']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    """Запуск бота"""
    application = Application.builder().token(API_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
