#!/usr/bin/python

import os
import discord
from discord.ext import commands
import requests
import datetime
import random
import psycopg2
from psycopg2.extras import DictCursor
import re
import string

db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_user = os.getenv('DB_USER')
db_pass = os.getenv('DB_PASS')
db_name = os.getenv('DB_NAME')
if not db_host or not db_port or not db_user or not db_pass or not db_name:
    raise RuntimeError('Incorrect database configuration')

mailgun_key = os.getenv('MAILGUN_KEY')
mailgun_host = os.getenv('MAILGUN_HOST')
mailgun_email = os.getenv('MAILGUN_EMAIL')
if not mailgun_key or not mailgun_host or not mailgun_email:
    raise RuntimeError('Incorrect mailgun configuration')

bot_token = os.getenv('BOT_TOKEN')
if not bot_token:
    raise RuntimeError('<BOT_TOKEN> environment variable is not set')

prefix = os.getenv('BOT_PREFIX')
if not prefix:
    prefix = '!kickstarter '

server_id = os.getenv('SERVER_ID')
if not server_id:
    raise RuntimeError('<SERVER_ID> environment variable is not set')
else:
    try:
        server_id = int(server_id)
    except:
        raise RuntimeError(
            'Invalid <SERVER_ID> environment variable: should be number')

server_invite_link = os.getenv('SERVER_INVITE_LINK')
if not server_invite_link:
    raise RuntimeError('<SERVER_INVITE_LINK> environment variable is not set')

client = commands.Bot(command_prefix=prefix)

@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.idle, activity=discord.Game('Listening to {0}help'.format(prefix)))
    print('I am online')


@client.event
async def on_command_error(ctx: commands.Context, error: str):
    await ctx.message.reply('Unknown error!\nPlease check my role is above any user roles in server settings.\nOtherwise contact developer.')
    print(error)


