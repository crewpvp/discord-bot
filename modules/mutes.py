import discord,random
from discord import app_commands
from discord.ext import commands,tasks
from utils import relativeTimeParser

class Mutes(commands.Cog):
	def __init__(self, bot, muted_role: int, check_every_seconds: int, images: [str,...] = []):
		self.bot = bot
		self.muted_role = muted_role
		self.images = images

		self.check_every_seconds = check_every_seconds
		self.mutes_check = tasks.loop(seconds=self.check_every_seconds)(self.on_mutes_check)
	
	@commands.Cog.listener()
	async def on_ready(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_isolator (discordid BIGINT NOT NULL, start INT(11) DEFAULT UNIX_TIMESTAMP(), end INT(11), isolated BOOL NOT NULL, time INT(11) NOT NULL DEFAULT 0, reason TEXT, CONSTRAINT PRIMARY KEY(discordid))")
		await self.sync_roles()
		self.mutes_check.start()

	def cog_unload(self):
		self.mutes_check.cancel()

	@app_commands.command(name='mute',description='выдать буйного на определенный срок')
	@app_commands.rename(member='пользователь',days='длительность',reason='причина')
	@app_commands.describe(days='количество дней буйного (поддерживает дробные значения)')
	async def mute(self,interaction: discord.Interaction, member: discord.Member, days: float = 1.0, reason: str = None):
		await self.mute_member(member,reason=reason,days=days)
		time=relativeTimeParser(days=days)
		if reason:
			embed = discord.Embed(description=f'{member.mention} доставлен в изолятор на срок {time} по причине {reason}',color=discord.Colour.green())
		else:
			embed = discord.Embed(description=f'{member.mention} доставлен в изолятор на срок {time}',color=discord.Colour.green())
		if self.images:
			embed.set_image(url=random.choice(self.images))
		await interaction.response.send_message(embed=embed)

	@app_commands.command(name='unmute',description='помиловать раба божьего')
	@app_commands.rename(member='пользователь')
	async def unmute(self,interaction: discord.Interaction, member: discord.Member):
		if await self.unmute_member(member):
			embed = discord.Embed(description=f'{member.mention} отпустили все совершенные ранее грехи',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed)
		else:
			embed = discord.Embed(description=f'{member.mention} не имеет ни единого греха',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			
	@app_commands.command(name='isolator',description='список буйных, время заточения в дурке и причины')
	@app_commands.rename(page='страница')
	async def isolator(self,interaction: discord.Interaction, page: int = None):
		page = 0 if not page or page < 1 else page-1
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid,end,reason FROM discord_isolator WHERE isolated=TRUE ORDER BY start DESC LIMIT {page*5},5 ')
			muted_users = await cursor.fetchall()
			await cursor.execute(f'SELECT count(*) FROM discord_isolator WHERE isolated=TRUE')
			count = (await cursor.fetchone())[0]
		if muted_users:
			mute_id = count-(page*5)
			embed = discord.Embed(title='Состояние изолятора', description=f'Вот они, легенды комьюнити.\nВсего: {count}',color=discord.Colour.green())
			not_empty = False
			for discordid,time,reason in muted_users:
				if (member:= interaction.guild.get_member(discordid)):
					not_empty = True
					if reason:
						embed.add_field(name=f'Пациент \#{mute_id}',value=f'{member.mention} **будет выпущен** <t:{time}:R>\nПричина изоляции: {reason}',inline=False)
					else:
						embed.add_field(name=f'Пациент \#{mute_id}',value=f'{member.mention} **будет выпущен** <t:{time}:R>',inline=False)
				mute_id-=1
			if not_empty:
				await interaction.response.send_message(embed=embed,ephemeral=False)
				return
		embed = discord.Embed(description='Изолятор пуст, жаль.',color=discord.Colour.red())
		await interaction.response.send_message(embed=embed,ephemeral=True)
	
	mutes_group = app_commands.Group(name='mutes', description='Управление мутом пользователей')

	@mutes_group.command(name='synchronize', description='синхронизировать роли буйных у пользователей c БД')
	async def mutes_synchronize(self, interaction: discord.Interaction):
		embed = discord.Embed(description='Синхронизация буйных с БД запущена',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed,ephemeral=True)
		await self.sync_roles()

	async def sync_roles(self):
		guild = self.bot.guild()
		role = guild.get_role(self.muted_role)
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_isolator WHERE isolated=TRUE')
			users = await cursor.fetchall()
		users = [id[0] for id in users] if users else []
		for member in role.members:
			fetched = None
			for i in range(len(users)):
				if member.id == users[i]:
					fetched = i
			if fetched != None:
				users.pop(fetched)
			else:
				await member.remove_roles(role)
		for id in users:
			if (member:= guild.get_member(id)):
				await member.add_roles(role)

	@commands.Cog.listener()
	async def on_member_join(self,member: discord.Member):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_isolator WHERE discordid={member.id} AND isolated=TRUE')
			if await cursor.fetchone():
				role = self.bot.guild().get_role(self.muted_role)
				await member.add_roles(role)
	
	async def on_mutes_check(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_isolator WHERE end<UNIX_TIMESTAMP() AND isolated=TRUE')
			users = await cursor.fetchall()
			if users:
				await cursor.execute(f'UPDATE discord_isolator SET time=time+end-start,reason=null, isolated=FALSE, start=null, end=null WHERE end<UNIX_TIMESTAMP() AND isolated=TRUE')
				guild = self.bot.guild()
				role = guild.get_role(self.muted_role)
				for discordid in users:
					if (member:=guild.get_member(discordid[0])):
						await member.remove_roles(role)

	async def mute_member(self, member: discord.Member, reason: str = None, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0, years: int = 0):
		time = seconds+(minutes*60)+(hours*3600)+(days*86400)+(years*31536000)
		async with self.bot.cursor() as cursor:
			if reason:
				await cursor.execute(f'INSERT INTO discord_isolator (discordid,end,reason,isolated) VALUES ({member.id},UNIX_TIMESTAMP()+{time},%s,TRUE) ON DUPLICATE KEY UPDATE isolated=TRUE, end=IF(end is null,UNIX_TIMESTAMP()+{time},end+{time}), start=IF(start is null,UNIX_TIMESTAMP(),start), reason=%s',(reason,reason,))
			else:
				await cursor.execute(f'INSERT INTO discord_isolator (discordid,end,isolated) VALUES ({member.id},UNIX_TIMESTAMP()+{time},TRUE) ON DUPLICATE KEY UPDATE isolated=TRUE, end=IF(end is null,UNIX_TIMESTAMP()+{time},end+{time}), start=IF(start is null,UNIX_TIMESTAMP(),start)')
		await member.add_roles(self.bot.guild().get_role(self.muted_role))
			
	async def unmute_member(self, member: discord.Member):
		await member.remove_roles(self.bot.guild().get_role(self.muted_role))
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_isolator WHERE discordid={member.id} AND isolated=TRUE')
			if await cursor.fetchone():
				await cursor.execute(f'UPDATE discord_isolator SET time=time+end-start, reason=null, isolated=FALSE, start=null, end=null WHERE discordid={member.id}')
				return True
		return False