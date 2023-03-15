import discord
import random
class DiscordFarewell:
	def __init__(self, bot, channels: [int,...], messages: [str,...]):
		self.bot = bot
		self.channels = channels
		self.messages = messages
		
		async def member_remove(member: discord.Member):
			guild = self.bot.guild()
			message = random.choice(messages).format(member=str(member))
			for channel in channels:
				try:
					await guild.get_channel(channel).send(content=message)
				except:
					pass
		self.member_remove = member_remove