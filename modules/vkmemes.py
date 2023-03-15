from vkbottle import Bot, SingleAiohttpClient
from io import BytesIO
import discord
import logging
import json
import os
from loguru import logger

class DiscordVkMemes:
	def __init__(self, bot, token: int, groups:[int,...], channels:[int,...], check_every_seconds: int):
		logging.getLogger("vkbottle").setLevel(logging.INFO)
		logger.disable("vkbottle")
		self.token = token
		self.vk = Bot(self.token)
		self.vk.api.http_client = SingleAiohttpClient()
		self.bot = bot
		self.groups = [str(group) for group in groups]
		self.last_posts = {}
		self.check_every_seconds = check_every_seconds
		self.channels = channels

		for group in self.groups:
			self.last_posts[group] = None
		
		if os.path.isfile("vkmemes.json"):
			with open('vkmemes.json') as json_file:
				data = json.load(json_file)
				for group in data.keys():
					if group in self.last_posts:
						self.last_posts[group] = data[group]

		async def check(num):
			if (num % self.check_every_seconds != 0):
				return
			guild = self.bot.guild()
			channels = [guild.get_channel(channel_id) for channel_id in self.channels]
			for groupid in self.groups:
				if not self.last_posts[groupid]:
					self.last_posts[groupid] = (await self.vk.api.wall.get(owner_id=groupid,offset=1,count=1)).items[0].id
					continue
				posts = await self.vk.api.wall.get(owner_id=groupid,offset=1, count=10)
				for post in reversed(posts.items):
					if post.id <= self.last_posts[groupid]:
						continue
					self.last_posts[groupid] = post.id
					if not post.attachments:
						continue
					if post.attachments[0].photo is None:
						continue
					photos = []

					for photo in post.attachments:
						photos.append(discord.File(BytesIO(await self.download_raw_file(max(photo.photo.sizes, key=lambda x: (x.height, x.width)).url)),filename="image.png"))
					for channel in channels:
						await channel.send(files=photos)
			with open('vkmemes.json', 'w') as outfile:
				json.dump(self.last_posts, outfile)
		self.check = check
	async def download_raw_file(self,url):
		return await self.vk.api.http_client.request_content(url)