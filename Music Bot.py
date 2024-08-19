from discord.ext import commands
import discord, yt_dlp as youtube_dl, os, asyncio
import subprocess
import re


print(os.getenv('PATH'))

subprocess.run(["C:/ffmpeg/bin/ffmpeg", "-version"])

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=";", help_command=None, intents=intents)
queuelist = []
filestodelete = []

async def delete_message_after(ctx, message, delay=5):
    await asyncio.sleep(delay)
    await ctx.message.delete()

async def check_queue(ctx, voice):
    try:
        if queuelist:
            title = queuelist.pop(0)
            file_path = f"{title}.mp3"
            voice.play(discord.FFmpegPCMAudio(file_path), after=lambda e: asyncio.run_coroutine_threadsafe(check_queue(ctx, voice), bot.loop))
            coro = bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=title))
            await asyncio.wait([coro])
            filestodelete.append(title)
        else:
            for file in filestodelete:
                os.remove(f"{file}.mp3")
            filestodelete.clear()
    except Exception as e:
        print(f"Error in check_queue: {e}")

@bot.command()
async def join(ctx):
    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    message = await ctx.send("Joined the voice channel.")
    await delete_message_after(ctx, message)

@bot.command()
async def leave(ctx, help="leaves the Voice Channel"):
    await ctx.voice_client.disconnect()
    message = await ctx.send("Disconnected from the voice channel.")
    await delete_message_after(ctx, message)

def sanitize_filename(title):
    # Remove unwanted characters and ensure only one '.mp3' extension
    sanitized_title = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', title)  # Remove invalid characters
    return sanitized_title

def download(url, title):
    sanitized_title = sanitize_filename(title)
    filename = f"{sanitized_title}.mp3"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{sanitized_title}.%(ext)s",  # Use a template that does not include '.mp3'
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            },
        ],
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

@bot.command()
async def play(ctx, *, searchword):
    ydl_opts = {}
    voice = ctx.voice_client

    if searchword.startswith(('http', 'www')):
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(searchword, download=False)
            title = info["title"]
            url = searchword
    else:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{searchword}", download=False)["entries"][0]
            title = info["title"]
            url = info["webpage_url"]

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download, url, title)

    sanitized_title = sanitize_filename(title)
    file_path = f"{sanitized_title}.mp3"

    if voice.is_playing():
        queuelist.append(title)
        message = await ctx.send(f"Added to Queue: ** {title} **")
    else:
        voice.play(discord.FFmpegPCMAudio(file_path), after=lambda e: asyncio.create_task(check_queue(ctx, voice)))
        message = await ctx.send(f"Playing ** {title} ** :musical_note:")
        filestodelete.append(sanitized_title)
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=title))

    await delete_message_after(ctx, message)

@bot.command()
async def pause(ctx):
    voice = ctx.voice_client
    if voice.is_playing():
        voice.pause()
        message = await ctx.send("Audio paused.")
    else:
        message = await ctx.send("Bot is not playing Audio!")
    await delete_message_after(ctx, message)

@bot.command(aliases=["skip"])
async def stop(ctx):
    voice = ctx.voice_client
    if voice.is_playing():
        voice.stop()
        message = await ctx.send("Audio stopped.")
    else:
        message = await ctx.send("Bot is not playing Audio!")
    await delete_message_after(ctx, message)

@bot.command()
async def resume(ctx):
    voice = ctx.voice_client
    if voice.is_playing():
        message = await ctx.send("Bot is already playing Audio!")
    else:
        voice.resume()
        message = await ctx.send("Audio resumed.")
    await delete_message_after(ctx, message)

@bot.command()
async def viewqueue(ctx):
    message = await ctx.send(f"Queue:  ** {str(queuelist)} ** ")
    await delete_message_after(ctx, message)

@join.error
@leave.error
@play.error
@stop.error
@resume.error
@pause.error
async def errorhandler(ctx, error):
    if isinstance(error, commands.errors.CommandInvokeError):
        await ctx.send("An error occurred while processing the command.")

bot.run("MTI3NTE0ODY1NTc2NjAxNjA2Mw.GqVb7s.OSAedJhIv_bQNHb9dMfX2Ug8uQyqXF-Rz1L3ms")
