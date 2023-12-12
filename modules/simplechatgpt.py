import discord
from discord import app_commands
from discord.ext import commands
import g4f

class SimpleChatGPT(commands.Cog):
	providers = [
    	g4f.Provider.ChatBase,
    	g4f.Provider.Liaobots,
	]

	def __init__(self, bot, allowed_roles: [int,...]):
		self.bot = bot
		self.allowed_roles = allowed_roles
	
	@commands.Cog.listener()
	async def on_message(self, message: discord.Message):
		if self.bot.user == message.author:
			return
		if message.guild.id != self.bot.guild_id:
			return
		if not message.content:
			return
		if not (self.bot.user.mention in message.content):
			return
		if not bool(set(self.allowed_roles) & set([role.id for role in message.author.roles])):
			return
		async with message.channel.typing():
			for provider in SimpleChatGPT.providers:
				try:
					response = await g4f.ChatCompletion.create_async(
						model="gpt-3.5-turbo",
						messages=[{"role": "user", "content": message.content}],
						provider=provider,
					)
					reference = discord.MessageReference(message_id=message.id, channel_id=message.channel.id)	
					await message.channel.send(content=response, reference=reference)
					return
				except:
					pass