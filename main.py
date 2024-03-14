import asyncio

import discord
import os

from discord.ext import commands
from discord.ext.commands.context import Context

from ydl import YTDLSource

# discord.opus.load_opus("libopus.so")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot('$', intents=intents)


def default_embed_msg(title: str, description: str = None, url: str = None, footer: str = None):
    e = discord.Embed(
        color=discord.Colour.orange(),
        title=title,
        description=description,
        url=url,
    )
    e.set_footer(text=footer)
    return e


def default_error_msg(title: str):
    return discord.Embed(
        title=title,
        color=discord.Colour.red()
    )


class MusicPlayer:
    def __init__(self):
        self.end_playing = asyncio.Event()
        self.queue: list[YTDLSource] = []
        self.worker: asyncio.Task | None = None
        self.vc: discord.VoiceClient | None = None
        self.playing_now: YTDLSource | None = None

    async def add(self, ctx: Context, player: YTDLSource):
        self.queue.append(player)
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self.player(ctx), name='Player')

    async def player(self, ctx: Context):
        while len(self.queue) > 0:
            self.vc = ctx.voice_client

            if self.vc is None:
                self.vc = await ctx.author.voice.channel.connect()

            self.playing_now = self.queue.pop(0)
            await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening,
                                                                name=self.playing_now.title))

            await ctx.send(embed=default_embed_msg(
                title=self.playing_now.title,
                description='Now playing',
                url=self.playing_now.url
            ))
            self.vc.play(self.playing_now, after=lambda e: self.send_end_playing())

            await self.end_playing.wait()

    def send_end_playing(self):
        self.playing_now = None
        self.end_playing.set()
        self.end_playing.clear()


music_player = MusicPlayer()


@bot.command()
async def ping(ctx: Context):
    await ctx.send('pong')


@bot.command()
async def play(ctx: Context, url: str = None):
    if url is None:
        return await resume(ctx)
    async with ctx.typing():
        if ctx.author.voice is None:
            return await ctx.send(embed=default_error_msg('You must join voice channel to play...'))

        player = await YTDLSource.from_url(url, stream=True)
        await music_player.add(ctx, player)
        await ctx.send(embed=default_embed_msg(
            title=player.title,
            description='Successfully added to queue',
            url=player.url
        ))


@bot.command()
async def queue(ctx: Context):
    if music_player.playing_now is None:
        return await ctx.send(embed=default_error_msg('Queue is empty...'))

    msg = ''
    for i, v in enumerate(music_player.queue):
        msg += f'{i + 1}. [{v.title}]({v.url})\n'

    embed = default_embed_msg(
        title=f'Playing now: {music_player.playing_now.title}',
        description=msg,
        footer='Queue status',
        url=music_player.playing_now.url
    )

    await ctx.send(embed=embed)


@bot.command()
async def pause(ctx: Context):
    if music_player.vc is None or not music_player.vc.is_playing():
        return await ctx.send(embed=default_error_msg('Nothing playing now...'))

    music_player.vc.pause()


@bot.command()
async def resume(ctx: Context):
    if music_player.vc is None or not music_player.vc.is_paused():
        return await ctx.send(embed=default_error_msg('Nothing playing now...'))

    music_player.vc.resume()


@bot.command()
async def skip(ctx: Context):
    if music_player.vc is None or not music_player.vc.is_playing():
        return await ctx.send(embed=default_error_msg('Nothing playing now...'))

    await ctx.send(embed=default_embed_msg(
        title=music_player.playing_now.title,
        description='Skipped',
        url=music_player.playing_now.url
    ))
    music_player.vc.stop()


@bot.hybrid_command()
async def clear(ctx: Context):
    if music_player.vc is None or not music_player.vc.is_playing():
        return await ctx.send(embed=default_error_msg('Nothing to clear...'))

    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect(force=True)

    music_player.queue = []
    music_player.send_end_playing()

    await music_player.vc.disconnect()

    return await ctx.send(embed=default_embed_msg('Successfully cleared...'))


@bot.command()
async def reset(ctx: Context):
    if music_player.vc is None:
        return await ctx.send(embed=default_error_msg('Nothing to reset...'))

    music_player.vc.pause()
    music_player.vc.resume()

    return await ctx.send(embed=default_embed_msg('Reset'))


if __name__ == "__main__":
    token = os.environ.get("TOKEN")
    bot.run(token)
