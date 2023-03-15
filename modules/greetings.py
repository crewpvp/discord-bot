import discord
import random
class DiscordGreeting:
	def __init__(self, bot, channels: [int,...], messages: [str,...]):
		self.bot = bot
		self.channels = channels
		self.messages = messages
		
		async def member_join(member: discord.Member):
			guild = self.bot.guild()
			message = random.choice(messages).format(member=member.mention)
			for channel in channels:
				try:
					await guild.get_channel(channel).send(content=message)
				except:
					pass
		self.member_join = member_join