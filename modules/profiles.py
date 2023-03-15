import re, discord
from discord import app_commands
from modules.utils import relativeTimeParser
from datetime import datetime
from modules.utils import numberWordFormat
from string import Template
from manager import DiscordManager

class DiscordProfiles:
	def __init__(self, bot, reputation_enums:[[str,bool],...]):
		self.bot = bot
		self.reputation_enums = reputation_enums
		
		with self.bot.cursor() as cursor:
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_profiles (discordid BIGINT NOT NULL, name VARCHAR(32), age INT(2), iswoman BOOL, PRIMARY KEY(discordid))")
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_reputation (user BIGINT NOT NULL, rater BIGINT NOT NULL, val INT NOT NULL, PRIMARY KEY(user, rater))")
		
		command_init = self.bot.language.commands['profile_age']['init']
		@command_init.command(**self.bot.language.commands['profile_age']['initargs'])
		@app_commands.describe(**self.bot.language.commands['profile_age']['describe'])
		@app_commands.rename(**self.bot.language.commands['profile_age']['rename'])
		async def command_profile_age(interaction: discord.Interaction, age: int = None):
			if age == None:
				with self.bot.cursor() as cursor:
					cursor.execute(f'INSERT INTO discord_profiles (discordid, age) VALUES (\'{interaction.user.id}\',NULL) ON DUPLICATE KEY UPDATE age=NULL')
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_age']['messages']['age-hidden'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			age = age if age > 6 else 6
			age = age if age < 99 else 99
			with self.bot.cursor() as cursor:
				cursor.execute(f'INSERT INTO discord_profiles (discordid, age) VALUES (\'{interaction.user.id}\',\'{age}\') ON DUPLICATE KEY UPDATE age=\'{age}\'')
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['profile_age']['messages']['age-changed']).safe_substitute(age=age))
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
		
		command_init = self.bot.language.commands['profile_name']['init']
		@command_init.command(**self.bot.language.commands['profile_name']['initargs'])
		@app_commands.describe(**self.bot.language.commands['profile_name']['describe'])
		@app_commands.rename(**self.bot.language.commands['profile_name']['rename'])
		async def command_profile_name(interaction: discord.Interaction, name: str = None):
			if name == None:
				with self.bot.cursor() as cursor:
					cursor.execute(f'INSERT INTO discord_profiles (discordid, name) VALUES (\'{interaction.user.id}\',NULL) ON DUPLICATE KEY UPDATE name=NULL')
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_name']['messages']['name-hidden'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			if len(name) > 32:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_name']['messages']['max-length-error'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			if len(name) < 2:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_name']['messages']['min-length-error'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			name = name.lower()
			if re.match("[їієґa-zа-яё]*",name) is not None:
				name = name.capitalize()
				with self.bot.cursor() as cursor:
					cursor.execute(f'INSERT INTO discord_profiles (discordid, name) VALUES (\'{interaction.user.id}\',\'{name}\') ON DUPLICATE KEY UPDATE name=\'{name}\'')
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['profile_name']['messages']['name-changed']).safe_substitute(name=name))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
			else:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_name']['messages']['incorrect-symbols-error'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				
		command_init = self.bot.language.commands['profile_gender']['init']
		@command_init.command(**self.bot.language.commands['profile_gender']['initargs'])
		@app_commands.choices(**self.bot.language.commands['profile_gender']['choices'])
		@app_commands.describe(**self.bot.language.commands['profile_gender']['describe'])
		@app_commands.rename(**self.bot.language.commands['profile_gender']['rename'])
		async def command_profile_gender(interaction: discord.Interaction, gender: app_commands.Choice[int] = None):
			if gender == None:
				with self.bot.cursor() as cursor:
					cursor.execute(f'INSERT INTO discord_profiles (discordid, iswoman) VALUES (\'{interaction.user.id}\',NULL) ON DUPLICATE KEY UPDATE iswoman=NULL')
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_gender']['messages']['gender-hidden'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
			else:
				with self.bot.cursor() as cursor:
					cursor.execute(f'INSERT INTO discord_profiles (discordid, iswoman) VALUES (\'{interaction.user.id}\',{gender.value}) ON DUPLICATE KEY UPDATE iswoman={gender.value}')
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['profile_gender']['messages']['gender-changed']).safe_substitute(gender=gender.name))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
		
		command_init = self.bot.language.commands['profile_reputation']['init']
		@command_init.command(**self.bot.language.commands['profile_reputation']['initargs'])
		@app_commands.describe(**self.bot.language.commands['profile_reputation']['describe'])
		@app_commands.rename(**self.bot.language.commands['profile_reputation']['rename'])
		@app_commands.choices(enum=[app_commands.Choice(name=self.reputation_enums[i][0].lower(), value=i) for i in range(len(self.reputation_enums))])
		async def command_profile_reputation(interaction: discord.Interaction,  member: discord.Member, enum: app_commands.Choice[int] = None):
			if member == interaction.user:
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['profile_reputation']['messages']['self-reputation-error']).safe_substitute(user=member.mention))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			if not enum:
				with self.bot.cursor() as cursor:
					cursor.execute(f'DELETE FROM discord_reputation WHERE user=\'{member.id}\' AND rater=\'{interaction.user.id}\'')
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['profile_reputation']['messages']['reputation-reset']).safe_substitute(user=member.mention))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			with self.bot.cursor() as cursor:
				cursor.execute(f'INSERT INTO discord_reputation VALUES (\'{member.id}\',\'{interaction.user.id}\',{enum.value}) ON DUPLICATE KEY UPDATE val={enum.value}')
			if self.reputation_enums[enum.value][1]:
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['profile_reputation']['messages']['positive-reputation']).safe_substitute(user=member.mention,reputation=self.reputation_enums[enum.value][0]))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=False)
			else:
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['profile_reputation']['messages']['nagative-reputation']).safe_substitute(user=member.mention,reputation=self.reputation_enums[enum.value][0]))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=False)

		command_init = self.bot.language.commands['profile_member']['init']
		@command_init.command(**self.bot.language.commands['profile_member']['initargs'])
		@app_commands.choices(**self.bot.language.commands['profile_member']['choices'])
		@app_commands.describe(**self.bot.language.commands['profile_member']['describe'])
		@app_commands.rename(**self.bot.language.commands['profile_member']['rename'])
		async def command_profile_member(interaction: discord.Interaction, member: discord.Member, hide: app_commands.Choice[int] = None):
			hide = True if (hide==None or hide.value==1) else False
			name,age,iswoman,premium_start, premium_end, nick, first_join, last_join, time_played,isolator_end,isolator_time = None, None, None, None, None, None, None, None, None, None, None
			
			with self.bot.cursor() as cursor:
				if 'mutes' in self.bot.enabled_modules:
					cursor.execute(f'SELECT end, time FROM discord_isolator WHERE discordid={member.id} LIMIT 1')
					data = cursor.fetchone()
					if data:
						isolator_end, isolator_time = data 
				if 'minecraft' in self.bot.enabled_modules:
					cursor.execute(f'SELECT id,nick,first_join,last_join,time_played FROM mc_accounts WHERE discordid={member.id} LIMIT 1')
					data = cursor.fetchone()
					if data:
						id,nick, first_join, last_join, time_played = data
						cursor.execute(f'SELECT bedrockUsername FROM LinkedPlayers WHERE javaUniqueId=UNHEX(REPLACE(\'{id}\', \'-\', \'\'))')
						data = cursor.fetchone()
						subname = data[0] if data else None	
					cursor.execute(f'SELECT COUNT(*) FROM mc_referals WHERE user={member.id}')
					referals_count = cursor.fetchone()[0]
				if 'premium' in self.bot.enabled_modules:
					cursor.execute(f'SELECT start,end FROM discord_premium WHERE discordid={member.id} LIMIT 1')
					data = cursor.fetchone()
					if data:
						premium_start, premium_end = data
				
				cursor.execute(f'SELECT name,age,iswoman FROM discord_profiles WHERE discordid={member.id} LIMIT 1')
				data = cursor.fetchone()
				if data:
					name,age,iswoman = data
				
				cursor.execute(f'SELECT val,COUNT(rater) AS cnt FROM discord_reputation WHERE user=\'{member.id}\' GROUP BY val ORDER BY cnt DESC')
				reputation = cursor.fetchall()

			if name or age or iswoman or premium_end or nick or isolator_time or isolator_end or member.avatar or reputation:
				embed_title = Template(self.bot.language.commands['profile_member']['messages']['embed-title']).safe_substitute(user=member)
				embed = discord.Embed(title = embed_title,colour = discord.Colour.green())

				if name or age or iswoman!=None or isolator_time or isolator_end:
					params = []
					gender = self.bot.language.commands['profile_member']['messages']['woman-gender'] if iswoman else self.bot.language.commands['profile_member']['messages']['man-gender'] if iswoman!=None else None
					if gender != None:
						params.append(Template(self.bot.language.commands['profile_member']['messages']['gender-format']).safe_substitute(gender=gender))
					if name:
						params.append(Template(self.bot.language.commands['profile_member']['messages']['name-format']).safe_substitute(name=name))
					if name:
						params.append(Template(self.bot.language.commands['profile_member']['messages']['age-format']).safe_substitute(age=age))
					if isolator_time and isolator_time > 0:
						params.append(Template(self.bot.language.commands['profile_member']['messages']['in-isolator-format']).safe_substitute(time=relativeTimeParser(seconds=isolator_time,greater=True)))
					if isolator_end:
						params.append(Template(self.bot.language.commands['profile_member']['messages']['isolator-ends-format']).safe_substitute(time=isolator_end))
					field_name = self.bot.language.commands['profile_member']['messages']['personalinfo-field-name']
					embed.add_field(name = field_name,value='\n'.join(params), inline=False)

				if nick:
					params = []
					nick = nick.replace('_','\\_')
					if subname:
						subname = subname.replace('_','\\_')
						subname = Template(self.bot.language.commands['profile_member']['messages']['subname-format']).safe_substitute(subname=subname)
					else:
						subname = ''
					params.append(Template(self.bot.language.commands['profile_member']['messages']['nick-format']).safe_substitute(nick=nick,subname=subname))
					if first_join!=last_join:
						params.append(Template(self.bot.language.commands['profile_member']['messages']['last-join-format']).safe_substitute(time=last_join))
					params.append(Template(self.bot.language.commands['profile_member']['messages']['first-join-format']).safe_substitute(time=first_join))
					if time_played > 0:
						params.append(Template(self.bot.language.commands['profile_member']['messages']['time-played-format']).safe_substitute(time=relativeTimeParser(seconds=time_played)))
					if referals_count > 0:
						referals_word = numberWordFormat(referals_count,[self.bot.language.commands['profile_member']['messages']['referal-word-1'],
																		self.bot.language.commands['profile_member']['messages']['referal-word-2'],
																		self.bot.language.commands['profile_member']['messages']['referal-word-3']])
						params.append(Template(self.bot.language.commands['profile_member']['messages']['referals-count-format']).safe_substitute(referals_count=referals_count,referals_word=referals_word))
					field_name = self.bot.language.commands['profile_member']['messages']['gameinfo-field-name']
					embed.add_field(name = field_name,value='\n'.join(params), inline=False)

				if premium_end and premium_end > int(datetime.now().timestamp()):
					params = []
					params.append(Template(self.bot.language.commands['profile_member']['messages']['premium-given-format']).safe_substitute(time=premium_start))
					params.append(Template(self.bot.language.commands['profile_member']['messages']['premium-ends-format']).safe_substitute(time=premium_end))
					field_name = self.bot.language.commands['profile_member']['messages']['premium-field-name']
					embed.add_field(name = field_name,value='\n'.join(params), inline=False)

				if reputation:
					l = len(reputation)
					rep = []
					field_name = self.bot.language.commands['profile_member']['messages']['reputation-field-name']
					for i in range(int(l/3 + (l % 3 > 0))):
						rep.append(f'**{self.reputation_enums[reputation[i][0]][0]}:** {reputation[i][1]}')
					embed.add_field(name = field_name,value='\n'.join(rep), inline=True)
					
					l - int(l/3 + (l % 3 > 0))
					rep = []
					for i in range(int(l/2 + (l % 2 > 0))):
						rep.append(f'**{self.reputation_enums[reputation[i][0]][0]}:** {reputation[i][1]}')
					if rep:
						embed.add_field(name = '** **',value='\n'.join(rep), inline=True)

					rep = []
					for i in range(int(l/2)):
						rep.append(f'**{self.reputation_enums[reputation[i][0]][0]}:** {reputation[i][1]}')
					if rep:
						embed.add_field(name = '** **',value='\n'.join(rep), inline=True)

				if member.avatar:
					embed.set_thumbnail(url=member.avatar.url)
				await interaction.response.send_message(embed=embed, ephemeral=hide)
			else:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_member']['messages']['info-not-found'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
			
		if 'minecraft' in self.bot.enabled_modules:
			async def nickAutocomplete(interaction: discord.Interaction, current: str,) -> [app_commands.Choice[str]]:
				with self.bot.cursor() as cursor:
					cursor.execute(f'SELECT nick FROM mc_accounts ORDER BY rand() LIMIT 25')
					choices = list(cursor.fetchall())
				return [ app_commands.Choice(name=choice[0], value=choice[0]) for choice in choices if current.lower() in choice[0].lower()]
			
			command_init = self.bot.language.commands['profile_nick']['init']
			@command_init.command(**self.bot.language.commands['profile_nick']['initargs'])
			@app_commands.choices(**self.bot.language.commands['profile_nick']['choices'])
			@app_commands.describe(**self.bot.language.commands['profile_nick']['describe'])
			@app_commands.rename(**self.bot.language.commands['profile_nick']['rename'])	
			@app_commands.autocomplete(nickname=nickAutocomplete)
			async def command_profile_nick(interaction: discord.Interaction, nickname: str, hide: app_commands.Choice[int] = None):
				dotnickname = nickname[1:] if nickname.startswith('.') else '.'+nickname
				with self.bot.cursor() as cursor:
					cursor.execute(f'SELECT discordid FROM mc_accounts WHERE LOWER(nick) LIKE LOWER(\'{nickname}\') OR LOWER(nick) LIKE LOWER(\'{dotnickname}\') LIMIT 1')
					discordid = cursor.fetchone()
				if not discordid:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_nick']['messages']['user-not-found'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				member = self.bot.guild().get_member(discordid)
				if not member:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['profile_nick']['messages']['user-leaved'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				await command_profile_member.callback(interaction,member,hide)
					
		
		command_init = self.bot.language.commands['profile_me']['init']
		@command_init.command(**self.bot.language.commands['profile_me']['initargs'])
		@app_commands.choices(**self.bot.language.commands['profile_me']['choices'])
		@app_commands.describe(**self.bot.language.commands['profile_me']['describe'])
		@app_commands.rename(**self.bot.language.commands['profile_me']['rename'])	
		async def command_profile_me(interaction: discord.Interaction,  hide: app_commands.Choice[int] = None):
			await command_profile_member.callback(interaction, interaction.user, hide)