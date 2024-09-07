from discord.ext import commands
import discord, yt_dlp as youtube_dl, os, asyncio
import subprocess
import re
import variables
from concurrent.futures import ThreadPoolExecutor

ffmpeg_path = "C:\\ffmpeg\\bin\\ffmpeg.exe"
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=";", help_command=None, intents=intents)

queuelist = []
filestodelete = []
playback_executor = ThreadPoolExecutor(max_workers=4)

async def delete_message_after(ctx, message, delay=5):
    await asyncio.sleep(delay)
    await ctx.message.delete()

async def delete_files(filenames):
    loop = asyncio.get_event_loop()
    for file in filenames:
        await loop.run_in_executor(None, os.remove, file)

async def check_queue(ctx, voice):
    try:
        if queuelist:
            title = queuelist.pop(0)
            file_path = f"{title}.mp3"
            
            if not os.path.exists(file_path):
                await download_song(title)
            
            await play_audio(ctx, voice, file_path)
            coro = bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=title))
            await asyncio.wait([coro])
            filestodelete.append(file_path)
        else:
            await delete_files(filestodelete)
            filestodelete.clear()
    except Exception as e:
        print(f"Error in check_queue: {e}")

async def play_audio(ctx, voice, file_path):
    loop = asyncio.get_event_loop()

    def after_playing(error):
        if error:
            print(f"Playback error: {error}")
        coro = check_queue(ctx, voice)
        future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        try:
            future.result()
        except Exception as e:
            print(f"Error in after_playing: {e}")

    await loop.run_in_executor(
        playback_executor,
        lambda: voice.play(
            discord.FFmpegPCMAudio(
                source=file_path,
                executable=ffmpeg_path,
                options=""
            ),
            after=after_playing
        )
    )

@bot.command(aliases=["skip"])
async def next(ctx):
    voice = ctx.voice_client
    if voice.is_playing():
        voice.stop()
        message = await ctx.send("Skipped to the next song.")
    else:
        message = await ctx.send("Bot is not playing Audio!")
    await delete_message_after(ctx, message)

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
async def leave(ctx):
    await ctx.voice_client.disconnect()
    message = await ctx.send("Disconnected from the voice channel.")
    await delete_message_after(ctx, message)

def sanitize_filename(title):
    sanitized_title = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', title)
    return sanitized_title

async def download_song(title):
    sanitized_title = sanitize_filename(title)
    filename = f"{sanitized_title}.mp3"

    if not os.path.exists(filename):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f"{sanitized_title}.%(ext)s",
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                },
            ],
        }
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: youtube_dl.YoutubeDL(ydl_opts).download([f"ytsearch:{title}"]))

@bot.command()
async def play(ctx, *, searchword):
    voice = ctx.voice_client

    if not voice:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            voice = await channel.connect()
            await ctx.send(f"Joined {channel}.")
        else:
            message = await ctx.send("You are not connected to a voice channel.")
            await delete_message_after(ctx, message)
            return

    is_url = searchword.startswith(('http', 'www'))
    sanitized_title = None
    file_path = None

    if not is_url:
        sanitized_title = sanitize_filename(searchword)
        file_path = f"{sanitized_title}.mp3"

    if is_url or not os.path.exists(file_path):
        if is_url:
            with youtube_dl.YoutubeDL({}) as ydl:
                info = ydl.extract_info(searchword, download=False)
                title = info["title"]
                url = searchword
        else:
            with youtube_dl.YoutubeDL({}) as ydl:
                info = ydl.extract_info(f"ytsearch:{searchword}", download=False)["entries"][0]
                title = info["title"]
                url = info["webpage_url"]

            sanitized_title = sanitize_filename(title)
            file_path = f"{sanitized_title}.mp3"

        await download_song(title)
    else:
        title = searchword

    if voice.is_playing():
        queuelist.append(title)
        message = await ctx.send(f"Added to Queue: ** {title} **")
    else:
        await play_audio(ctx, voice, file_path)
        message = await ctx.send(f"Playing ** {title} ** :musical_note:")
        filestodelete.append(sanitized_title)
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=title))

@bot.command()
async def pause(ctx):
    voice = ctx.voice_client
    if voice.is_playing():
        voice.pause()
        message = await ctx.send("Audio paused.")
    else:
        message = await ctx.send("Bot is not playing Audio!")
    await delete_message_after(ctx, message)

@bot.command()
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

bot.run(variables.bot_token)
