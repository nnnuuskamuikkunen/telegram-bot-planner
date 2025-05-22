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
                note_type TEXT NOT NULL,
                note_date TEXT NOT NULL, -- Формат YYYY-MM-DD
                note_time TEXT NOT NULL, -- Формат HH:MM
                task_complete INTEGER DEFAULT 0, -- 0: не выполнено, 1: выполнено
                reminder_24h_sent INTEGER DEFAULT 0, -- 0: не отправлено, 1: отправлено
                reminder_1h_sent INTEGER DEFAULT 0 -- 0: не отправлено, 1: отправлено
            )
        ''')
        await db.commit()
    print("База данных инициализирована.")

async def add_note(db_name: str, user_id: int, note_text: str, note_type: str, note_date: str, note_time: str):
    """Добавляет новую заметку в базу данных."""
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.cursor()
        await cursor.execute('''
            INSERT INTO notes (user_id, note_text, note_type, note_date, note_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, note_text, note_type, note_date, note_time))
        await db.commit()
    print(f"Заметка для пользователя {user_id} добавлена.")

async def get_user_notes(db_name: str, user_id: int):
    """Возвращает все заметки для конкретного пользователя."""
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        await cursor.execute('SELECT id, note_text, note_date, note_time, note_type FROM notes WHERE user_id = ? ORDER BY note_date, note_time', (user_id,))
        notes = await cursor.fetchall()
        return notes

async def delete_note(db_name: str, note_id: int, user_id: int):
    """Удаляет заметку по её ID, проверяя, что она принадлежит пользователю."""
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.cursor()
        await cursor.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id))
        await db.commit()
        return cursor.rowcount > 0
    
async def get_note_by_id(db_name: str, note_id: int, user_id: int) -> dict | None:
    """Ищет заметку по ID"""
    async with aiosqlite.connect(db_name) as db:
        cursor = await db.execute(
            """SELECT id, note_text, note_type, note_date, note_time 
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
                "note_type" : row[3],
                "note_time": row[4]
            }
        return None

async def get_notes_by_date(db_name: str, user_id: int, search_date: str) -> list[dict]:
    """Ищет заметки пользователя по указанной дате"""
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

async def get_notes_by_type(db_name: str, user_id: int, search_type: str) -> list[dict]:
    """Ищет заметки пользователя по указанной категории"""
    try:
        async with aiosqlite.connect(db_name) as db:
            cursor = await db.execute(
                """SELECT id, note_text, note_date, note_time 
                   FROM notes 
                   WHERE user_id = ? AND note_type = ?
                   ORDER BY note_date, note_type""",
                (user_id, search_type))
            
            notes = []
            async for row in cursor:
                notes.append({
                    "id": row[0],
                    "note_text": row[1],
                    "note_date": row[2],
                    "note_time": row[3]
                })
            
            await cursor.close()
            return notes
            
    except aiosqlite.Error as e:
        print(f"Ошибка при поиске заметок: {e}")
        return []

async def get_upcoming_notes(db_name: str, user_id: int, limit: int = 10) -> list[dict]:
    """Возвращает ближайшие заметки пользователя, отсортированные по дате и времени.    """
    try:
        async with aiosqlite.connect(db_name) as db:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            cursor = await db.execute(
                """SELECT id, note_text, note_date, note_time 
                   FROM notes 
                   WHERE user_id = ? AND datetime(note_date || ' ' || note_time) >= datetime(?)
                   ORDER BY datetime(note_date || ' ' || note_time)
                   LIMIT ?""",
                (user_id, now, limit))

            notes = []
            async for row in cursor:
                notes.append({
                    "id": row[0],
                    "note_text": row[1],
                    "note_date": row[2],
                    "note_time": row[3]
                })

            await cursor.close()
            return notes

    except aiosqlite.Error as e:
        print(f"Ошибка при поиске ближайших заметок: {e}")
        return []

async def get_notes_for_reminders(db_name: str):
    """Возвращает заметки, для которых, возможно, нужно отправить напоминание."""
    async with aiosqlite.connect(db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        # Выбираем заметки, для которых еще не отправлены оба напоминания
        await cursor.execute('SELECT id, user_id, note_text, note_type, note_date, note_time, task_complete, reminder_24h_sent, reminder_1h_sent FROM notes WHERE reminder_24h_sent = 0 OR reminder_1h_sent = 0')
        notes = await cursor.fetchall()
        return notes

async def mark_reminder_sent(db_name: str, note_id: int, reminder_type: str):
    """Помечает напоминание как отправленное для конкретной заметки."""
    column_name = f'reminder_{reminder_type}_sent' # 'reminder_24h_sent' или 'reminder_1h_sent'
    async with aiosqlite.connect(db_name) as db:
        await db.execute(f'UPDATE notes SET {column_name} = 1 WHERE id = ?', (note_id,))
        await db.commit()

async def edit_notes(db_name: str, user_id: int, note_id: int, new_text: str):
    async with aiosqlite.connect(db_name) as db:
        await db.execute(
            "UPDATE notes SET note_text = ? WHERE id = ? AND user_id = ?",
            (new_text, note_id, user_id)
        )
        await db.commit()
    print(f"Заметка для пользователя {user_id} изменена.")

async def save_as_complete(db_name: str, user_id: int, note_id: int, new_text: str):
    async with aiosqlite.connect(db_name) as db:
        await db.execute(
            "UPDATE notes SET note_text = ? WHERE id = ? AND user_id = ?",
            (new_text, note_id, user_id)
        )
        await db.commit()
        await db.execute(
            "UPDATE notes SET task_complete = 1 WHERE id = ? AND user_id = ?",
            (note_id, user_id)
        )
        print(f"Заметка для пользователя {user_id} отмечена как выполненная.")



