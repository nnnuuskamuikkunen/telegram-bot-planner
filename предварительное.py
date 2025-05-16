from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, DateTime, select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
import pytz

# Настройка базы данных
DATABASE_URL = "sqlite+aiosqlite:///tasks.db"
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# Модель задачи
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    text = Column(String)
    due_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    is_notified = Column(Integer, default=0)  # 0 - не уведомлено, 1 - уведомлено

# Инициализация бота и планировщика
bot = Bot(token="7916408010:AAEdFMaxbw4J8qXWALNuC9TBgZlBuzTlx0o")
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=pytz.UTC)

# Состояния FSM
class TaskStates(StatesGroup):
    waiting_for_task_text = State()
    waiting_for_task_date = State()

# Создание таблиц при старте
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Функция для отправки напоминания
async def send_reminder(user_id: int, task_id: int):
    async with async_session() as session:
        task = await session.get(Task, task_id)
        if task and not task.is_notified:
            await bot.send_message(
                user_id,
                f"🔔 Напоминание о задаче:\n\n"
                f"{task.text}\n"
                f"Запланировано на: {task.due_date.strftime('%d.%m.%Y %H:%M')}"
            )
            task.is_notified = 1
            await session.commit()

# Запланировать все существующие задачи при старте
async def schedule_existing_tasks():
    async with async_session() as session:
        result = await session.execute(select(Task).where(Task.is_notified == 0))
        tasks = result.scalars().all()
        
        for task in tasks:
            if task.due_date > datetime.now():
                scheduler.add_job(
                    send_reminder,
                    DateTrigger(task.due_date),
                    args=(task.user_id, task.id)
                )

# Обработчик команды /start
@dp.message(Command("start"))
async def start_bot(message: types.Message):
    await message.answer("Добро пожаловать!"
    )

# Добавление задачи - шаг 1
@dp.message(F.text == "📝 Добавить задачу")
async def add_task_step1(message: types.Message, state: FSMContext):
    await message.answer("✏️ Введите текст задачи:")
    await state.set_state(TaskStates.waiting_for_task_text)

# Добавление задачи - шаг 2 (получение текста)
@dp.message(TaskStates.waiting_for_task_text)
async def add_task_step2(message: types.Message, state: FSMContext):
    await state.update_data(task_text=message.text)
    await message.answer("📅 Теперь введите дату и время выполнения (формат: ДД.ММ.ГГГГ ЧЧ:ММ)")
    await state.set_state(TaskStates.waiting_for_task_date)

# Добавление задачи - шаг 3 (получение даты)
@dp.message(TaskStates.waiting_for_task_date)
async def add_task_step3(message: types.Message, state: FSMContext):
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        if due_date < datetime.now():
            raise ValueError("Дата в прошлом")
            
        data = await state.get_data()
        
        async with async_session() as session:
            task = Task(
                user_id=message.from_user.id,
                text=data['task_text'],
                due_date=due_date
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            
            # Планируем напоминание
            scheduler.add_job(
                send_reminder,
                DateTrigger(due_date),
                args=(message.from_user.id, task.id)
            )
        
        await message.answer(
            f"✅ Задача сохранена!\n"
            f"Текст: {data['task_text']}\n"
            f"Дата: {due_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"ID задачи: {task.id}"
        )
        await state.clear()
    
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {str(e) or 'Неверный формат даты. Используйте ДД.ММ.ГГГГ ЧЧ:ММ'}")

# Просмотр задач
@dp.message(F.text == "📋 Список задач")
async def list_tasks(message: types.Message):
    async with async_session() as session:
        result = await session.execute(
            select(Task)
            .where(Task.user_id == message.from_user.id)
            .order_by(Task.due_date)
        )
        tasks = result.scalars().all()
        
    if not tasks:
        return await message.answer("У вас нет активных задач")
    
    response = ["Ваши задачи:"]
    for task in tasks:
        status = "🔔 (напоминание запланировано)" if not task.is_notified else "✓ (напоминание отправлено)"
        response.append(
            f"📌 {task.text}\n"
            f"⏰ {task.due_date.strftime('%d.%m.%Y %H:%M')} {status}\n"
            f"ID: {task.id}"
        )
    
    await message.answer("\n\n".join(response))

# Удаление задачи
@dp.message(F.text.regexp(r'^❌ Удалить задачу (\d+)$'))
async def delete_task(message: types.Message):
    task_id = int(message.text.split()[-1])
    
    async with async_session() as session:
        result = await session.execute(
            select(Task).where(
                (Task.id == task_id) & 
                (Task.user_id == message.from_user.id))
        )
        task = result.scalar_one_or_none()
        
        if task:
            # Удаляем задание из планировщика
            for job in scheduler.get_jobs():
                if job.args == (message.from_user.id, task_id):
                    job.remove()
            
            await session.delete(task)
            await session.commit()
            await message.answer(f"Задача #{task_id} удалена")
        else:
            await message.answer("Задача не найдена")

# Запуск бота
async def main():
    await init_db()
    await schedule_existing_tasks()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())