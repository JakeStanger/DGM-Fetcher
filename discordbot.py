from typing import List

import discord
import json
import math
import time
from dgmparse import session, Show, Track, Instrument, Member
from dgmfetch import base_url


class DGMBot(discord.Client):
    _page_num = 0
    _results = []
    _max_pages = 0
    _query = ''

    _last_msg: discord.Message = None

    _result: Show

    page_size = 10

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))

    async def on_message(self, message: discord.Message):
        prefix = settings['discord_prefix']
        if message.content.startswith(prefix):
            command = message.content[len(prefix):].split(' ')

            ident = command[0]

            if ident == 'id':
                id = int(command[1])

                if not id:
                    await self._error(message, 'You have to enter an id')
                    return

                show = session.query(Show).filter_by(dgm_id=id).one()
                self._result = show
                await self._send(message, self._build_show_embed(show))
            elif ident == 'search':
                query = ' '.join(command[1:])

                if not query:
                    await self._error(message, 'You have to enter a search query')
                    return

                results, total = Show.search(query)

                self._query = query
                self._page_num = 0
                self._results = list.copy(results)
                self._max_pages = math.ceil(len(results) / self.page_size)

                results = results[:self.page_size]

                if len(results) == 1:
                    self._result = results[0]
                    await self._send(message, self._build_show_embed(results[0]))
                else:
                    await self._send(message, self._build_search_embed(results, query))
            elif ident == 'next':
                if not self._results or not len(self._results):
                    await self._error(message, 'You have to search for something first')
                    return

                if self._page_num + 1 < self._max_pages and len(self._results):
                    self._page_num += 1

                    results = self._results[self._page_num * self.page_size:(self._page_num + 1) * self.page_size]
                    await self._last_msg.delete()
                    await self._send(message, self._build_search_embed(results, self._query))

            elif ident == 'select':
                if not self._results or not len(self._results):
                    await self._error(message, 'You have to search for something first')
                    return

                index = int(command[1])
                show = self._results[index]

                self._result = show

                await self._last_msg.delete()
                await self._send(message, self._build_show_embed(show))
            elif ident == 'tracks':
                if not self._result:
                    await self._error(message, 'You have to select a show first')
                    return
                if not len(self._result.tracks) > 0:
                    await self._error(message, 'No documented setlist for this show')
                    return

                await self._send(message, self._build_tracks_embed(self._result))
            elif ident == 'members' or ident == 'lineup':
                if not self._result:
                    await self._error(message, 'You have to select a show first')
                    return
                if not len(self._result.members) > 0:
                    await self._error(message, 'No documented setlist for this show')
                    return

                await self._send(message, self._build_members_embed(self._result))
            elif ident == 'help':
                embed = discord.Embed(title='Help', description='**$search <query>** - Search for shows\n'
                                                                '**$next** - View next page of results\n'
                                                                '**$select <num>** - Select result with this number\n'
                                                                '**$tracks** - See tracks for selected show\n'
                                                                '**$lineup** - See lineup for selected show\n'
                                                                '**$members** - Alias for lineup\n'
                                                                '**$id <num>** - Select show with this DGM ID')
                await message.channel.send(embed=embed)
                await message.delete()

    def _build_search_embed(self, shows: List[Show], query: str):
        title = 'Shows matching \'%s\' (%r/%r)' % (
            query, self._page_num + 1, self._max_pages)
        description = '\n'.join('[%s] **%s, %s** - %s' % (self._results.index(show),
                                                          show.venue,
                                                          show.location,
                                                          show.date_friendly)
                                for show in shows)

        embed = discord.Embed(title=title, description=description)
        return embed

    def _build_show_embed(self, show: Show):
        embed = discord.Embed(title=self._build_title(show), description=self._build_description(show),
                              url=self._build_url(show))

        if show.cover:
            embed.set_thumbnail(url=show.cover)

        embed.add_field(name='Date', value=show.date_friendly)
        if show.quality_rating:
            embed.add_field(name='Quality Rating', value='⭐' * show.quality_rating)

        embed.add_field(name='Has Download', value='Yes' if show.has_download else 'No')
        return embed

    def _build_tracks_embed(self, show: Show):
        description = '\n'.join('**%r.** %s  **[%s]**' % (track.pos,
                                                          track.name,
                                                          time.strftime('%M:%S', time.gmtime(track.length)))
                                for track in show.tracks)

        embed = discord.Embed(title=self._build_title(show) + ' - Setlist', description=description)

        return embed

    def _build_members_embed(self, show: Show):
        description = '\n'.join(
            '**%s**: %s' % (member.name, ', '.join(instrument.name for instrument in member.instruments))
            for member in show.members)

        embed = discord.Embed(title=self._build_title(show) + ' - Lineup', description=description)

        return embed

    async def _send(self, message, embed):
        msg = await message.channel.send(embed=embed)
        await message.delete()
        self._last_msg = msg

    @staticmethod
    async def _error(message, error):
        msg = await message.channel.send(error)
        await message.delete()
        time.sleep(3)
        await msg.delete()
        return

    @staticmethod
    def _build_title(show: Show):
        return "%s, %s" % (show.venue, show.location)

    @staticmethod
    def _build_url(show: Show):
        return base_url + str(show.dgm_id)

    @staticmethod
    def _build_description(show: Show):
        if not show.description:
            return

        desc_builder = ''
        desc = show.description.split(' ')
        i = 0
        while len(desc_builder) < 180 and i < len(desc) - 1:
            desc_builder += ' %s' % desc[i]
            i += 1

        if len(show.description) > 180:
            desc_builder += '...'
        return desc_builder


with open('settings.json', 'r') as f:
    settings = json.loads(f.read())

client = DGMBot()
client.run(settings['discord_token'])
