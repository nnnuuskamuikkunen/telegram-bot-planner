import logging
from datetime import datetime, timedelta
import asyncio
from database import get_notes_for_reminders, mark_reminder_sent
from config import DATABASE_NAME

async def check_reminders(bot):
    """Фоновая задача для проверки и отправки напоминаний."""
    while True:
        logging.info("Проверка напоминаний...")
        now = datetime.now()
        notes_to_check = await get_notes_for_reminders(DATABASE_NAME)

        for note in notes_to_check:
            note_id = note['id']
            user_id = note['user_id']
            note_text = note['note_text']
            note_type = note["note_type"]
            note_date_str = note['note_date']
            note_time_str = note['note_time']

            try:
                note_datetime = datetime.strptime(f"{note_date_str} {note_time_str}", "%d-%m-%Y %H:%M")
            except ValueError:
                logging.error(f"Неверный формат даты/времени для заметки ID {note_id}: {note_date_str} {note_time_str}")
                continue

            time_diff = note_datetime - now

            if not note['reminder_24h_sent'] and time_diff <= timedelta(days=1) and time_diff > timedelta(hours=1):
                try:
                    await bot.send_message(user_id, f"Напоминание (24 часа): \"{note_text}\" в категории \"{note_type}\" запланировано на {note_date_str} {note_time_str}")
                    await mark_reminder_sent(DATABASE_NAME, note_id, '24h')
                    logging.info(f"Отправлено напоминание 24h для заметки ID {note_id} пользователю {user_id}")
                except Exception as e:
                    logging.error(f"Ошибка отправки 24h напоминания для заметки ID {note_id}: {e}")

            elif not note['reminder_1h_sent'] and time_diff <= timedelta(hours=1) and time_diff > timedelta(minutes=0):
                try:
                    await bot.send_message(user_id, f"Напоминание (1 час): \"{note_text}\" в категории \"{note_type}\" запланировано на {note_date_str} {note_time_str}")
                    await mark_reminder_sent(DATABASE_NAME, note_id, '1h')
                    logging.info(f"Отправлено напоминание 1h для заметки ID {note_id} пользователю {user_id}")
                except Exception as e:
                    logging.error(f"Ошибка отправки 1h напоминания для заметки ID {note_id}: {e}")

        await asyncio.sleep(60)