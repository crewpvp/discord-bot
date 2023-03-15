from discord import app_commands
from discord.ext import tasks
import discord
from datetime import datetime
from modules.utils import relativeTimeParser
import random
from string import Template
from manager import DiscordManager

class DiscordMutes:
	def __init__(self, bot, muted_role: int, check_every_seconds: int, images: [str,...] = []):
		self.bot = bot
		self.muted_role = muted_role
		self.images = images
		self.check_every_seconds = check_every_seconds

		with self.bot.cursor() as cursor:
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_isolator (discordid BIGINT NOT NULL, start INT(11) DEFAULT UNIX_TIMESTAMP(), end INT(11), isolated BOOL NOT NULL, time INT(11) NOT NULL DEFAULT 0, reason TEXT, CONSTRAINT PRIMARY KEY(discordid))")
		
		command_init = self.bot.language.commands['mute']['init']
		@command_init.command(**self.bot.language.commands['mute']['initargs'])
		@app_commands.choices(**self.bot.language.commands['mute']['choices'])
		@app_commands.describe(**self.bot.language.commands['mute']['describe'])
		@app_commands.rename(**self.bot.language.commands['mute']['rename'])
		async def command_mute(interaction: discord.Interaction, member: discord.Member, days: float = 1.0, reason: str = None):
			await self.mute(member,reason,days=days)
			reason = Template(self.bot.language.commands['mute']['messages']['reason']).safe_substitute(reason=reason) if reason else ''
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['mute']['messages']['user-muted']).safe_substitute(reason=reason,user=member.mention,time=relativeTimeParser(days=days)))
			if self.images and embeds:
				embeds[0].set_image(url=random.choice(self.images))
			await interaction.response.send_message(content=content,embeds=embeds)

		command_init = self.bot.language.commands['unmute']['init']
		@command_init.command(**self.bot.language.commands['unmute']['initargs'])
		@app_commands.describe(**self.bot.language.commands['unmute']['describe'])
		@app_commands.rename(**self.bot.language.commands['unmute']['rename'])
		async def command_unmute(interaction: discord.Interaction, member: discord.Member):
			if await self.unmute(member):
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['unmute']['messages']['user-unmuted']).safe_substitute(user=member.mention))
				await interaction.response.send_message(content=content,embeds=embeds)
			else:
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['unmute']['messages']['user-not-muted']).safe_substitute(user=member.mention))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				
		command_init = self.bot.language.commands['isolator']['init']
		@command_init.command(**self.bot.language.commands['isolator']['initargs'])
		@app_commands.describe(**self.bot.language.commands['isolator']['describe'])
		@app_commands.rename(**self.bot.language.commands['isolator']['rename'])
		async def command_isolator(interaction: discord.Interaction, page: int = None):
			page = 0 if not page or page < 1 else page-1
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT discordid,end,reason FROM discord_isolator WHERE isolated=TRUE ORDER BY start DESC LIMIT {page*5},5 ')
				buinie = cursor.fetchall()
				cursor.execute(f'SELECT count(*) FROM discord_isolator WHERE isolated=TRUE')
				count = cursor.fetchone()[0]
			if buinie:
				mutes = []
				mute_id = count-(page*5)
				for discordid,time,reason in buinie:
					member = interaction.guild.get_member(discordid)
					if member:
						reason = Template(self.bot.language.commands['isolator']['messages']['reason']).safe_substitute(reason=reason) if reason else ''
						mutes.append(Template(self.bot.language.commands['isolator']['messages']['mute-format']).safe_substitute(reason=reason,user=member.mention,time=time,id=mute_id))
					mute_id-=1
				if mutes:
					mutes = (self.bot.language.commands['isolator']['messages']['join-by']).join(mutes)
					content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['isolator']['messages']['mute-list']).safe_substitute(mutes=mutes, count=count, page=page+1))
					await interaction.response.send_message(content=content,embeds=embeds,ephemeral=False)
					return

			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['isolator']['messages']['empty-mute-list'])
			await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
		
		async def member_join(member: discord.Member):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT discordid FROM discord_isolator WHERE discordid={member.id} AND isolated=TRUE')
				if cursor.fetchone():
					role = self.bot.guild().get_role(self.muted_role)
					await member.add_roles(role)

		self.member_join = member_join
	
		async def check(num):
			if (num % self.check_every_seconds != 0):
				return
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT discordid FROM discord_isolator WHERE end<UNIX_TIMESTAMP() AND isolated=TRUE')
				users = cursor.fetchall()
				if users:
					cursor.execute(f'UPDATE discord_isolator SET time=time+end-start,reason=null, isolated=FALSE, start=null, end=null WHERE end<UNIX_TIMESTAMP() AND isolated=TRUE')
					guild = self.bot.guild()
					role = guild.get_role(self.muted_role)
					for discordid in users:
						member = guild.get_member(discordid[0])
						if member:
							await member.remove_roles(role)
		self.check = check

	async def mute(self, member: discord.Member, reason: str = None, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0, years: int = 0):
		time = seconds+(minutes*60)+(hours*3600)+(days*86400)+(years*31536000)
		with self.bot.cursor() as cursor:
			if reason:
				cursor.execute(f'INSERT INTO discord_isolator (discordid,end,reason,isolated) VALUES ({member.id},UNIX_TIMESTAMP()+{time},?,TRUE) ON DUPLICATE KEY UPDATE isolated=TRUE, end=IF(end is null,UNIX_TIMESTAMP()+{time},end+{time}), start=IF(start is null,UNIX_TIMESTAMP(),start), reason=?',(reason,reason,))
			else:
				cursor.execute(f'INSERT INTO discord_isolator (discordid,end,isolated) VALUES ({member.id},UNIX_TIMESTAMP()+{time},TRUE) ON DUPLICATE KEY UPDATE isolated=TRUE, end=IF(end is null,UNIX_TIMESTAMP()+{time},end+{time}), start=IF(start is null,UNIX_TIMESTAMP(),start)')
		await member.add_roles(self.bot.guild().get_role(self.muted_role))
			
	async def unmute(self, member: discord.Member):
		await member.remove_roles(self.bot.guild().get_role(self.muted_role))
		with self.bot.cursor() as cursor:
			cursor.execute(f'SELECT discordid FROM discord_isolator WHERE discordid={member.id} AND isolated=TRUE')
			if cursor.fetchone():
				cursor.execute(f'UPDATE discord_isolator SET time=time+end-start, reason=null, isolated=FALSE, start=null, end=null WHERE discordid={member.id}')
				return True
		return False