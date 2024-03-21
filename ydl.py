import asyncio
from typing import Optional

import discord
import yt_dlp as youtube_dl


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}


ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YDLInfo:
    def __init__(self, data, volume, source, *, loop=None):
        self.volume = volume
        self.loop = loop
        self.data = data
        self.source = source

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, volume, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if data is None:
            return None

        if 'entries' in data:
            data = data['entries'][0]

        source = data['url']

        return cls(data, volume, source, loop=loop)

    def init_source(self) -> discord.PCMVolumeTransformer:
        return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(self.source, **ffmpeg_options), volume=self.volume)
