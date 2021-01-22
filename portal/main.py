import os

import pytz
import requests
from dotenv import load_dotenv
from flask import (Flask, g, flash, redirect, render_template, request, session,
                   url_for, abort)
from flask_cas import CAS, login_required, logout
from flask_talisman import Talisman
from werkzeug.exceptions import HTTPException

from .discord import (OAUTH_URL, SERVER_ID, VERIFIED_ROLE_ID,
                     add_role_to_member, add_user_to_server, get_member,
                     get_tokens, get_user_info, kick_member_from_server,
                     set_member_nickname)
from .rcos import (delete_user_discord_account, fetch_user,
                  fetch_user_discord_account, upsert_user, upsert_user_discord_account)

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

@app.before_request
def before_request():
    '''Runs before every request.'''

    # Try to fetch user
    if 'user' not in session and cas.username:
        session['user'] = fetch_user(cas.username.lower())

    # Try to fetch user's discord account
    if ('user_discord_account' not in session or session['user_discord_account'] is None) and cas.username:
        session['user_discord_account'] = fetch_user_discord_account(cas.username.lower())

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/join', methods=['GET', 'POST'])
def join():
    is_logged_in = cas.username is not None
    username = cas.username.lower() if is_logged_in else None
    user = session['user'] if is_logged_in else None
    
    if request.method == 'GET':
        if is_logged_in:
            app.logger.info(f'Home page requested by RPI user {cas.username}')
        else:
            app.logger.info(f'Home page requested by external user')

        # Already connected to Discord!
        if session['user_discord_account']:
            return redirect(url_for('joined'))

        return render_template('join.html', is_logged_in=is_logged_in, user=user, username=username, timezones=pytz.all_timezones)
    elif request.method == 'POST':
        # Limit to 20 characters so overall Discord nickname doesn't exceed limit of 32 characters
        first_name = request.form['first_name'].strip()[:20]
        last_name = request.form['last_name'].strip()
        graduation_year = int(request.form['graduation_year'].strip())

        if len(first_name) == 0 or len(last_name) == 0:
            flash('Nice try... Please enter a name.', category='error')
            return redirect(url_for('index'))

        if graduation_year > 2038 or graduation_year < 2000:
            flash('Nice try... Stick to the allowed graduation year range.', category='error')
            return redirect(url_for('index'))


        user = {
            'first_name': first_name,
            'last_name': last_name,
            'graduation_year': graduation_year,
            'timezone': request.form['timezone']
        }
        
        # This will either create or update the user
        session['user'] = upsert_user(cas.username.lower(), user)

        app.logger.info(f'Redirecting {cas.username} to Discord OAuth page')
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
                f'{cas.username} declined to connect their Discord account')
            return render_template('error.html', error='You declined to connect your Discord account!')
        else:
            # Handle generic Discord error
            error_description = request.args.get('error_description')
            app.logger.error(
                f'An error occurred on the Discord callback for {cas.username}: {error_description}')
            raise Exception(error_description)

    # Get user from DB
    user = session['user']

    # Generate nickname as "<first name> <last name initial> '<2 digit graduation year> (<rcs id>)"
    # e.g. "Frank M '22 (matraf)"
    nickname = user['first_name'] + ' ' + \
        user['last_name'][0] + " '" + str(user['graduation_year'])[2:] + \
        f' ({cas.username.lower()})'

    # Exchange authorization code for tokens
    tokens = get_tokens(authorization_code)

    # Get info on the Discord user that just connected (really only need id)
    discord_user = get_user_info(tokens['access_token'])

    # Save to DB
    upsert_user_discord_account(user['username'], discord_user['id'])

    # Add them to the server
    add_user_to_server(tokens['access_token'],
                        discord_user['id'], nickname)
    app.logger.info(f'Added {cas.username} to Discord server')

    # Set their nickname
    try:
        set_member_nickname(discord_user['id'], nickname)
        app.logger.info(
            f'Set {cas.username}\'s nickname to "{nickname}" on server')
    except requests.exceptions.HTTPError as e:
        app.logger.warning(
            f'Failed to set nickname "{nickname}" to {cas.username} on server: {e}')

    # Give them the verified role
    try:
        add_role_to_member(discord_user['id'], VERIFIED_ROLE_ID)
        app.logger.info(f'Added verified role to {cas.username} on server')
    except requests.exceptions.HTTPError as e:
        app.logger.warning(
            f'Failed to add role to {cas.username} on server: {e}')

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
    discord_member = get_member(session['user_discord_account']['account_id'])
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