# region Backer Roles
class BackerVerification(commands.Cog, name='Backer verification'):
    @client.command(brief='Backer verification help')
    async def backer_help(self, ctx: commands.Context):
        log_command(ctx.message.author, 'backer_help')

        msg = 'This bot will help you identify yourself as a backer and obtain access to Discord\'s private channels.\r\r' \
            'In order to start the process, you\'ll need to know the email you\'ve used to back our project. That would be ' \
            'your Kickstarter email, PayPal email or your Facebook email if you have your Kickstarter and Facebook ' \
            'accounts linked.\r\r' \
            'Send me the following command: \r\r' \
            '{0}backer_mail email@example.com'.format(prefix)
        if ctx.message.channel.is_private:
            await ctx.send(msg)
        else:
            await ctx.message.delete()
            try:
                await ctx.message.author.send(msg)
            except discord.errors.Forbidden:
                await ctx.reply(ctx.message.channel, '{0} you have disabled direct messages '
                                                            'from this server members. '
                                                            'Please, allow them temporarily so we can start the process.'
                                    .format(ctx.message.author.mention))


    @client.command(brief='Initiate backer\'s email verification')
    async def backer_mail(self, ctx: commands.Context, email: str):
        log_command(ctx.message.author, 'backer_mail', email)

        # Only works if we're on a private message
        if ctx.message.channel.is_private:
            # Check if email is valid
            if valid_email(email):
                # Check the Database and see if we have the email.
                # Also check it we already sent a verification code and send the same one
                db = db_connect()
                try:
                    with db.cursor() as cursor:
                        cursor.execute('SELECT `verification_code` FROM `backers` WHERE `email`=%s', email)
                        result = cursor.fetchone()

                        token = None

                        if result is None:
                            # User doesn't exists in the database. Throw an error.
                            await ctx.send('The email address is not registered as a valid backer. '
                                        'Please, make sure you\'ve entered the right email.\r\r')
                        elif result['verification_code'] is None:
                            # User hasn't started the verified proccess previously. Generate a new verifiy token.
                            token = generate_random_string(40)

                            # Save the token on the database.
                            cursor.execute('UPDATE `backers` SET `verification_code`=%s'
                                        ' WHERE `email`=%s', (token, email))
                            db.commit()
                        else:
                            # Get previous token and reuse it.
                            # token = result['verification_code']
                            ctx.send('We\'ve already send you verification email, please check your inbox and spam folder.')

                        if token is not None:
                            # Send an email with the token and say the instructions to verify it.
                            requests.post('https://api.mailgun.net/v2/{0}/messages'.format(mailgun_host),
                                        auth=('api', mailgun_key),
                                        data={
                                            'from': '{0}'.format(mailgun_email),
                                            'to': email,
                                            'subject': 'Discord: Email Verification',
                                            'html': 'Hello Backer! <br/><br/>'
                                                    'This is a confirmation email to verify you as one of our '
                                                    'backers. In order to confirm you as a backer, please go to Discord '
                                                    'and send the following message to BackersBot: <br/><br/>'
                                                    '{0}backer_verify {1} {2}'.format(prefix, email, token)
                                        })

                            await ctx.send('Welcome backer! Just one more step to access the backer-exclusive channels. '
                                        'Please, check your email for the verification code we just sent you (please '
                                        'check your spam folder too just in case) and send '
                                        'me back the following command:\r\r'
                                        '{0}backer_verify {1} verification_code_here'
                                        .format(prefix, email))
                finally:
                    cursor.close()
                    db.close()
            else:
                await ctx.send('The email address looks like it\'s invalid. '
                            'Please, make sure you enter a valid email address.')
        else:
            await ctx.message.delete()
            try:
                await ctx.message.author.send('That command only works on private message. '
                                            'Please send me the command again.')
            except discord.errors.Forbidden:
                await ctx.reply(ctx.message.channel, '{0} you have disabled direct messages '
                                'from this server members. '
                                'Please, allow them temporarily so we can start the process.'
                                .format(ctx.message.author.mention))


    @client.command(brief='Verify backer\'s email')
    async def backer_verify(self, ctx: commands.Context, email: str, token: str):
        log_command(ctx.message.author, 'backer_verify', email, token)

        # Only works if we're on a private message
        if ctx.message.channel.is_private:
            # Connect to the database and check if the email-token is correct
            db = db_connect()
            try:
                with db.cursor() as cursor:
                    cursor.execute('SELECT `discord_user_id`, `role_id` FROM `backers` WHERE `email`=%s'
                                ' AND `verification_code`=%s',
                                (email, token))
                    result = cursor.fetchone()

                    if result is None:
                        # User doesn't exists in the database. Throw an error.
                        await ctx.send('The combination of user and verification code doesn\'t exist. '
                                    'Please, make sure you\'ve entered the right email and code.\r\r')
                    elif result['discord_user_id'] == ctx.message.author.id:
                        # The user is already registered
                        server = client.get_guild(id=server_id)
                        server_member = discord.utils.get(server.members, id=ctx.message.author.id)
                        if server_member is not None:
                            server_role = discord.utils.get(server.roles, id=result['role_id'])
                            await server_member.add_roles(server_role)

                        await ctx.send('You\'ve already been confirmed as a backer.')
                    elif result['discord_user_id'] is not None:
                        # Someone already registered this email.
                        await ctx.send('It looks like this email has already been registered by another user.')
                    else:
                        # Check if the user has joined server
                        server = client.get_guild(id=server_id)
                        server_member = discord.utils.get(server.members, id=ctx.message.author.id)
                        if server_member is not None:
                            # Update the database to register this user as taken
                            cursor.execute('UPDATE `backers` SET `discord_user_id`=%s'
                                        ' WHERE `email`=%s AND `verification_code`=%s',
                                        (ctx.message.author.id, email, token))
                            db.commit()

                            server_role = discord.utils.get(server.roles, id=result['role_id'])

                            await server_member.add_roles(server_role)
                            await ctx.send(
                                'Congratulations! You just completed the process and you\'ve been confirmed as '
                                'a **{0}** tier backer.'
                                .format(server_role.name))
                        elif server_invite_link:
                            await ctx.send(
                                'You haven\'t joined our Discord server! You should join it first and then come '
                                'back and run the command again.\r\r'
                                'Please, join the server here: {0}'.format(server_invite_link))
            finally:
                cursor.close()
                db.close()
        else:
            await ctx.message.delete()
            try:
                await ctx.message.author.send('That command only works on private message. '
                                            'Please send me the command again.')
            except discord.errors.Forbidden:
                await ctx.reply(ctx.message.channel, '{0} you have disabled direct messages '
                                'from this server members. '
                                'Please, allow them temporarily so we can start the process.'
                                .format(ctx.message.author.mention))
# endregion


# region Util
def log_command(author: discord.Member, command_name: str, *args):
    args_str = ' '.join(str(arg) for arg in args)
    if len(args_str) > 0: args_str = ' ' + args_str
    print('Processed command: {0}{1} by {2}'.format(command_name, args_str, author.id))


def valid_email(email):
    return re.match(r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)', email)


def db_connect():
    # Connect to the database
    return psycopg2.connect(host=db_host,
                            port=db_port,
                            user=db_user,
                            password=db_pass,
                            dbname=db_name,
                            cursor_factory=DictCursor,
                            sslmode='require')


def generate_random_string(size = 20, chars = string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
# endregion


client.add_cog(BackerVerification(client))
client.run(bot_token)
