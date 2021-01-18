import requests
from requests import HTTPError
import datetime
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import os

from api import API_URL, encoded_jwt

load_dotenv()

webhook_url = os.environ['MEETING_WEBHOOK_URL']

meeting_type_colors = {
    'large_group': 14297372,
    'small_group': 6950317,
    'coordinators': 16766720
}

default_meeting_color = None

def fetch_upcoming_meetings():
    format = '%Y-%m-%dT%H:%M:%S'
    start = datetime.datetime.now().strftime(format)
    end = (datetime.datetime.now() + datetime.timedelta(hours=2)).strftime(format)
    r = requests.get(f'{API_URL}/public_meetings', params=[
        ('start_date_time', 'gte.' + start),
        ('start_date_time', 'lte.' + end)
    ])
    r.raise_for_status()
    upcoming_meetings = r.json()

    for meeting in upcoming_meetings:
        if not meeting['is_public']:
            print(f'Skipping non-public meeting {meeting["meeting_id"]}: {meeting["title"]}')
            continue

        meeting_start_date_time = datetime.datetime.strptime(meeting['start_date_time'], format)
        meeting_end_date_time = datetime.datetime.strptime(meeting['end_date_time'], format)

        meeting_type_display = ' '.join(map(str.capitalize, meeting['type'].split('_'))) + ' Meeting'
        date_str = datetime.datetime.strftime(meeting_start_date_time, '%A, %b %-d, %Y')

        color = meeting_type_colors[meeting['type']] if meeting['type'] in meeting_type_colors else default_meeting_color

        time_until = relativedelta(meeting_start_date_time, datetime.datetime.now())

        fields = [
            {
                'name': 'Start',
                'value': datetime.datetime.strftime(meeting_start_date_time, '%-I:%M %p'),
                'inline': True
            },
            {
                'name': 'End',
                'value': datetime.datetime.strftime(meeting_end_date_time, '%-I:%M %p'),
                'inline': True
            },
            {
                'name': 'Location',
                'value': meeting['location'] or 'Not given',
                'inline': True
            },
            {
                'name': 'Agenda',
                'value': '\n'.join(map(lambda s: '- '+s, meeting['agenda'])) if len(meeting['agenda']) else 'Not given',
                'inline': True
            }
        ]

        if meeting['host_username']:
            # Fetch host Discord account
            hr = requests.get(f'{API_URL}/user_accounts', params={
                'username': 'eq.' + meeting['host_username'],
                'type': 'eq.discord'
            }, headers={
                'Authorization': 'Bearer ' + encoded_jwt,
                'Accept': 'application/vnd.pgrst.object+json'
            })
            try:
                hr.raise_for_status()

                host_discord_user_id = hr.json()['account_id']
                fields.append({
                    'name': 'Hosted By',
                    'value': f'<@{host_discord_user_id}>',
                    'inline': True
                })
            except HTTPError as err:
                print(err.response.json())
                print(f'Failed to fetch host Discord account for {meeting["host_username"]}')

        w = requests.post(webhook_url, json={
            'embeds': [{
                'title': meeting['title'] or 'Untitled Meeting',
                'description': f'{meeting_type_display} starting in **{time_until.minutes} minutes**!',
                'fields': fields,
                'color': color,
                'url': f'https://rcos-meetings.herokuapp.com/meetings/{meeting["meeting_id"]}'
            }]
        })

        print(f'{w.status_code} - Sent webhook reminder about {meeting["meeting_id"]} {meeting_type_display}: {meeting["title"]}')

try:
    fetch_upcoming_meetings()
except HTTPError as e:
    print(e)
    print(e.response.json())