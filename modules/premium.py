import discord
from discord import app_commands
from utils import relativeTimeParser
from discord.ext import commands, tasks

class Premium(commands.Cog):
	def __init__(self, bot, premium_role: int, check_every_seconds: int):
		self.bot = bot
		self.premium_role = premium_role
		self.check_every_seconds = check_every_seconds
		self.premium_check = tasks.loop(seconds=self.check_every_seconds)(self.on_premium_check)

		@self.premiums_give.autocomplete('reason')
		async def premiums_give_reason_autocomplete(interaction: discord.Interaction, current: str) -> [app_commands.Choice[str]]:
			autocompletions = ('одобрение предложенной идеи','всяческая поддержка проекта в развитии','участие в событии','написание отзыва')
			return [app_commands.Choice(name=value,value=value) for value in autocompletions if current.lower() in value.lower()]

	@commands.Cog.listener()
	async def on_ready(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_premium (discordid BIGINT NOT NULL, start INT(11), end INT(11), PRIMARY KEY(discordid))")
		await self.sync_roles()
		self.premium_check.start()

	def cog_unload(self):
		self.premium_check.cancel()

	premiums_group = app_commands.Group(name='premiums', description='Управление премиумом пользователей')

	@premiums_group.command(name='give',description='выдать/добавить премиум на определенный период')
	@app_commands.rename(member='пользователь',days='длительность',reason='причина')
	@app_commands.describe(days='количество дней премиума (поддерживает дробные значения)')
	async def premiums_give(self,interaction: discord.Interaction, member: discord.Member, days: float = 1.0, reason: str = None):
		await self.add_premium(member=member,days=days)
		time = relativeTimeParser(days=days)
		if reason:
			embed = discord.Embed(description=f'Пользователю {member.mention} был выдан премиум на {time} по причине {reason}',color=discord.Colour.green())
		else:
			embed = discord.Embed(description=f'Пользователю {member.mention} был выдан премиум на {time}',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed,ephemeral=False)

	@premiums_group.command(name='remove',description='отобрать леденец у ребенка')
	@app_commands.rename(member='пользователь')
	async def premiums_remove(self,interaction: discord.Interaction, member: discord.Member):
		if not await self.remove_premium(member):
			embed = discord.Embed(description=f'{member.mention} не имеет премиума',color=discord.Colour.red())
		else:
			embed = discord.Embed(description=f'{member.mention} лишен премиума',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed,ephemeral=True)
	
	@premiums_group.command(name='synchronize', description='синхронизировать роли премиума у пользователей c БД')
	async def premiums_synchronize(self, interaction: discord.Interaction):
		embed = discord.Embed(description='Синхронизация премиума с БД запущена',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed,ephemeral=True)
		await self.sync_roles()
		
	@commands.Cog.listener()
	async def on_member_join(self,member: discord.Member):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_premium WHERE discordid={member.id} AND end IS NOT NULL AND start IS NOT NULL')
			if await cursor.fetchone():
				guild = self.bot.guild()
				role = guild.get_role(self.premium_role)
				await member.add_roles(role)

	async def on_premium_check(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_premium WHERE end<UNIX_TIMESTAMP() AND end IS NOT NULL')
			users = await cursor.fetchall()
			if not users:
				return
			await cursor.execute(f'UPDATE discord_premium SET end=NULL, start=NULL WHERE end<UNIX_TIMESTAMP()')
				
			guild = self.bot.guild()
			role = guild.get_role(self.premium_role)
			for discordid in users:
				if (member:= guild.get_member(discordid[0])):
					await member.remove_roles(role)

	async def sync_roles(self):
		guild = self.bot.guild()
		role = guild.get_role(self.premium_role)
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_premium WHERE end IS NOT NULL AND start IS NOT NULL')
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

	async def add_premium(self,member: discord.Member, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0, years: int = 0):
		time = seconds+(minutes*60)+(hours*3600)+(days*86400)+(years*31536000)
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'INSERT INTO discord_premium (discordid,start,end) VALUES(\'{member.id}\',UNIX_TIMESTAMP(), UNIX_TIMESTAMP()+{time}) ON DUPLICATE KEY UPDATE end=IF(end > UNIX_TIMESTAMP(),end+{time},UNIX_TIMESTAMP()+{time}),start=IF(start IS NULL,UNIX_TIMESTAMP(),start)')
		await member.add_roles(self.bot.guild().get_role(self.premium_role))
	
	async def remove_premium(self,member: discord.Member):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_premium WHERE discordid={member.id} AND end IS NOT NULL')
			if await cursor.fetchone():
				await cursor.execute(f'UPDATE discord_premium SET end=NULL, start=NULL WHERE discordid={member.id}')
				await member.remove_roles(self.bot.guild().get_role(self.premium_role))
				return True
			return False
