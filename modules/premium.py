from discord import app_commands
import discord

from string import Template
from modules.utils import relativeTimeParser
from manager import DiscordManager

class DiscordPremium:
	def __init__(self, bot, premium_role: int, check_every_seconds: int):
		self.bot = bot
		self.premium_role = premium_role
		self.check_every_seconds = check_every_seconds
		
		with self.bot.cursor() as cursor:
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_premium (discordid BIGINT NOT NULL, start INT(11), end INT(11), PRIMARY KEY(discordid))")

		command_init = self.bot.language.commands['premium_give']['init']
		@command_init.command(**self.bot.language.commands['premium_give']['initargs'])
		@app_commands.choices(**self.bot.language.commands['premium_give']['choices'])
		@app_commands.describe(**self.bot.language.commands['premium_give']['describe'])
		@app_commands.rename(**self.bot.language.commands['premium_give']['rename'])
		async def command_premium_give(interaction: discord.Interaction, member: discord.Member, days: float = 1.0, reason: str = None):
			reason = Template(self.bot.language.commands['premium_give']['messages']['reason']).safe_substitute(reason=reason) if reason else reason
			await self.add_premium(member=member,days=days)
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['premium_give']['messages']['premium-given']).safe_substitute(user=member.mention,time=relativeTimeParser(days=days),reason=reason))
			await interaction.response.send_message(content=content,embeds=embeds,ephemeral=False)
		
		for key in self.bot.language.commands['premium_give']['autocomplete']:
			@command_premium_give.autocomplete(key)
			async def autocomplete(interaction: discord.Interaction, current: str,) -> [app_commands.Choice[str]]:
				return self.bot.language.commands['premium_give']['autocomplete'][key](interaction,current)

		command_init = self.bot.language.commands['premium_remove']['init']
		@command_init.command(**self.bot.language.commands['premium_remove']['initargs'])
		@app_commands.describe(**self.bot.language.commands['premium_remove']['describe'])
		@app_commands.rename(**self.bot.language.commands['premium_remove']['rename'])
		async def command_premium_remove(interaction: discord.Interaction, member: discord.Member):
			if await self.remove_premium(member):
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['premium_remove']['messages']['premium-not-found']).safe_substitute(user=member.mention))
			else:
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['premium_remove']['messages']['premium-removed']).safe_substitute(user=member.mention))
			await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)

		async def member_join(member: discord.Member):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT discordid FROM discord_premium WHERE discordid={member.id} AND end IS NOT NULL AND start IS NOT NULL')
				if cursor.fetchone():
					guild = self.bot.guild()
					role = guild.get_role(self.premium_role)
					await member.add_roles(role)
		self.member_join = member_join
		
		async def check(num):
			if (num % self.check_every_seconds != 0):
				return
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT discordid FROM discord_premium WHERE end<UNIX_TIMESTAMP() AND end IS NOT NULL AND start IS NOT NULL')
				users = cursor.fetchall()
				if not users:
					return
				cursor.execute(f'UPDATE discord_premium SET end=NULL, start=NULL WHERE end<UNIX_TIMESTAMP()')
					
				guild = self.bot.guild()
				role = guild.get_role(self.premium_role)
				for discordid in users:
					member = guild.get_member(discordid)
					if member:
						member.remove_roles(role)
			

	async def add_premium(self,member: discord.Member, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0, years: int = 0):
		time = seconds+(minutes*60)+(hours*3600)+(days*86400)+(years*31536000)
		with self.bot.cursor() as cursor:
			cursor.execute(f'INSERT INTO discord_premium VALUES(\'{member.id}\',UNIX_TIMESTAMP(), UNIX_TIMESTAMP()+{time}) ON DUPLICATE KEY UPDATE end=IF(end > UNIX_TIMESTAMP(),end+{time},UNIX_TIMESTAMP()+{time}),start=IF(end > UNIX_TIMESTAMP(),start,UNIX_TIMESTAMP())')
		await member.add_roles(self.bot.guild().get_role(self.premium_role))
	
	async def remove_premium(self,member: discord.Member):
		with self.bot.cursor() as cursor:
			cursor.execute(f'SELECT discordid FROM discord_premium WHERE discordid={member.id} AND end IS NOT NULL AND start IS NOT NULL')
			if cursor.fetchone():
				cursor.execute(f'UPDATE discord_premium SET end=NULL, start=NULL WHERE discordid={member.id}')
				await member.remove_roles(self.bot.guild().get_role(self.premium_role))
				return True
			return False
