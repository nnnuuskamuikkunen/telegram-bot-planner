from __future__ import annotations
import datetime
import pickle
import os.path
import re
from typing import Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from aiogram import Bot
import aiosqlite

# Настройки
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_TIMEZONE = 'Asia/Singapore'
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'

class GoogleCalendarClient:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.service = None

    async def _get_credentials(self, user_id: int) -> Optional[Credentials]:
        """Асинхронно получает или обновляет учетные данные пользователя"""
        creds = None
        
        # Проверяем наличие сохраненных токенов в базе данных
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT token FROM google_tokens WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                creds = pickle.loads(row[0])
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Сохраняем обновленные токены в базу данных
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT OR REPLACE INTO google_tokens (user_id, token) 
                       VALUES (?, ?)""",
                    (user_id, pickle.dumps(creds))
                )
                await db.commit()
        
        return creds

    async def initialize_service(self, user_id: int) -> bool:
        """Инициализирует сервис Google Calendar"""
        creds = await self._get_credentials(user_id)
        if not creds:
            return False
        
        self.service = build('calendar', 'v3', credentials=creds)
        return True

    async def book_timeslot(
        self,
        user_id: int,
        event_description: str,
        booking_time: str,
        attendee_email: str,
        bot: Optional[Bot] = None,
        chat_id: Optional[int] = None
    ) -> bool:
        """Асинхронно бронирует временной слот в календаре"""
        if not await self.initialize_service(user_id):
            return False

        # Форматируем время
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        start_time = f"{today}T{booking_time}:00+08:00"
        end_hour = str(int(booking_time[:2]) + 1).zfill(2)
        end_time = f"{today}T{end_hour}:00:00+08:00"

        # Проверяем доступность слота
        now = datetime.datetime.now().isoformat() + 'Z'
        events_result = await self.service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Проверяем на конфликты
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            if start == start_time:
                if bot and chat_id:
                    await bot.send_message(chat_id, "❌ Это время уже занято!")
                return False

        # Создаем событие
        event = {
            'summary': 'Запись на услугу',
            'location': 'Онлайн',
            'description': event_description,
            'start': {
                'dateTime': start_time,
                'timeZone': CALENDAR_TIMEZONE,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': CALENDAR_TIMEZONE,
            },
            'attendees': [{'email': attendee_email}],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        created_event = await self.service.events().insert(
            calendarId='primary',
            body=event
        ).execute()
        
        if bot and chat_id:
            await bot.send_message(
                chat_id,
                f"✅ Запись успешно создана!\n"
                f"📅 Дата: {today}\n"
                f"⏰ Время: {booking_time}\n"
                f"📝 Описание: {event_description}\n"
                f"🔗 Ссылка: {created_event.get('htmlLink')}"
            )
        
        return True

async def initialize_database(db_path: str):
    """Инициализирует базу данных для хранения токенов"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS google_tokens (
                user_id INTEGER PRIMARY KEY,
                token BLOB NOT NULL
            )
        """)
        await db.commit()

async def check_email(email: str) -> bool:
    """Проверяет валидность email"""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.fullmatch(pattern, email))

# Пример использования с aiogram
async def handle_booking(
    bot: Bot,
    chat_id: int,
    user_id: int,
    db_path: str,
    description: str,
    time: str,
    email: str
):
    if not await check_email(email):
        await bot.send_message(chat_id, "❌ Неверный формат email!")
        return
    
    calendar = GoogleCalendarClient(db_path)
    success = await calendar.book_timeslot(
        user_id=user_id,
        event_description=description,
        booking_time=time,
        attendee_email=email,
        bot=bot,
        chat_id=chat_id
    )
    
    if not success:
        await bot.send_message(chat_id, "❌ Не удалось создать запись. Попробуйте позже.")

# Инициализация при старте бота
async def on_startup(dp):
    await initialize_database('bot_database.db')

# Пример обработчика команды в aiogram
from aiogram import types

async def cmd_book(message: types.Message):
    # Пример команды: /book 14:00 dye bikshanovau@gmail.com
    try:
        _, time, description, email = message.text.split(maxsplit=3)
        await handle_booking(
            bot=message.bot,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            db_path='bot_database.db',
            description=description,
            time=time,
            email=email
        )
    except ValueError:
        await message.answer("Используйте: /book ЧЧ:ММ описание email@example.com")