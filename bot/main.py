import os

from discord.ext import commands
from discord.ext.commands.context import Context
from dotenv import load_dotenv

load_dotenv()

bot = commands.Bot(command_prefix='?')

@bot.event
async def on_ready():
    print(f'Logged in as @{bot.user.name}: <@{bot.user.id}>')

@bot.command()
async def poll(ctx: Context, title: str, *options):
    '''Create a poll with a title and up to 9 options'''
    if len(options) == 0:
        return await ctx.send_help('poll')
    if len(options) > 9:
        return await ctx.reply(f'Plase give up to **9** options! You gave {len(options)}.')

    lines = [f'Poll: **{title}**\n']
    emojis = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣']
    for i in range(len(options)):
        lines.append(f'{emojis[i]} - {options[i]}')
    poll_message = await ctx.send('\n'.join(lines))
    for i in range(len(options)):
        await poll_message.add_reaction(emojis[i])

@bot.command()
async def code(ctx: Context):
    '''Send direct link to bot's source code'''
    await ctx.reply('https://github.com/rcos/rcos-discord')

bot.run(os.environ['DISCORD_BOT_TOKEN'])
