import discord
from discord.ext import commands
import random

class Greetings(commands.Cog):
	def __init__(self, bot, channels: [int,...], messages: [str,...]):
		self.bot = bot
		self.channels = channels
		self.messages = messages

	@commands.Cog.listener()
	async def on_member_join(self,member: discord.Member):
		guild = self.bot.guild()
		message = random.choice(self.messages).format(member=member.mention)
		for channel in self.channels:
			if (channel:=guild.get_channel(channel)):
				await channel.send(content=message)