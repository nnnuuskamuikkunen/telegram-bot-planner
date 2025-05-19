import os
import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Google OAuth2 flow setup
flow = Flow.from_client_config(
    client_config={
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://accounts.google.com/o/oauth2/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    },
    scopes=["https://www.googleapis.com/auth/calendar"],
)


# States for event creation
class EventCreation(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_duration = State()


# Database simulation (in production use a real database)
user_credentials = {}
user_events = {}


@router.message(Command("start"))
async def start_command(message: Message):
    """Handle the /start command"""
    welcome_text = (
        "👋 Welcome to Calendar Bot!\n\n"
        "I can help you create events and sync them with your Google Calendar.\n\n"
        "Available commands:\n"
        "/connect - Connect your Google account\n"
        "/create_event - Create a new event\n"
        "/my_events - View your upcoming events"
    )
    await message.answer(welcome_text)


@router.message(Command("connect"))
async def connect_google_account(message: Message):
    """Initiate Google OAuth2 flow"""
    # Generate authorization URL
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    # Store the state for this user
    user_credentials[message.from_user.id] = {"oauth_state": state}

    # Create inline keyboard with authorization link
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🔗 Connect Google Account",
        url=authorization_url
    ))
    builder.add(types.InlineKeyboardButton(
        text="✅ I've connected",
        callback_data="oauth_complete"
    ))

    await message.answer(
        "Please connect your Google account by clicking the button below:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "oauth_complete")
async def oauth_complete(callback: CallbackQuery):
    """Handle OAuth completion confirmation"""
    user_id = callback.from_user.id
    if user_id not in user_credentials or "oauth_state" not in user_credentials[user_id]:
        await callback.answer("Please start the connection process with /connect")
        return

    await callback.message.edit_text(
        "Great! Now you can create events that will sync with your Google Calendar."
    )
    await callback.answer()


async def handle_authorization_code(user_id: int, authorization_response: str):
    """Exchange authorization code for tokens"""
    try:
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials

        # Store credentials for the user
        user_credentials[user_id] = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }

        return True
    except Exception as e:
        print(f"Error exchanging token: {e}")
        return False


@router.message(Command("create_event"))
async def create_event_start(message: Message, state: FSMContext):
    """Start the event creation process"""
    user_id = message.from_user.id

    # Check if user is connected to Google
    if user_id not in user_credentials or "token" not in user_credentials[user_id]:
        await message.answer("Please connect your Google account first with /connect")
        return

    await state.set_state(EventCreation.waiting_for_title)
    await message.answer("Let's create a new event! First, what's the title of the event?")


@router.message(EventCreation.waiting_for_title)
async def process_event_title(message: Message, state: FSMContext):
    """Process event title"""
    await state.update_data(title=message.text)
    await state.set_state(EventCreation.waiting_for_description)
    await message.answer("Great! Now please provide a description for the event:")


@router.message(EventCreation.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext):
    """Process event description"""
    await state.update_data(description=message.text)
    await state.set_state(EventCreation.waiting_for_date)
    await message.answer("When is the event? Please provide the date in YYYY-MM-DD format:")


@router.message(EventCreation.waiting_for_date)
async def process_event_date(message: Message, state: FSMContext):
    """Process event date"""
    try:
        date = datetime.datetime.strptime(message.text, "%Y-%m-%d").date()
        await state.update_data(date=date)
        await state.set_state(EventCreation.waiting_for_time)
        await message.answer("What time does the event start? (HH:MM, 24-hour format):")
    except ValueError:
        await message.answer("Invalid date format. Please use YYYY-MM-DD:")


@router.message(EventCreation.waiting_for_time)
async def process_event_time(message: Message, state: FSMContext):
    """Process event time"""
    try:
        time = datetime.datetime.strptime(message.text, "%H:%M").time()
        data = await state.get_data()
        date = data['date']
        datetime_start = datetime.datetime.combine(date, time)

        await state.update_data(datetime_start=datetime_start)
        await state.set_state(EventCreation.waiting_for_duration)
        await message.answer("How long is the event in minutes? (e.g., 60 for 1 hour):")
    except ValueError:
        await message.answer("Invalid time format. Please use HH:MM (24-hour format):")


@router.message(EventCreation.waiting_for_duration)
async def process_event_duration(message: Message, state: FSMContext):
    """Process event duration and create the event"""
    try:
        duration = int(message.text)
        data = await state.get_data()

        # Calculate end time
        datetime_start = data['datetime_start']
        datetime_end = datetime_start + datetime.timedelta(minutes=duration)

        # Prepare event data
        event_data = {
            'title': data['title'],
            'description': data.get('description', ''),
            'start': datetime_start,
            'end': datetime_end
        }

        # Create event in Google Calendar
        success = await create_google_calendar_event(message.from_user.id, event_data)

        if success:
            # Store event locally
            if message.from_user.id not in user_events:
                user_events[message.from_user.id] = []
            user_events[message.from_user.id].append(event_data)

            await message.answer(
                f"✅ Event '{data['title']}' created successfully!\n"
                f"📅 Date: {datetime_start.strftime('%Y-%m-%d %H:%M')}\n"
                f"⏳ Duration: {duration} minutes"
            )
        else:
            await message.answer("Failed to create event in Google Calendar. Please try again.")

        await state.clear()
    except ValueError:
        await message.answer("Please enter a valid number for duration (in minutes):")


async def create_google_calendar_event(user_id: int, event_data: dict) -> bool:
    """Create an event in Google Calendar"""
    if user_id not in user_credentials:
        return False

    try:
        # Load credentials from storage
        creds_data = user_credentials[user_id]
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )

        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Update stored credentials
            user_credentials[user_id]['token'] = creds.token
            user_credentials[user_id]['expiry'] = creds.expiry.isoformat()

        # Build Google Calendar service
        service = build('calendar', 'v3', credentials=creds)

        # Create event
        event = {
            'summary': event_data['title'],
            'description': event_data['description'],
            'start': {
                'dateTime': event_data['start'].isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': event_data['end'].isoformat(),
                'timeZone': 'UTC',
            },
        }

        # Insert event
        event = service.events().insert(calendarId='primary', body=event).execute()
        return True

    except Exception as e:
        print(f"Error creating Google Calendar event: {e}")
        return False


@router.message(Command("my_events"))
async def list_upcoming_events(message: Message):
    """List upcoming events from Google Calendar"""
    user_id = message.from_user.id

    # Check if user is connected to Google
    if user_id not in user_credentials or "token" not in user_credentials[user_id]:
        await message.answer("Please connect your Google account first with /connect")
        return

    try:
        # Load credentials from storage
        creds_data = user_credentials[user_id]
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )

        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Update stored credentials
            user_credentials[user_id]['token'] = creds.token
            user_credentials[user_id]['expiry'] = creds.expiry.isoformat()

        # Build Google Calendar service
        service = build('calendar', 'v3', credentials=creds)

        # Get upcoming events
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            await message.answer("No upcoming events found.")
            return

        response = ["📅 Your upcoming events:"]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            response.append(
                f"\n📌 {event['summary']}\n"
                f"🕒 {start} - {end}\n"
                f"📝 {event.get('description', 'No description')}"
            )

        await message.answer("\n".join(response))

    except Exception as e:
        print(f"Error listing events: {e}")
        await message.answer("Failed to fetch events from Google Calendar. Please try again.")


async def on_startup():
    """Run on bot startup"""
    print("Bot has started")


async def on_shutdown():
    """Run on bot shutdown"""
    print("Bot is shutting down")


async def main():
    """Main function to start the bot"""
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())