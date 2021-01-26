import os

import pytz
import requests
from dotenv import load_dotenv
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from flask_cas import CAS, login_required, logout
from flask_talisman import Talisman
from requests.models import HTTPError
from werkzeug.exceptions import HTTPException

from .discord import (OAUTH_URL, SERVER_ID, VERIFIED_ROLE_ID,
                      add_role_to_member, add_user_to_server, get_member,
                      get_tokens, get_user_info, kick_member_from_server,
                      set_member_nickname)
from .rcos import (delete_user_discord_account, fetch_user,
                   fetch_user_discord_account, create_or_update_user,
                   create_or_update_user_discord_account)

# Load .env into os.environ
load_dotenv()

app = Flask(__name__)
cas = CAS(app, '/cas')

csp = {
    'default-src': [
        '\'self\'',
        '\'unsafe-inline\'',
        'discord.com',
        '*.discordapp.com',
        'apexal.github.io',
        '*.googleapis.com',
        '*.gstatic.com'
    ]
}
Talisman(app, content_security_policy=csp)

app.secret_key = os.environ.get('FLASK_SECRET_KEY')
app.config['SITE_TITLE'] = os.environ.get('SITE_TITLE')
app.config['CAS_SERVER'] = 'https://cas-auth.rpi.edu/cas'
app.config['CAS_AFTER_LOGIN'] = 'join'

DISCORD_SERVER_INVITE_URL = os.environ.get('DISCORD_SERVER_INVITE_URL')


@app.before_request
def before_request():
    '''Runs before every request.'''

    # Try to fetch user
    if 'user' not in session and cas.username:
        session['user'] = fetch_user(cas.username.lower())
    # Try to fetch user's discord account
    if ('user_discord_account' not in session or session['user_discord_account'] is None) and cas.username:
        session['user_discord_account'] = fetch_user_discord_account(
            cas.username.lower())

    g.is_logged_in = cas.username is not None
    g.username = cas.username.lower() if g.is_logged_in else None
    g.user = session['user'] if 'user' in session else None
    g.identifier = f'RPI user {g.username}' if g.is_logged_in else 'external user '


@app.route('/')
def index():
    if g.is_logged_in:
        return redirect(url_for('join'))
    return render_template('index.html', discord_server_invite_url=DISCORD_SERVER_INVITE_URL)


@app.route('/join', methods=['GET', 'POST'])
@login_required
def join():
    if request.method == 'GET':
        # Already connected to Discord!
        if 'user_discord_account' in session and session['user_discord_account']:
            return redirect(url_for('joined'))

        return render_template('join.html', is_logged_in=True, is_student=True, username=g.username, user=g.user, timezones=pytz.all_timezones)
    elif request.method == 'POST':
        # Limit to 20 characters so overall Discord nickname doesn't exceed limit of 32 characters
        first_name = request.form['first_name'].strip()[:20]
        last_name = request.form['last_name'].strip()

        if len(first_name) == 0 or len(last_name) == 0:
            flash('Nice try... Please enter a name.', category='error')
            return redirect(url_for('index'))

        user = {
            'username': g.username,
            'first_name': first_name,
            'last_name': last_name,
            'role': 'student',
            'timezone': request.form['timezone']
        }

        if 'graduation_year' in request.form and len(request.form['graduation_year']):
            graduation_year = int(request.form['graduation_year'].strip())
            if graduation_year > 2038 or graduation_year < 2000:
                flash(
                    'Nice try... Stick to the allowed graduation year range.', category='error')
                return redirect(url_for('index'))

            user['cohort'] = graduation_year - 4

            # This will ensure the user now exists
            session['user'] = create_or_update_user(g.username, user)

        app.logger.info(f'Redirecting {g.identifier} to Discord OAuth page')
        return redirect(OAUTH_URL)


@app.route('/discord/callback', methods=['GET'])
@login_required
def discord_callback():
    # Extract code or error from URL
    authorization_code = request.args.get('code')
    error = request.args.get('error')

    if error:
        # Handle the special case where the user declined to connect
        if error == 'access_denied':
            app.logger.error(
                f'{g.identifier} declined to connect their Discord account')
            return render_template('error.html', error='You declined to connect your Discord account!')
        else:
            # Handle generic Discord error
            error_description = request.args.get('error_description')
            app.logger.error(
                f'An error occurred on the Discord callback for {g.identifier}: {error_description}')
            raise Exception(error_description)

    # Get user from DB
    user = session['user']

    # Generate nickname as "<first name> <last name initial> '<2 digit graduation year>"
    # e.g. "Frank M '22"
    nickname = user['first_name'] + ' ' + \
        user['last_name'][0]

    if user['cohort']:
        nickname += " '" + str(user['cohort'] + 4)[2:]

    # Exchange authorization code for tokens
    tokens = get_tokens(authorization_code)

    # Get info on the Discord user that just connected (really only need id)
    discord_user = get_user_info(tokens['access_token'])

    # Save to DB
    create_or_update_user_discord_account(user['username'], discord_user['id'])

    # Add them to the server
    add_user_to_server(tokens['access_token'],
                       discord_user['id'], nickname)
    app.logger.info(f'Added {g.identifier} to Discord server')

    # Set their nickname
    try:
        set_member_nickname(discord_user['id'], nickname)
        app.logger.info(
            f'Set {g.username}\'s nickname to "{nickname}" on server')
    except requests.exceptions.HTTPError as e:
        app.logger.warning(
            f'Failed to set nickname "{nickname}" to {g.username} on server: {e}')

    # Give them the verified role
    try:
        add_role_to_member(discord_user['id'], VERIFIED_ROLE_ID)
        app.logger.info(f'Added verified role to {g.username} on server')
    except requests.exceptions.HTTPError as e:
        app.logger.warning(
            f'Failed to add role to {g.username} on server: {e}')

    return redirect(url_for('joined'))


@app.route('/discord/reset')
@login_required
def reset_discord():
    discord_user_id = session['user_discord_account']['account_id']

    # Attempt to kick member from server and then remove DB records
    try:
        kick_member_from_server(discord_user_id)
        delete_user_discord_account(session['user']['username'])
        session['user_discord_account'] = None
    except:
        raise Exception('Failed to kick your old account from the server.')

    return redirect('/')


@app.route('/joined')
@login_required
def joined():
    # Hasn't connected yet, redirect to form
    if session['user_discord_account'] is None:
        return redirect('/')
    try:
        discord_member = get_member(session['user_discord_account']['account_id'])
    except HTTPError as err:
        if err.response.status_code == 404:
            # User disconnected Discord through a different means than this website... REMOVE THEIR RECORD
            delete_user_discord_account(session['user']['username'])
            session['user_discord_account'] = None
            return redirect(url_for('join'))
        raise err

    return render_template('joined.html', rcs_id=cas.username.lower(), user=session['user'], discord_member=discord_member, discord_server_id=SERVER_ID)


@app.errorhandler(404)
def page_not_found(e):
    '''Render 404 page.'''
    return render_template('404.html'), 404


@app.errorhandler(Exception)
def handle_exception(e):
    '''Handles all unhandled exceptions.'''

    # Handle HTTP errors
    if isinstance(e, HTTPException):
        return render_template('error.html', error=e), e.code

    # Handle non-HTTP errors
    app.logger.exception(e)

    # Hide error details in production
    if app.env == 'production':
        e = 'Something went wrong... Please try again later.'

    return render_template('error.html', error=e), 500
