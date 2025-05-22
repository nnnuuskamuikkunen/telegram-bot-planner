from __future__ import print_function
import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


# If modifying these scopes, delete the file token.pickle.
# SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
SCOPES = ['https://www.googleapis.com/auth/calendar']

# ! время начала события -- то, которое ввел пользователь
# ! время окончания -- всегда через час, не менять
# поменять часовой пояс, либо добавить поправку к Сингапуру
# как сделать дату не только текущего дня
#

def book_timeslot(event_description, event_time, input_email):
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            # print(flow)
            # print(flow.run_local_server(port=0))
            # creds = flow.run_local_server(port=0)  # run_local_server -- выводит ссылку для авторизации Please visit this URL
            # print(message)
            # print(type(creds))
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)

    # --------------------- Manipulating Booking Time ----------------------------
    # start_time = str(datetime.datetime.now())[:10] + 'T' + booking_time + ':00+08:00' # booking_time -- часы : мин  дата
    # end_time = str(datetime.datetime.now())[:10] + 'T' + str(int(booking_time[:2]) + 1) + ':00:00+08:00'
    start_time = event_time[:10] + 'T' + event_time[12:] + ':00+05:00'  # booking_time -- часы : мин  дата
    end_time = event_time[:10] + 'T' + event_time[12:] + ':00+05:00'
    # ----------------------------------------------------------------------------

    # Call the Calendar API
    # now = datetime.datetime.now().isoformat() + 'Z'  # 'Z' indicates UTC time
    print('Booking a time slot....')
    print(start_time)
    # events_result = service.events().list(calendarId='primary', timeMin=now,
                                          # maxResults=10, singleEvents=True,
                                          # orderBy='startTime').execute()
    # events = events_result.get('items', [])
    events = dict()
    if not events:
        event = {
            'summary': event_description,
            # 'location': 'Moscow',
            # 'description': str(event_description) + 'with AutomationFeed',
            'start': {
                'dateTime': start_time,
                'timeZone': 'Europe/Moscow',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Europe/Moscow',
            },
             'recurrence': [
               'RRULE:FREQ=DAILY;COUNT=0'
             ],
             'attendees': [
                {'email': 'automationfeed@gmail.com'},
                {'email': str(input_email)},
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }
        # event = service.events().insert(calendarId='primary', body=event).execute()
        # print('Event created: %s' % (event.get('htmlLink')))
        return True

    else:
        # --------------------- Check if there are any similar start time ---------------------
        # for event in events:
            # start = event['start'].get('dateTime', event['start'].get('date'))
            # if start == start_time:
            #     print('Already book....')
            #     return False
        # -------------------- Break out of for loop if there are no apppointment that has the same time ----------
        event = {
            'summary': event_description,
            # 'location': 'Moscow',
            # 'description': str(event_description) + 'with AutomationFeed',
            'start': {
                'dateTime': start_time,
                'timeZone': 'Europe/Moscow',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Europe/Moscow',
            },
            'recurrence': [
                'RRULE:FREQ=DAILY;COUNT=1'
            ],
             'attendees': [
                 {'email': 'automationfeed@gmail.com'},
                {'email': str(input_email)},
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }
        # event = service.events().insert(calendarId='primary', body=event).execute()
        # print('Event created: %s' % (event.get('htmlLink')))
        return True

# def check_email(email):
#     regex = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
#     # regex = '[a-z]([\.-]*[a-z]*)*@gmail.com'
#     if(re.search(regex,email)):
#         print("Valid Email")
#         return True
#     else:
#         print("Invalid Email")
#         return False

# if __name__ == '__main__':
    # input_email = 'avstrpeg@gmail.com'
    # event_time = '2025-05-26 01:00'
    # result = book_timeslot('Dye', event_time, input_email)

# Please visit this URL to authorize this application: https://accounts.google.com/o/oauth2/auth?response_type=code&client_id=132942191562-8cstck6d6j5k6f01d57k22higucrg4v4.apps.googleusercontent.com&redirect_uri=http%3A%2F%2Flocalhost%3A53869%2F&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcalendar&state=3TUECAlwB5dq3NlymQ0GzwD4sjohGD&access_type=offline

# без if __name__ == '__main__': никакого вывода, Process finished with exit code 0