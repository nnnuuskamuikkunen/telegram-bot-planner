import aiosqlite
from datetime import datetime

async def init_db(db_name: str):
    """Инициализирует базу данных: создает таблицу заметок, если она не существует."""
    async with aiosqlite.connect(db_name) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                note_text TEXT NOT NULL,
                note_date TEXT NOT NULL, -- Формат YYYY-MM-DD
                note_time TEXT NOT NULL, -- Формат HH:MM
                reminder_24h_sent INTEGER DEFAULT 0, -- 0: не отправлено, 1: отправлено
                reminder_1h_sent INTEGER DEFAULT 0 -- 0: не отправлено, 1: отправлено
            )
        ''')
        await db.commit()
    print("База данных инициализирована.")



"""работа с заметками"""

async def add_note(db_name: str, user_id: int, note_text: str, note_date: str, note_time: str):
    """Добавляет новую заметку в базу данных."""
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.cursor()
        await cursor.execute('''
            INSERT INTO notes (user_id, note_text, note_date, note_time)
            VALUES (?, ?, ?, ?)
        ''', (user_id, note_text, note_date, note_time))
        await db.commit()
    print(f"Заметка для пользователя {user_id} добавлена.")

async def get_user_notes(db_name: str, user_id: int):
    """Возвращает все заметки для конкретного пользователя."""
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row # Это позволит получать строки как объекты с доступом по имени колонки
        cursor = await db.cursor()
        await cursor.execute('SELECT id, note_text, note_date, note_time FROM notes WHERE user_id = ? ORDER BY note_date, note_time', (user_id,))
        notes = await cursor.fetchall()
        return notes

async def delete_note(db_name: str, note_id: int, user_id: int):
    """Удаляет заметку по её ID, проверяя, что она принадлежит пользователю."""
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.cursor()
        await cursor.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id))
        await db.commit()
        return cursor.rowcount > 0 # Возвращает True, если была удалена хотя бы одна строка
    
async def get_note_by_id(db_name: str, note_id: int, user_id: int) -> dict | None:
    async with aiosqlite.connect(db_name) as db:
        # Используем параметризованный запрос для безопасности
        cursor = await db.execute(
            """SELECT id, note_text, note_date, note_time 
               FROM notes 
               WHERE id = ? AND user_id = ?""",
            (note_id, user_id)
        )
        row = await cursor.fetchone()
        await cursor.close()
        
        if row:
            return {
                "id": row[0],
                "note_text": row[1],
                "note_date": row[2],
                "note_time": row[3]
            }
        return None
    
async def get_notes_by_date(db_name: str, user_id: int, search_date: str) -> list[dict]:
    """
    Ищет заметки пользователя по указанной дате
    Args:
        db_name: Имя файла базы данных
        user_id: ID пользователя
        search_date: Дата в формате 'ГГГГ-ММ-ДД'
    Returns:
        Список словарей с заметками (пустой список, если ничего не найдено)
    """
    try:
        async with aiosqlite.connect(db_name) as db:
            # Ищем заметки с указанной датой
            cursor = await db.execute(
                """SELECT id, note_text, note_time 
                   FROM notes 
                   WHERE user_id = ? AND note_date = ?
                   ORDER BY note_time""",
                (user_id, search_date))
            
            notes = []
            async for row in cursor:
                notes.append({
                    "id": row[0],
                    "note_text": row[1],
                    "note_time": row[2]
                })
            
            await cursor.close()
            return notes
            
    except aiosqlite.Error as e:
        print(f"Ошибка при поиске заметок: {e}")
        return []



"""напоминания"""

async def get_notes_for_reminders(db_name: str):
    """Возвращает заметки, для которых, возможно, нужно отправить напоминание."""
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        # Выбираем заметки, для которых еще не отправлены оба напоминания
        await cursor.execute('SELECT id, user_id, note_text, note_date, note_time, reminder_24h_sent, reminder_1h_sent FROM notes WHERE reminder_24h_sent = 0 OR reminder_1h_sent = 0')
        notes = await cursor.fetchall()
        return notes

async def mark_reminder_sent(db_name: str, note_id: int, reminder_type: str):
    """Помечает напоминание как отправленное для конкретной заметки."""
    column_name = f'reminder_{reminder_type}_sent' # 'reminder_24h_sent' или 'reminder_1h_sent'
    async with aiosqlite.connect(db_name) as db:
        await db.execute(f'UPDATE notes SET {column_name} = 1 WHERE id = ?', (note_id,))
        await db.commit()
