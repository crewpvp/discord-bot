from vkbottle import Bot, SingleAiohttpClient
from io import BytesIO
import discord,logging,json,os
from discord.ext import commands, tasks

logging.getLogger("vkbottle").setLevel(logging.ERROR)
#logger.disable("vkbottle")

class VkMemes(commands.Cog):
	def __init__(self, bot, token: int, groups:[int,...], channels:[int,...], check_every_seconds: int):
		self.bot = bot

		self.token = token
		self.vk = Bot(self.token)
		self.vk.api.http_client = SingleAiohttpClient()
		
		self.last_posts = {}
		for group in groups:
			self.last_posts[str(group)] = None
		self.load_data()

		self.channels = channels

		self.check_every_seconds = check_every_seconds
		self.posts_check = tasks.loop(seconds=self.check_every_seconds)(self.on_posts_check)
		
	@commands.Cog.listener()
	async def on_ready(self):
		self.posts_check.start()

	def cog_unload(self):
		self.posts_check.cancel()

	async def on_posts_check(self):
		guild = self.bot.guild()
		channels = [guild.get_channel(channel_id) for channel_id in self.channels]
		for group_id in self.last_posts.keys():
			if not self.last_posts[group_id]:
				self.last_posts[group_id] = (await self.vk.api.wall.get(owner_id=group_id,offset=1,count=1)).items[0].id
				continue
			posts = await self.vk.api.wall.get(owner_id=group_id,offset=1, count=20)
			for post in reversed(posts.items):
				if post.id <= self.last_posts[group_id]:
					continue
				self.last_posts[group_id] = post.id
				if not post.attachments:
					continue
				if post.attachments[0].photo is None:
					continue
				photos = []
				try:
					for photo in post.attachments:
						photos.append(discord.File(BytesIO(await self.download_raw_file(max(photo.photo.sizes, key=lambda x: (x.height, x.width)).url)),filename="image.png"))
					for channel in channels:
						await channel.send(files=photos)
				except:
					pass
		self.save_data()

	async def download_raw_file(self,url):
		return await self.vk.api.http_client.request_content(url)

	def save_data(self):
		with open('vkmemes.json', 'w') as outfile:
			json.dump(self.last_posts, outfile)

	def load_data(self):
		if not os.path.isfile("vkmemes.json"):
			return
		with open('vkmemes.json') as json_file:
			data = json.load(json_file)
			for group in data.keys():
				if group in self.last_posts:
					self.last_posts[group] = data[group]
