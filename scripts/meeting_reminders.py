import requests
from requests import HTTPError
import datetime
from dotenv import load_dotenv
import os

load_dotenv()

api_base_url = 'https://rcos-api.herokuapp.com/api/v1'

headers = {
    'api_key': os.environ['RCOS_API_KEY']
}

webhook_url = os.environ['MEETING_WEBHOOK_URL']

meeting_type_colors = {
    'large_group': 14297372,
    'small_group': 6950317,
    'coordinators': 16766720
}

default_meeting_color = None

def fetch_upcoming_meetings():
    start = datetime.datetime.now()
    end = start + datetime.timedelta(minutes=20)

    r = requests.get(f'{api_base_url}/meetings', params={
        'start_date_time__gte': start,
        'start_date_time__lte': end
    }, headers=headers)

    r.raise_for_status()
    upcoming_meetings = r.json()

    for meeting in upcoming_meetings:
        if not meeting['is_public']:
            print(f'Skipping non-public meeting {meeting["meeting_id"]}: {meeting["title"]}')
            continue

        meeting_start_date_time = datetime.datetime.strptime(meeting['start_date_time'], '%Y-%m-%dT%H:%M:%S')
        meeting_end_date_time = datetime.datetime.strptime(meeting['end_date_time'], '%Y-%m-%dT%H:%M:%S')

        meeting_type_display = ' '.join(map(str.capitalize, meeting['meeting_type'].split('_'))) + ' Meeting'
        date_str = datetime.datetime.strftime(meeting_start_date_time, '%A, %b %-d, %Y')

        color = meeting_type_colors[meeting['meeting_type']] if meeting['meeting_type'] in meeting_type_colors else default_meeting_color

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
                'value': meeting['location'],
                'inline': True
            },
            {
                'name': 'Agenda',
                'value': '\n'.join(map(lambda s: '- '+s, meeting['agenda'])),
                'inline': True
            }
        ]

        if meeting['host_username']:
            # Fetch host Discord account
            hr = requests.get(f'{api_base_url}/users/{meeting["host_username"]}/accounts/discord', headers=headers)
            try:
                hr.raise_for_status()

                host_discord_user_id = hr.json()['account_id']
                fields.append({
                    'name': 'Hosted By',
                    'value': f'<@{host_discord_user_id}>',
                    'inline': True
                })
            except HTTPError as err:
                print(f'Failed to fetch host Discord account for {meeting["host_username"]}')

        w = requests.post(webhook_url, json={
            'embeds': [{
                'title': meeting['title'],
                'description': f'{meeting_type_display} on {date_str}',
                'fields': fields,
                'color': color,
                'url': f'https://meetings.rcos.io/{meeting["meeting_id"]}'
            }]
        })
        print(f'{w.status_code} - Sent webhook reminder about {meeting["meeting_id"]} {meeting_type_display}: {meeting["title"]}')

fetch_upcoming_meetings()