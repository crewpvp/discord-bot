import re, discord
from discord import app_commands
from discord.ext import commands
from utils import numberWordFormat, relativeTimeParser

class Profiles(commands.Cog):
	def __init__(self, bot, reputation_enums:[[str,bool],...]):
		self.bot = bot
		self.reputation_enums = reputation_enums
		self.profiles_reputation = app_commands.choices(enum=[app_commands.Choice(name=self.reputation_enums[i][0].lower(), value=i) for i in range(len(self.reputation_enums))])(self.profiles_reputation)
		self.bot.tree.add_command(app_commands.ContextMenu(name='Показать профиль',callback=self.context_profiles_member),guild=self.bot.guild_object())
		
		if 'minecraft' in self.bot.enabled_modules:
			self.profiles_nick = Profiles.profiles_group.command(name='nick',description='отобразить профиль игрока')(self.profiles_nick)
			self.profiles_nick = app_commands.rename(nick='игровой_ник',hide='скрывать_сообщение')(self.profiles_nick)
			self.profiles_nick = app_commands.choices(hide=[app_commands.Choice(name='да', value=0),app_commands.Choice(name='нет', value=1)])(self.profiles_nick)

			@self.profiles_nick.autocomplete('nick')
			async def profiles_nick_autocomplete(interaction: discord.Interaction, current: str) -> [app_commands.Choice[str]]:
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT nick FROM mc_accounts ORDER BY rand() LIMIT 25')
					choices = list(await cursor.fetchall())
				return [ app_commands.Choice(name=choice[0], value=choice[0]) for choice in choices if current.lower() in choice[0].lower()]
	
	@commands.Cog.listener()
	async def on_ready(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_profiles (discordid BIGINT NOT NULL, name VARCHAR(32), age INT(2), iswoman BOOL, PRIMARY KEY(discordid))")
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_reputation (user BIGINT NOT NULL, rater BIGINT NOT NULL, val INT NOT NULL, PRIMARY KEY(user, rater))")
	
	profiles_group = app_commands.Group(name='profiles', description='Управление профилем')

	@profiles_group.command(name='age', description='установить/удалить возраст в профиле')
	@app_commands.rename(age='возраст')
	@app_commands.describe(age='оставьте пустым для удаления')
	async def profiles_age(self,interaction: discord.Interaction, age: int = None):
		if age == None:
			async with self.bot.cursor() as cursor:
				await cursor.execute(f'INSERT INTO discord_profiles (discordid, age) VALUES ({interaction.user.id},NULL) ON DUPLICATE KEY UPDATE age=NULL')
			embed = discord.Embed(description='Ваш возраст скрыт',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		age = age if age > 6 else 6
		age = age if age < 99 else 99
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'INSERT INTO discord_profiles (discordid, age) VALUES ({interaction.user.id},{age}) ON DUPLICATE KEY UPDATE age={age}')
		embed = discord.Embed(description=f'Ваш возраст изменен на {age}',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)
		
	@profiles_group.command(name='name', description='установить/удалить имя в профиле')
	@app_commands.rename(name='имя')
	@app_commands.describe(name='оставьте пустым для удаления')
	async def profiles_name(self,interaction: discord.Interaction, name: str = None):
		if name == None:
			async with self.bot.cursor() as cursor:
				await cursor.execute(f'INSERT INTO discord_profiles (discordid, name) VALUES ({interaction.user.id},NULL) ON DUPLICATE KEY UPDATE name=NULL')
			embed = discord.Embed(description='Ваше имя скрыто',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		if len(name) > 32:
			embed = discord.Embed(description=f'Максимальная длина имени **32 символа**',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		if len(name) < 2:
			embed = discord.Embed(description=f'Минимальная длина имени **2 символа**',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		name = name.lower()
		if re.match("[їієґa-zа-яё]*",name) is not None:
			name = name.capitalize()
			async with self.bot.cursor() as cursor:
				await cursor.execute(f'INSERT INTO discord_profiles (discordid, name) VALUES ({interaction.user.id},%s) ON DUPLICATE KEY UPDATE name=%s',(name,name,))
			embed = discord.Embed(description=f'Ваше имя изменено на {name}',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)
		else:
			embed = discord.Embed(description=f'Имя может быть написано на русском, украинском и английском языках',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
				
	@profiles_group.command(name='gender', description='установить/удалить пол в профиле')
	@app_commands.rename(gender='пол')
	@app_commands.describe(gender='оставьте пустым для удаления')
	@app_commands.choices(gender=[app_commands.Choice(name='мужской', value=0),app_commands.Choice(name='женский', value=1)])
	async def profiles_gender(self,interaction: discord.Interaction, gender: app_commands.Choice[int] = None):
		if gender == None:
			async with self.bot.cursor() as cursor:
				await cursor.execute(f'INSERT INTO discord_profiles (discordid, iswoman) VALUES ({interaction.user.id},NULL) ON DUPLICATE KEY UPDATE iswoman=NULL')
			embed = discord.Embed(description='Ваше пол скрыт',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)
		else:
			async with self.bot.cursor() as cursor:
				await cursor.execute(f'INSERT INTO discord_profiles (discordid, iswoman) VALUES ({interaction.user.id},{gender.value}) ON DUPLICATE KEY UPDATE iswoman={gender.value}')
			embed = discord.Embed(description=f'Ваше пол изменен на {gender.name}',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)
		
	@profiles_group.command(name='reputation', description='установить/удалить репутацию пользователю')
	@app_commands.rename(enum='значение')
	@app_commands.describe(enum='оставьте пустым для удаления')
	async def profiles_reputation(self,interaction: discord.Interaction,  member: discord.Member, enum: app_commands.Choice[int] = None):
		if member == interaction.user:
			embed = discord.Embed(description='Вы не можете установить репутацию себе',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		if not enum:
			async with self.bot.cursor() as cursor:
				await cursor.execute(f'DELETE FROM discord_reputation WHERE user={member.id} AND rater={interaction.user.id}')
			embed = discord.Embed(description=f'Значение репутации для {member.mention} сброшено',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'INSERT INTO discord_reputation VALUES ({member.id},{interaction.user.id},{enum.value}) ON DUPLICATE KEY UPDATE val={enum.value}')
		reputation_name = self.reputation_enums[enum.value][0]
		is_positive = self.reputation_enums[enum.value][1]
		if is_positive:
			embed = discord.Embed(description=f'{member.mention} **+{reputation_name}**',color=discord.Colour.green())
		else:
			embed = discord.Embed(description=f'{member.mention} **-{reputation_name}**',color=discord.Colour.red())
		await interaction.response.send_message(embed=embed, ephemeral=False)

	@profiles_group.command(name='member', description='отобразить профиль пользователя')
	@app_commands.rename(member='пользователь', hide='скрывать_сообщение')
	@app_commands.choices(hide=[app_commands.Choice(name='да', value=0),app_commands.Choice(name='нет', value=1)])
	async def profiles_member(self,interaction: discord.Interaction, member: discord.Member, hide: app_commands.Choice[int] = None):
		hide = True if (hide==None or hide.value==1) else False
		mute_data, minecraft_data, premium_data, profile_data, reputation_data = None, None, None, None, None
		async with self.bot.cursor() as cursor:
			if 'mutes' in self.bot.enabled_modules:
				await cursor.execute(f'SELECT time, end FROM discord_isolator WHERE discordid={member.id}')
				mute_data = await cursor.fetchone() 
			if 'minecraft' in self.bot.enabled_modules:
				await cursor.execute(f'SELECT a.nick,a.first_join,a.last_join,a.time_played,e.start,e.end,l.bedrockUsername FROM mc_accounts AS a LEFT JOIN mc_exceptions AS e ON a.id=e.id LEFT JOIN LinkedPlayers AS l ON l.javaUniqueId=UNHEX(REPLACE(a.id, \'-\', \'\')) WHERE a.discordid={member.id}')
				minecraft_data = await cursor.fetchone()
				await cursor.execute(f'SELECT COUNT(*) FROM mc_referals WHERE user={member.id}')
				minecraft_referals_count = (await cursor.fetchone())[0]
			if 'premium' in self.bot.enabled_modules:
				await cursor.execute(f'SELECT start,end FROM discord_premium WHERE discordid={member.id} AND end>UNIX_TIMESTAMP()')
				premium_data = await cursor.fetchone()
			
			await cursor.execute(f'SELECT name,age,iswoman FROM discord_profiles WHERE discordid={member.id}')
			profile_data = await cursor.fetchone()
			
			await cursor.execute(f'SELECT val,COUNT(rater) AS cnt FROM discord_reputation WHERE user=\'{member.id}\' GROUP BY val ORDER BY cnt DESC')
			reputation_data = await cursor.fetchall()

		if not (mute_data or minecraft_data or premium_data or profile_data or reputation_data or member.avatar):
			embed = discord.Embed(description='Информации о пользователе не найдено',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
			
		embed = discord.Embed(title = f'Профиль {member}',colour = discord.Colour.green())
		if mute_data or profile_data:
			attributes = []
			if profile_data:
				name, age, gender = profile_data
				gender = 'Женский' if gender else 'Мужской' if gender!=None else None
				if gender:
					attributes.append(f'**Пол:** {gender}')
				if name:
					attributes.append(f'**Имя:** {name}')
				if age:
					attributes.append(f'**Возраст:** {age}')
			if mute_data:
				isolator_time, isolator_end = mute_data
				if isolator_time and isolator_time > 0:
					isolator_time = relativeTimeParser(seconds=isolator_time,greater=True)
					attributes.append(f'**Проведено в изоляции:** `{isolator_time}`')
				if isolator_end:
					attributes.append(f'**Изоляция окончится:** <t:{isolator_end}:R>')
			attributes = '\n'.join(attributes)
			embed.add_field(name = 'Персональная информация',value=attributes, inline=False)
		
		if minecraft_data:
			attributes = []
			nick,first_join,last_join,time_played,exception_start,exception_end,subname = minecraft_data
			nick = nick.replace('_','\\_')
			if subname:
				subname = subname.replace('_','\\_')
				attributes.append(f'**Никнейм:** {nick} ({subname})')
			else:
				attributes.append(f'**Никнейм:** {nick}')
				
			if first_join!=last_join:
				attributes.append(f'**Был(а) онлайн:** <t:{last_join}:R>')
			attributes.append(f'**Регистрация:** <t:{first_join}:R>')
			if time_played > 0:
				time_played = relativeTimeParser(seconds=time_played)
				attributes.append(f'**Время игры:** `{time_played}`') 
			if minecraft_referals_count > 0:
				referals_word = numberWordFormat(minecraft_referals_count,['человека','человека','человек'])
				attributes.append(f'**Пригласил(а):** {minecraft_referals_count} {referals_word}')
			attributes = '\n'.join(attributes)
			embed.add_field(name = 'Игровая информация',value=attributes, inline=False)

			if exception_start and exception_end:
				attributes = []
				attributes.append(f'**Блокировка получена:** <t:{exception_start}:R>')
				attributes.append(f'**Блокировка истекает:** <t:{exception_end}:R>')
				attributes = '\n'.join(attributes)
				embed.add_field(name = 'Игровая блокировка',value=attributes, inline=False)

		if premium_data:
			attributes = []
			premium_start, premium_end = premium_data
			attributes.append(f'**Получен:** <t:{premium_start}:R>')
			attributes.append(f'**Истекает:** <t:{premium_end}:R>')
			attributes = '\n'.join(attributes)
			embed.add_field(name = 'Премиум',value=attributes, inline=False)

		if reputation_data:
			l = len(reputation)
			rep = []
			for i in range(int(l/3 + (l % 3 > 0))):
				rep.append(f'**{self.reputation_enums[reputation[i][0]][0]}:** {reputation[i][1]}')
			rep = '\n'.join(rep)
			embed.add_field(name = 'Репутация',value=rep, inline=True)
			
			l - int(l/3 + (l % 3 > 0))
			rep = []
			for i in range(int(l/2 + (l % 2 > 0))):
				rep.append(f'**{self.reputation_enums[reputation[i][0]][0]}:** {reputation[i][1]}')
			if rep:
				rep = '\n'.join(rep)
				embed.add_field(name = '** **',value=rep, inline=True)

			rep = []
			for i in range(int(l/2)):
				rep.append(f'**{self.reputation_enums[reputation[i][0]][0]}:** {reputation[i][1]}')
			if rep:
				rep = '\n'.join(rep)
				embed.add_field(name = '** **',value=rep, inline=True)

		if member.avatar:
			embed.set_thumbnail(url=member.avatar.url)
		await interaction.response.send_message(embed=embed, ephemeral=hide)
		
	async def context_profiles_member(self, interaction: discord.Interaction, member: discord.Member):
		await self.profiles_member.callback(self,interaction,member)	
			
	async def profiles_nick(self,interaction: discord.Interaction, nick: str, hide: app_commands.Choice[int] = None):
		dotnick = nick[1:] if nick.startswith('.') else '.'+nick
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM mc_accounts WHERE LOWER(nick) LIKE LOWER(%s) OR LOWER(nick) LIKE LOWER(%s) LIMIT 1',(nick,dotnick,))
			discordid = await cursor.fetchone()
		if not discordid:
			embed = discord.Embed(description='Игрока с таким ником не найдено',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		member = self.bot.guild().get_member(discordid[0])
		if not member:
			embed = discord.Embed(description='Игрок с данным ником покинул сервер',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		await self.profiles_member.callback(self,interaction,member,hide)
					
	@app_commands.command(name='profile',description='отобразить ваш профиль')
	@app_commands.rename(hide='скрывать_сообщение')
	@app_commands.choices(hide=[app_commands.Choice(name='да', value=0),app_commands.Choice(name='нет', value=1)])
	async def profile(self,interaction: discord.Interaction,  hide: app_commands.Choice[int] = None):
		await self,profiles_member.callback(self,interaction, interaction.user, hide)

