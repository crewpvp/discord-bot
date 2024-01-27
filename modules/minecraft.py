import discord,re,uuid,random,yaml,aiohttp
from discord import app_commands
from discord.ext import commands,tasks
from datetime import datetime
from utils import relativeTimeParser,json_to_message
import skcrew

class Minecraft(commands.Cog):
	def __init__(self, bot, category: int, channel: int, cooldown: int, registered_role: int,approved_time:int, disapproved_time: int,request_duration: int,exception_role: int,inactive: {}, counter: {}, check_every_seconds: int, web_host: str, web_login: str, web_password: str, link_cooldown: int, nick_change_cooldown: int):
		self.bot = bot
		self.stages = yaml.load(open('verification.yml'), Loader=yaml.FullLoader)
		self.category = category
		self.channel = channel
		self.cooldown = cooldown
		self.registered_role = registered_role
		self.inactive = inactive
		self.counter = counter
		self.disapproved_time = disapproved_time
		self.link_cooldown = link_cooldown
		self.nick_change_cooldown = nick_change_cooldown
		self.request_duration = request_duration
		self.approved_time = approved_time
		self.check_every_seconds = check_every_seconds
		self.exception_role = exception_role
		self.skcrewapi = skcrew.api(web_host,web_login,web_password)
		self.check = tasks.loop(seconds=self.check_every_seconds)(self.on_check)
	
	@commands.Cog.listener()
	async def on_ready(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_accounts (id UUID NOT NULL,nick CHAR(16) UNIQUE,discordid BIGINT UNIQUE NOT NULL,pseudonym CHAR(64),ip CHAR(36),first_join INT(11) DEFAULT UNIX_TIMESTAMP() NOT NULL,last_join INT(11) DEFAULT UNIX_TIMESTAMP() NOT NULL,time_played INT(11) DEFAULT 0 NOT NULL,last_server VARCHAR(32),timezone INT(2) DEFAULT 0 NOT NULL,chat_global BOOL NOT NULL DEFAULT TRUE,chat_local BOOL NOT NULL DEFAULT TRUE,chat_private BOOL NOT NULL DEFAULT TRUE,inactive BOOL NOT NULL DEFAULT FALSE, purged BOOL NOT NULL DEFAULT FALSE, code INT(5), code_time INT(11), country VARCHAR(32) DEFAULT 'Unknown' NOT NULL,city VARCHAR(32) DEFAULT 'Unknown' NOT NULL, operator BOOL NOT NULL DEFAULT FALSE,PRIMARY KEY (id))")
			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_playerdata (id UUID NOT NULL, server VARCHAR(32) NOT NULL, playerdata LONGTEXT NOT NULL, advancements LONGTEXT NOT NULL, PRIMARY KEY (id,server), FOREIGN KEY(id) REFERENCES mc_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE)")
			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_playerstats (id UUID NOT NULL, stats LONGTEXT NOT NULL, PRIMARY KEY(id), FOREIGN KEY(id) REFERENCES mc_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE)")

			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_exceptions (id UUID NOT NULL, start INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), end INT(11) NOT NULL, reason TEXT, PRIMARY KEY(id), FOREIGN KEY(id) REFERENCES mc_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE)")

			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_registrations (id INT NOT NULL AUTO_INCREMENT, discordid BIGINT NOT NULL,uuid UUID NOT NULL, nick CHAR(32) NOT NULL, referal BIGINT, channelid BIGINT UNIQUE, channel_deleted BOOL NOT NULL DEFAULT FALSE, messageid BIGINT UNIQUE, time INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), stage TEXT NOT NULL,sended INT(11), approved BOOL NOT NULL DEFAULT FALSE, closed INT(11), close_reason TEXT, PRIMARY KEY (id))")
			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_registrations_answers (id INT NOT NULL, stage TEXT NOT NULL, question TEXT NOT NULL, answer TEXT, FOREIGN KEY(id) REFERENCES mc_registrations(id) ON DELETE CASCADE)")
			
			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_inactive_recovery (id INT NOT NULL AUTO_INCREMENT, discordid BIGINT NOT NULL,messageid BIGINT NOT NULL, sended INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), approved BOOL NOT NULL DEFAULT FALSE, closed INT(11), close_reason TEXT, PRIMARY KEY(id), FOREIGN KEY(discordid) REFERENCES mc_accounts(discordid) ON DELETE CASCADE ON UPDATE CASCADE)")
			
			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_referals (user BIGINT NOT NULL,referal BIGINT NOT NULL UNIQUE, FOREIGN KEY(referal) REFERENCES mc_accounts(discordid) ON DELETE CASCADE ON UPDATE CASCADE)")
			
			await cursor.execute("CREATE TABLE IF NOT EXISTS LinkedPlayers (bedrockId BINARY(16) NOT NULL ,javaUniqueId BINARY(16) NOT NULL UNIQUE,javaUsername VARCHAR(16) NOT NULL UNIQUE, bedrockUsername VARCHAR(17), PRIMARY KEY (bedrockId), INDEX (bedrockId, javaUniqueId)) ENGINE = InnoDB")
			await cursor.execute("CREATE OR REPLACE TRIGGER LinkedPlayers_UPDATE AFTER UPDATE ON mc_accounts FOR EACH ROW UPDATE LinkedPlayers SET javaUniqueId=UNHEX(REPLACE(NEW.id, \'-\', \'\')), javaUsername=NEW.nick WHERE javaUniqueId=UNHEX(REPLACE(OLD.id, \'-\', \'\'))")
			await cursor.execute("CREATE OR REPLACE TRIGGER LinkedPlayers_DELETE AFTER DELETE ON mc_accounts FOR EACH ROW DELETE FROM LinkedPlayers WHERE javaUniqueId=UNHEX(REPLACE(OLD.id, \'-\', \'\'))")
			
			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_last_link (id BIGINT NOT NULL, time INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), PRIMARY KEY (id), FOREIGN KEY(id) REFERENCES mc_accounts(discordid) ON DELETE CASCADE ON UPDATE CASCADE)")
			await cursor.execute(f'CREATE OR REPLACE TRIGGER mc_last_link_UPDATE AFTER UPDATE ON LinkedPlayers FOR EACH ROW BEGIN IF NEW.javaUniqueId != OLD.javaUniqueId THEN INSERT INTO mc_last_link (id,time) VALUES((SELECT discordid FROM mc_accounts WHERE id=HEX(NEW.javaUniqueId)),UNIX_TIMESTAMP()+{self.link_cooldown}) ON DUPLICATE KEY UPDATE id=(SELECT discordid FROM mc_accounts WHERE id=HEX(NEW.javaUniqueId)), time=UNIX_TIMESTAMP()+{self.link_cooldown}; END IF; END')
			await cursor.execute(f'CREATE OR REPLACE TRIGGER mc_last_link_INSERT AFTER INSERT ON LinkedPlayers FOR EACH ROW INSERT INTO mc_last_link (id,time) VALUES((SELECT discordid FROM mc_accounts WHERE id=HEX(NEW.javaUniqueId)),UNIX_TIMESTAMP()+{self.link_cooldown}) ON DUPLICATE KEY UPDATE id=(SELECT discordid FROM mc_accounts WHERE id=HEX(NEW.javaUniqueId)), time=UNIX_TIMESTAMP()+{self.link_cooldown}')

			await cursor.execute("CREATE TABLE IF NOT EXISTS mc_last_nick_change (id BIGINT NOT NULL, time INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), PRIMARY KEY (id), FOREIGN KEY(id) REFERENCES mc_accounts(discordid) ON DELETE CASCADE ON UPDATE CASCADE)")
			await cursor.execute(f'CREATE OR REPLACE TRIGGER mc_last_nick_change_UPDATE AFTER UPDATE ON mc_accounts FOR EACH ROW BEGIN IF NEW.id != OLD.id THEN INSERT INTO mc_last_nick_change (id,time) VALUES(NEW.discordid,UNIX_TIMESTAMP()+{self.nick_change_cooldown}) ON DUPLICATE KEY UPDATE id=NEW.discordid, time=UNIX_TIMESTAMP()+{self.nick_change_cooldown}; END IF; END')
		await self.sync_roles()
		self.check.start()

	def cog_unload(self):
		self.check.cancel()

	minecraft_group = app_commands.Group(name='minecraft', description='управление модулем')

	registration_group = app_commands.Group(name='registration', parent=minecraft_group, description='управление регистрациями')
	recovery_group = app_commands.Group(name='recovery', parent=minecraft_group, description='управление восстановлением аккаунтов')

	registration_authorize_group = app_commands.Group(name='authorize', parent=minecraft_group, description='создание кнопок')
	registration_authcode_group = app_commands.Group(name='authcode', parent=minecraft_group, description='создание кнопок')
	registration_logout_group = app_commands.Group(name='logout', parent=minecraft_group, description='создание кнопок')

	exception_group = app_commands.Group(name='exception',parent=minecraft_group, description='управление исключениями')
	unexception_group = app_commands.Group(name='unexception',parent=minecraft_group, description='управление исключениями')

	top_group = app_commands.Group(name='top', description='Все возможные игровые топы')
	change_group = app_commands.Group(name='change', description='Изменить данные игрового аккаунта')

	@minecraft_group.command(name='synchronize', description='синхронизировать роли у пользователей c БД')
	async def minecraft_synchronize(self, interaction: discord.Interaction):
		embed = discord.Embed(description='Синхронизация ролей с БД запущена',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed,ephemeral=True)
		await self.sync_roles()

	@registration_group.command(name='accept',description='одобрить заявку на регистрацию аккаунта')
	@app_commands.rename(id='номер_заявки')
	async def registration_accept(self,interaction: discord.Interaction, id: int):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid, nick, uuid, channelid, referal, messageid FROM mc_registrations WHERE id={id} AND closed IS NULL')
			if not (data:=await cursor.fetchone()):
				embed = discord.Embed(description='Заявка на регистрацию с данным id не найдена',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			discordid, nick, uuid, channelid, referal, messageid = data
			channel = interaction.guild.get_channel(channelid)
			member = interaction.guild.get_member(discordid)
			try:
				message = await self.bot.guild().get_channel(self.channel).fetch_message(messageid)
			except:
				message = None

			if member:
				await cursor.execute(f'UPDATE mc_registrations SET approved=TRUE, closed=UNIX_TIMESTAMP(), close_reason = \'Заявка одобрена {interaction.user}\' WHERE id={id}')
				await cursor.execute(f'INSERT INTO mc_accounts (id, nick, discordid, pseudonym) VALUES (\'{uuid}\',\'{nick}\',{discordid},\'{nick}\')')
				if referal:
					await cursor.execute(f'SELECT user,referal FROM mc_referals WHERE user={member.id} AND referal={referal}')
					if not await cursor.fetchone():
						await cursor.execute(f'INSERT INTO mc_referals (user,referal) VALUES ({referal},{member.id})')
						referal = interaction.guild.get_member(referal)
						if (premium:=self.bot.get_cog(name='Premium')):
							await premium.add_premium(member=member,hours=12,days=3)
							if referal:
								await premium.add_premium(member=referal,days=7)

				try:
					await member.remove_roles(interaction.guild.get_role(self.inactive['role']))
					await member.add_roles(interaction.guild.get_role(self.registered_role))
				except:
					pass
				if message:
					embed = message.embeds[0]
					embed.colour = discord.Colour.green()
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Одобрено <t:{time}:R>',value=f'{interaction.user.mention}')
					await message.edit(content=None,view=None,embed=embed)

				embed = discord.Embed(color=discord.Colour.green())
				embed.add_field(name='Регистрация на игровом сервере',value='Ваша заявка была одобрена! Приятной игры!',inline=False)
				embed.add_field(name='Информбюро: о режимах',value='У сервера существует информбюро «о режимах»\nНайти его можно по ссылке [info.crewpvp.xyz](https://info.crewpvp.xyz/) или в канале <#967423687965966336>',inline=False)
				embed.add_field(name='Информбюро: тикеты',value='Вам нужна помощь? Напишите свой вопрос в тикете и мы поможем\nКанал: <#1022157438033608774>',inline=False)
				try:
					await member.send(embed=embed)
				except:
					pass
				if channel:
					embed = discord.Embed(color=discord.Colour.green())
					embed.add_field(name='Регистрация на игровом сервере',value='Ваша заявка была одобрена! Приятной игры!',inline=False)
					embed.add_field(name='Вам выдана роль с доступом к разделу Minecraft',value='Познакомьтесь с другими пользователями, имеющими роль <@&943836722557513779>\nБудьте уверены, большинство будут рады пообщаться и поиграть вместе!',inline=False)
					embed.add_field(name='Информбюро: о режимах',value='У сервера существует информбюро «о режимах»\nНайти его можно по ссылке [info.crewpvp.xyz](https://info.crewpvp.xyz/) или в канале <#967423687965966336>',inline=False)
					embed.add_field(name='Информбюро: тикеты',value='Вам нужна помощь? Напишите свой вопрос в тикете и мы поможем\nКанал: <#1022157438033608774>',inline=False)
					await channel.send(embed=embed)
				embed = discord.Embed(description='Заявка была одобрена', color=discord.Colour.green())
			else:
				await cursor.execute(f'UPDATE mc_registrations SET closed=UNIX_TIMESTAMP(), close_reason = \'Заявка автоматически отклонена в связи с покиданием Discord сервера\' WHERE id={id}')
				if message:
					embed = message.embeds[0]
					embed.colour = discord.Colour.red()
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Отклонено <t:{time}:R>',value='Автор заявки покинул Discord сервер')
					await message.edit(content=None,view=None,embed=embed)
				if channel:
					embed = discord.Embed(color=discord.Colour.red())
					embed.add_field(name='Регистрация на игровом сервере',value='Ваша заявка была отклонена, так как вы покинули Discord сервер')
					await channel.send(embed=embed)
				embed = discord.Embed(description='Заявка автоматически отклонена, так как пользователь покинул Discord сервер', color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@registration_group.command(name='decline',description='отклонить заявку на регистрацию игрового аккаунта')
	@app_commands.rename(id='номер_заявки',reason='причина')
	async def registration_decline(self,interaction: discord.Interaction, id: int, reason: str):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid,channelid,messageid FROM mc_registrations WHERE id={id}')
			if not (data:=await cursor.fetchone()):
				embed = discord.Embed(description='Заявка на регистрацию с данным id не найдена',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			
			member = interaction.guild.get_member(data[0])
			channel = interaction.guild.get_channel(data[1])
			try:
				message = await self.bot.guild().get_channel(self.channel).fetch_message(data[2])
			except:
				message = None

			if member:
				await cursor.execute(f'UPDATE mc_inactive_recovery SET closed=UNIX_TIMESTAMP(), close_reason = %s WHERE id={id}', (reason,))
				if message:
					embed = message.embeds[0]
					embed.colour = discord.Colour.red()
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Отклонено <t:{time}:R>',value=f'{interaction.user.mention} по причине {reason}')
					await message.edit(content=None,view=None,embed=embed)
				
				cooldown_time = relativeTimeParser(seconds=self.cooldown,greater=True)

				if channel:
					embed = discord.Embed(color=discord.Colour.red())
					embed.add_field(name='Регистрация на игровом сервере',value=f'Ваша заявка была отклонена!\nПо причине {reason}')
					embed.set_footer(text=f'Вы сможете повторить попытку через {cooldown_time}')
					await channel.send(embed=embed)
				
				embed = discord.Embed(color=discord.Colour.red())
				embed.add_field(name='Регистрация на игровом сервере',value=f'Ваша заявка была отклонена!\nПо причине {reason}')
				embed.set_footer(text=f'Вы сможете повторить попытку через {cooldown_time}')
				try:
					await member.send(embed=embed)
				except:
					pass

				embed = discord.Embed(description='Заявка была отклонена', color=discord.Colour.red())
			else:
				await cursor.execute(f'UPDATE mc_registrations SET closed=UNIX_TIMESTAMP(), close_reason = \'Заявка автоматически отклонена в связи с покиданием Discord сервера\' WHERE id={id}')
				if message:
					embed = message.embeds[0]
					embed.colour = discord.Colour.red()
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Отклонено <t:{time}:R>',value='Автор заявки покинул Discord сервер')
					await message.edit(content=None,view=None,embed=embed)
				if channel:
					embed = discord.Embed(color=discord.Colour.red())
					embed.add_field(name='Регистрация на игровом сервере',value='Ваша заявка была отклонена, так как вы покинули Discord сервер')
					await channel.send(embed=embed)

				embed = discord.Embed(description='Заявка автоматически отклонена, так как пользователь покинул Discord сервер', color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
	
	@recovery_group.command(name='accept',description='одобрить восстановление игрового аккаунта')
	@app_commands.rename(id='номер_заявки')
	async def recovery_accept(self,interaction: discord.Interaction, id: int):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid,messageid FROM mc_inactive_recovery WHERE id={id} AND closed IS NULL')
			if not (data:=await cursor.fetchone()):
				embed = discord.Embed(description='Заявка на восстановление с данным id не найдена',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			member = interaction.guild.get_member(data[0])
			try:
				message = await self.bot.guild().get_channel(self.channel).fetch_message(data[1])
			except:
				message = None

			if member:
				await cursor.execute(f'UPDATE mc_accounts SET inactive=FALSE, last_join=UNIX_TIMESTAMP() WHERE discordid={member.id}')
				await cursor.execute(f'UPDATE mc_inactive_recovery SET approved=TRUE,closed=UNIX_TIMESTAMP(),close_reason=\'Ваша заявка о восстановлении была одобрена\' WHERE messageid={id}')
				try:
					await member.remove_roles(interaction.guild.get_role(self.inactive['role']))
					await member.add_roles(interaction.guild.get_role(self.registered_role))
				except:
					pass
				if message:
					embed = message.embeds[0]
					embed.colour = discord.Colour.green()
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Одобрено <t:{time}:R>',value=f'{interaction.user.mention}')
					await message.edit(content=None,view=None,embed=embed)

				embed = discord.Embed(color=discord.Colour.green())
				embed.add_field(name='Восстановление игрового аккаунта',value=f'Ваша заявка была одобрена! Приятной игры!')
				try:
					await member.send(embed=embed)
				except:
					pass

				embed = discord.Embed(description='Заявка была одобрена', color=discord.Colour.green())
			else:
				await cursor.execute(f'UPDATE mc_inactive_recovery SET closed=UNIX_TIMESTAMP(), close_reason = \'Заявка автоматически отклонена в связи с покиданием Discord сервера\' WHERE id={id}')
				if message:
					embed = message.embeds[0]
					embed.colour = discord.Colour.red()
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Отклонено <t:{time}:R>',value='Автор заявки покинул Discord сервер')
					await message.edit(content=None,view=None,embed=embed)
				embed = discord.Embed(description='Заявка автоматически отклонена, так как пользователь покинул Discord сервер', color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@recovery_group.command(name='decline',description='отклонить восстановление игрового аккаунта')
	@app_commands.rename(id='номер_заявки',reason='причина')
	async def recovery_decline(self,interaction: discord.Interaction, id: int, reason: str):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid,messageid FROM mc_inactive_recovery WHERE id={id} AND closed IS NULL')
			if not (data:=await cursor.fetchone()):
				embed = discord.Embed(description='Заявка на восстановление с данным id не найдена',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			
			member = interaction.guild.get_member(data[0])
			try:
				message = await self.bot.guild().get_channel(self.channel).fetch_message(data[1])
			except:
				message = None

			if member:
				await cursor.execute(f'UPDATE mc_inactive_recovery SET closed=UNIX_TIMESTAMP(), close_reason = %s WHERE id={id}',(reason,))
				if message:
					embed = message.embeds[0]
					embed.colour = discord.Colour.red()
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Отклонено <t:{time}:R>',value=f'{interaction.user.mention} по причине {reason}')
					await message.edit(content=None,view=None,embed=embed)
				
				embed = discord.Embed(color=discord.Colour.green())
				embed.add_field(name='Восстановление игрового аккаунта',value=f'Ваша заявка была отклонена по причине {reason}')
				try:
					await member.send(embed=embed)
				except:
					pass
				embed = discord.Embed(description='Заявка была одобрена', color=discord.Colour.green())
			else:
				await cursor.execute(f'UPDATE mc_inactive_recovery SET closed=UNIX_TIMESTAMP(), close_reason = \'Заявка автоматически отклонена в связи с покиданием Discord сервера\' WHERE id={id}')
				if message:
					embed = message.embeds[0]
					embed.colour = discord.Colour.red()
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Отклонено <t:{time}:R>',value='Автор заявки покинул Discord сервер')
					await message.edit(content=None,view=None,embed=embed)
				embed = discord.Embed(description='Заявка автоматически отклонена, так как пользователь покинул Discord сервер', color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@registration_group.command(name='buttons',description='Создать кнопки начала регистрации')
	@app_commands.rename(java_label='название_java',java_color='цвет_java',bedrock_label='название_bedrock',bedrock_color='цвет_bedrock')
	@app_commands.choices(java_color=[app_commands.Choice(name=name,value=value) for name,value in (('синяя',1),('серая',2),('зеленая',3),('красная',4))])
	@app_commands.choices(bedrock_color=[app_commands.Choice(name=name,value=value) for name,value in (('синяя',1),('серая',2),('зеленая',3),('красная',4))])
	async def registration_start_buttons(self,interaction: discord.Interaction, java_label: str = None, java_color: app_commands.Choice[int] = None,bedrock_label: str = None, bedrock_color: app_commands.Choice[int] = None):
		java_label = java_label[:80] if java_label else 'Java Edition'
		bedrock_label = bedrock_label[:80] if bedrock_label else 'Bedrock Edition'
		java_color = discord.ButtonStyle(java_color.value) if java_color else discord.ButtonStyle(2)
		bedrock_color = discord.ButtonStyle(bedrock_color.value) if bedrock_color else discord.ButtonStyle(2)
		view = discord.ui.View(timeout=None)
		view.add_item(discord.ui.Button(disabled=False,custom_id="registration_start_java",label=java_label,style=java_color))
		view.add_item(discord.ui.Button(disabled=False,custom_id="registration_start_bedrock",label=bedrock_label,style=bedrock_color))
		await interaction.channel.send(view=view)
		embed = discord.Embed(description='Кнопки начала регистрации созданы',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)

	@recovery_group.command(name='button',description='Создать кнопку восстановления аккаунта')
	@app_commands.rename(label='название',color='цвет')
	@app_commands.choices(color=[app_commands.Choice(name=name,value=value) for name,value in (('синяя',1),('серая',2),('зеленая',3),('красная',4))])
	async def recovery_button(self, interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
		label = label[:80] if label else 'Восстановить аккаунт'
		color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
		view = discord.ui.View(timeout=None)
		view.add_item(discord.ui.Button(disabled=False,custom_id="inactive_recovery_start",label=label,style=color))
		await interaction.channel.send(view=view)
		embed = discord.Embed(description='Кнопка восстановления аккаунта создана',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)

	@registration_authorize_group.command(name='button',description='Создать кнопку авторизации аккаунта')
	@app_commands.rename(label='название',color='цвет')
	@app_commands.choices(color=[app_commands.Choice(name=name,value=value) for name,value in (('синяя',1),('серая',2),('зеленая',3),('красная',4))])
	async def registration_authorize_button(self, interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
		label = label[:80] if label else 'Авторизоваться'
		color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
		view = discord.ui.View(timeout=None)
		view.add_item(discord.ui.Button(disabled=False,custom_id="authorize",label=label,style=color))
		await interaction.channel.send(view=view)
		embed = discord.Embed(description='Кнопка авторизации аккаунта создана',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)

	@registration_authcode_group.command(name='button',description='Создать кнопку получения одноразового кода для входа')
	@app_commands.rename(label='название',color='цвет')
	@app_commands.choices(color=[app_commands.Choice(name=name,value=value) for name,value in (('синяя',1),('серая',2),('зеленая',3),('красная',4))])
	async def registration_authcode_button(self, interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
		label = label[:80] if label else 'Код для входа'
		color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
		view = discord.ui.View(timeout=None)
		view.add_item(discord.ui.Button(disabled=False,custom_id="authcode",label=label,style=color))
		await interaction.channel.send(view=view)
		embed = discord.Embed(description='Кнопка получения одноразового кода для входа создана',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)

	@registration_logout_group.command(name='button',description='Создать кнопку выхода из игрового аккаунта')
	@app_commands.rename(label='название',color='цвет')
	@app_commands.choices(color=[app_commands.Choice(name=name,value=value) for name,value in (('синяя',1),('серая',2),('зеленая',3),('красная',4))])
	async def registration_logout_button(self, interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
		label = label[:80] if label else 'Выйти из аккаунта'
		color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
		view = discord.ui.View(timeout=None)
		view.add_item(discord.ui.Button(disabled=False,custom_id="logout",label=label,style=color))
		await interaction.channel.send(view=view)
		embed = discord.Embed(description='Кнопка выхода из аккаунта создана',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)

	@app_commands.command(name='recovery',description='начать восстановление аккаунта')
	async def recovery(self, interaction: discord.Interaction):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id FROM mc_accounts WHERE discordid={interaction.user.id} AND inactive=TRUE')
			if not await cursor.fetchone():
				embed = discord.Embed(description='Ваш аккаунт не найден в списке инактива',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			await cursor.execute(f'SELECT id FROM mc_inactive_recovery WHERE discordid={interaction.user.id} AND closed IS NULL')
			if await cursor.fetchone():
				embed = discord.Embed(description='У вас уже есть активная заявка на восстановление аккаунта',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			await interaction.response.send_modal(self.recovery_modal())
					
	@app_commands.command(name='authorize',description='авторизовать аккаунт на игровом сервере')
	async def authorize(self, interaction: discord.Interaction):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={interaction.user.id}')
			data = await cursor.fetchone()
		if not data:
			embed = discord.Embed(description='Вы не зарегистрированны на игровом сервере',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		uuid,nick = data
		try:
			player=await self.skcrewapi.player(uuid)
			await self.skcrewapi.signals(signals=[skcrew.Signal('authorize',[str(uuid)])],servers=[player.server])
			embed = discord.Embed(description='Вы успешно авторизованны!',color=discord.Colour.green())
		except:
			embed = discord.Embed(description='Для авторизации вы должны быть онлайн на игровом сервере',color=discord.Colour.red())
		
		await interaction.response.send_message(embed=embed, ephemeral=True)
		
	@app_commands.command(name='logout',description='выйти с аккаунта на игровом сервере')
	async def logout(self, interaction: discord.Interaction):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id,nick,ip FROM mc_accounts WHERE discordid={interaction.user.id}')
			data = await cursor.fetchone()
			if not data:
				embed = discord.Embed(description='Вы не зарегистрированны на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			uuid,nick,ip = data
			if not ip:
				embed = discord.Embed(description='Вы и так не авторизованны',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			try: 
				player=await self.skcrewapi.player(uuid)
				await self.skcrewapi.signals(signals=[skcrew.Signal('logout',[str(uuid)])],servers=[player.server])
			except:
				pass
			await cursor.execute(f'UPDATE mc_accounts SET ip=NULL WHERE id=\'{uuid}\'')
			embed = discord.Embed(description='Вы успешно вышли из игрового аккаунта!',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@app_commands.command(name='authcode',description='получить одноразовый код для входа')
	@app_commands.rename(minutes='длительность')
	@app_commands.describe(minutes='длительность работы одноразового кода в минутах')
	async def authcode(self, interaction: discord.Interaction, minutes: int = 60):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={interaction.user.id}')
			data = await cursor.fetchone()
			if not data:
				embed = discord.Embed(description='Вы не зарегистрированны на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			uuid,nick = data
			code = random.randrange(10000,99999)
			code_time = int(datetime.now().timestamp())+(minutes*60)
			await cursor.execute(f'UPDATE mc_accounts SET code={code}, code_time={code_time} WHERE id=\'{uuid}\'')
			embed = discord.Embed(description=f'Ваш одноразовый код для входа на игровой аккаунт: ||{code}||\nДействительность кода истекает <t:{code_time}:R>',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@app_commands.command(name='register',description='начать регистрацию')
	@app_commands.rename(nick='игровой_ник',environment='редакция_игры',referal='ник_пригласившего')
	@app_commands.choices(environment=[app_commands.Choice(name=name,value=value) for name,value in (('Java Edition',0),('Bedrock Edition',1))])
	async def register(self, interaction: discord.Interaction, environment: app_commands.Choice[int], nick:str, referal: str = None):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id FROM mc_accounts WHERE discordid={interaction.user.id}')
			if await cursor.fetchone():
				embed = discord.Embed(description='Вы уже зарегистрированны на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			await cursor.execute(f'SELECT id FROM mc_registrations WHERE discordid={interaction.user.id} AND closed IS NULL')
			if await cursor.fetchone():
				embed = discord.Embed(description='У вас уже есть активная заявка на регистрацию',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			await cursor.execute(f'SELECT closed+{self.cooldown} FROM mc_registrations WHERE discordid={interaction.user.id} AND closed+{self.cooldown} > UNIX_TIMESTAMP()')
			time = await cursor.fetchone()
			if time:
				time = time[0]
				embed = discord.Embed(description=f'Вы сможете повторить заявку <t:{time}:R>',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			if referal:
				if not (referal:=await self.fetchDiscordByNick(referal)):
					embed = discord.Embed(description=f'Аккаунт, связанный с ником, который вы указали как пригласившего не найден',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await cursor.execute(f'SELECT user,referal FROM mc_referals WHERE user={interaction.user.id} AND referal={referal}')
				if await cursor.fetchone():
					embed = discord.Embed(description=f'Вы не можете быть приглашены пользователем, который приглашён вами',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return

			if environment.value == 1:
				if not re.match("^\.?[A-Za-z][A-Za-z0-9]{0,11}[0-9]{0,4}",nick) is not None:
					embed = discord.Embed(description=f'Недопустимый или несуществующий ник для создания Bedrock аккаунта',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				if not (uuid:=await self.getBedrockUUID(nick[1:] if nick.startswith('.') else nick)):
					embed = discord.Embed(description=f'Недопустимый или несуществующий ник для создания Bedrock аккаунта',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await cursor.execute(f'SELECT bedrockId FROM LinkedPlayers WHERE bedrockId=UNHEX(REPLACE(\'{uuid}\', \'-\', \'\'))')
				if await cursor.fetchone():
					embed = discord.Embed(description='Данный аккаунт уже зарегистрирован на игровом сервере',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				if not nick.startswith("."):
					nick = "."+nick
			else:
				if not re.match("[A-Za-z_0-9]{3,16}", nick) is not None:
					embed = discord.Embed(description=f'Недопустимый ник для создания Java аккаунта',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				uuid = self.getJavaUUID(nick)
			await cursor.execute(f'SELECT id FROM mc_accounts WHERE id=\'{uuid}\'')
			if await cursor.fetchone():
				embed = discord.Embed(description='Аккаунт с данным ником уже зарегистрирован на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			await cursor.execute(f'SELECT id FROM mc_registrations WHERE uuid=\'{uuid}\' AND closed IS NULL')
			if await cursor.fetchone():
				embed = discord.Embed(description='Аккаунт с данным ником уже зарегистрирован на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			category = interaction.guild.get_channel(self.category)
			overwrites = {
				interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
				interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
			}
			channel = await interaction.guild.create_text_channel(name=nick[1:] if nick.startswith('.') else nick,category=category, overwrites=overwrites)
			start_stage = self.stages['start_stage']
			if referal:
				await cursor.execute(f'INSERT INTO mc_registrations (discordid,nick,channelid,stage,uuid,referal) VALUES({interaction.user.id},\'{nick}\',{channel.id},\'{start_stage}\',\'{uuid}\',{referal})')	
			else:
				await cursor.execute(f'INSERT INTO mc_registrations (discordid,nick,channelid,stage,uuid) VALUES({interaction.user.id},\'{nick}\',{channel.id},\'{start_stage}\',\'{uuid}\')')	
			if self.isFormStage(start_stage):
				content,embeds,component = self.registrationButton(start_stage)
			else:
				content,embeds,component = self.parseQuestions(start_stage)
			await channel.send(content = content, embeds = embeds, view = component)
			
			channel_link = f'https://discord.com/channels/{self.bot.guild_id}/{channel.id}'
			embed = discord.Embed(description=f'Регистрация начата, перейдите в канал [{channel.name}]({channel_link})',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@app_commands.command(name='link',description='привязать второй аккаунт')
	@app_commands.rename(nick='ник')
	async def link(self, interaction: discord.Interaction, nick: str):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={interaction.user.id}')
			data = await cursor.fetchone()
			if not data:
				embed = discord.Embed(description='Вы не зарегистрированны на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			id, nickname = data
			
			await cursor.execute(f'SELECT time FROM mc_last_link WHERE id={interaction.user.id} AND time>UNIX_TIMESTAMP()')
			data = await cursor.fetchone()
			if data:
				time = data[0]
				embed = discord.Embed(description=f'Вы сможете сделать привязку второго аккаунта <t:${time}:R>',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			if nickname.startswith('.'):
				bedrock_uuid, bedrock_nick = id, nickname
				java_nick, java_uuid = nick, self.getJavaUUID(nick)

				await cursor.execute(f'SELECT id FROM mc_registrations WHERE uuid=\'{java_uuid}\' AND closed IS NULL')
				if await cursor.fetchone():
					embed = discord.Embed(description=f'Данный ник уже зарегистрирован на игровом сервере',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return

				if not re.match("[A-Za-z_0-9]{3,16}", nick) is not None:
					embed = discord.Embed(description=f'Неверно указан ник для второго игрового аккаунта',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await cursor.execute(f'SELECT id FROM mc_accounts WHERE id=\'{java_uuid}\'')
				if await cursor.fetchone():
					embed = discord.Embed(description=f'Данный ник уже зарегистрирован на игровом сервере',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await cursor.execute(f'SELECT bedrockId FROM LinkedPlayers WHERE bedrockId=UNHEX(REPLACE(\'{bedrock_uuid}\', \'-\', \'\'))')
				if await cursor.fetchone():
					embed = discord.Embed(description=f'Данный ник уже зарегистрирован на игровом сервере',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await cursor.execute(f'UPDATE mc_accounts SET id = \'{java_uuid}\', nick = \'{java_nick}\', pseudonym=\'{java_nick}\' WHERE discordid={interaction.user.id}')
				try:
					player = await self.skcrewapi.player(bedorck_uuid)
					await self.skcrewapi.signals(signals=[skcrew.Signal('link_account',[str(bedrock_uuid)])],servers=[player.server])
				except:
					pass
			else:
				java_uuid, java_nick = id, nickname
				if not re.match("^\.?[A-Za-z][A-Za-z0-9]{0,11}[0-9]{0,4}",nick) is not None:
					embed = discord.Embed(description=f'Неверно указан ник для второго игрового аккаунта',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				if not (bedrock_uuid:= await self.getBedrockUUID(nick[1:] if nick.startswith('.') else nick)):
					embed = discord.Embed(description=f'Неверно указан ник для второго игрового аккаунта',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await cursor.execute(f'SELECT id FROM mc_registrations WHERE uuid=\'{bedrock_uuid}\' AND closed IS NULL')
				if await cursor.fetchone():
					embed = discord.Embed(description=f'Данный ник уже зарегистрирован на игровом сервере',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await cursor.execute(f'SELECT bedrockId FROM LinkedPlayers WHERE bedrockId=UNHEX(REPLACE(\'{bedrock_uuid}\', \'-\', \'\'))')
				if await cursor.fetchone():
					embed = discord.Embed(description=f'Данный ник уже зарегистрирован на игровом сервере',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await cursor.execute(f'SELECT id FROM mc_accounts WHERE id=\'{bedrock_uuid}\'')
				if await cursor.fetchone():
					embed = discord.Embed(description=f'Данный ник уже зарегистрирован на игровом сервере',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				if not nick.startswith("."):
					nick = '.'+nick
				bedrock_nick = nick
			await cursor.execute(f'INSERT INTO LinkedPlayers VALUES(UNHEX(REPLACE(\'{bedrock_uuid}\', \'-\', \'\')),UNHEX(REPLACE(\'{java_uuid}\', \'-\', \'\')),\'{java_nick}\',\'{bedrock_nick}\')')
			embed = discord.Embed(description=f'Аккаунт успешно привязан',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@app_commands.command(name='unlink',description='отвязать второй аккаунт')
	@app_commands.rename(environment='редакция_игры')
	@app_commands.choices(environment=[app_commands.Choice(name=name,value=value) for name,value in (('Java Edition',0),('Bedrock Edition',1))])
	async def unlink(self,interaction: discord.Interaction, environment: app_commands.Choice[int] = None):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT bedrockId,javaUniqueId,javaUsername,bedrockUsername FROM LinkedPlayers WHERE javaUniqueId = (SELECT UNHEX(REPLACE(id, \'-\', \'\')) FROM mc_accounts WHERE discordid = {interaction.user.id} LIMIT 1)')
			data = await cursor.fetchone()
			if not data:
				embed = discord.Embed(description='У вас не найден второй аккаунт',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			bedrock_uuid, java_uuid, java_nick, bedrock_nick = data
			bedrock_uuid, java_uuid = uuid.UUID(bytes=bedrock_uuid), uuid.UUID(bytes=java_uuid)
			if not environment:
				component = discord.ui.View(timeout=None)
				options = [discord.SelectOption(label='Java аккаунт',value=0,description=f'Ник: {java_nick}'),discord.SelectOption(label='Bedrock аккаунт',value=1,description=f'Ник: {bedrock_nick}')]
				component.add_item(discord.ui.Select(custom_id='unlink_account',disabled=False, min_values=1, max_values=1, placeholder='Выберите редакцию игры', options=options))
				await interaction.response.send_message(view=component, ephemeral=True)
			else:
				environment = environment.value
				await cursor.execute(f'DELETE FROM LinkedPlayers WHERE javaUniqueId = UNHEX(REPLACE(\'{java_uuid}\', \'-\', \'\')) AND bedrockId = UNHEX(REPLACE(\'{bedrock_uuid}\', \'-\', \'\'))')
				if environment == 0:
					await cursor.execute(f'UPDATE mc_accounts SET id=\'{bedrock_uuid}\', nick=\'{bedrock_nick}\', pseudonym=\'{bedrock_nick}\' WHERE id=\'{java_uuid}\'')
					try:
						player=await self.skcrewapi.player(java_uuid)
						await self.skcrewapi.signals(signals=[skcrew.Signal('unlink_account',[str(java_uuid)])],servers=[player.server])
					except:
						pass
				embed = discord.Embed(description='Аккаунт успешно отвязан',color=discord.Colour.green())
				if interaction.message:
					await interaction.response.edit_message(embed=embed,view=None)
				else:
					await interaction.response.send_message(embed=embed, ephemeral=True)

	@change_group.command(name='nick',description='изменить игровой ник')
	@app_commands.rename(nick='новый_ник')
	async def change_nick(self, interaction: discord.Interaction, nick: str):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={interaction.user.id}')
			data = await cursor.fetchone()
			if not data:
				embed = discord.Embed(description='Вы не зарегистрированны на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			previous_uuid,previous_nick = data
			if previous_nick.startswith("."):
				embed = discord.Embed(description='Смена ника поддерживается только на Java редакции игры. Для смены ника Bedrock используйте Xbox аккаунт',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			await cursor.execute(f'SELECT time FROM mc_last_nick_change WHERE id=? AND time>UNIX_TIMESTAMP()',(interaction.user.id,))
			data = await cursor.fetchone()
			if data:
				time = data[0]
				embed = discord.Embed(description=f'Вы сможете снова сменить ник <t:{time}:R>',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			if not re.match("[A-Za-z_0-9]{3,16}", nick) is not None:
				embed = discord.Embed(description=f'Неверно указан новый ник',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			uuid = self.getJavaUUID(nick)
			await cursor.execute(f'SELECT id FROM mc_accounts WHERE id=\'{uuid}\'')
			if await cursor.fetchone():
				embed = discord.Embed(description=f'Аккаунт с указанным ником уже зарегистрирован на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			await cursor.execute(f'SELECT id FROM mc_registrations WHERE uuid=\'{uuid}\' AND closed IS NULL')
			if await cursor.fetchone():
				embed = discord.Embed(description=f'Аккаунт с указанным ником уже зарегистрирован на игровом сервере',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return

			await cursor.execute(f'UPDATE mc_accounts SET id = \'{uuid}\', nick = \'{nick}\', pseudonym=\'{nick}\' WHERE discordid={interaction.user.id}')
			try:
				player=await self.skcrewapi.player(previous_uuid)
				await self.skcrewapi.signals(signals=[skcrew.Signal('change_nick',[str(previous_uuid)])],servers=[player.server])
			except:
				pass
			nick = nick.replace('_','\\\\_')
			embed = discord.Embed(description=f'Ник изменен на **`{nick}`**',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@top_group.command(name='activity',description='топ самых активных игроков')
	@app_commands.rename(page='страница')
	async def top_activity(self, interaction: discord.Interaction, page: int = 1):
		page = 0 if page < 1 else page-1
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT nick,discordid,time_played FROM mc_accounts ORDER BY time_played DESC LIMIT {page*25},25')
			players = await cursor.fetchall()
		if not players:
			embed = discord.Embed(description='Ноль игроков нахуй. Крев сдох блять.',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		playerlist = []
		for nick,discordid,time_played in players:
			user = interaction.guild.get_member(discordid)
			nick = nick.replace('_','\\\\_')
			time = relativeTimeParser(seconds=time_played)
			if user:
				playerlist.append(f'**{nick}** ({user.mention}): `{time}`')
			else:
				playerlist.append(f'**{nick}**: `{time}`')
		playerlist = '\n'.join(playerlist)
		embed = discord.Embed(title='Топ активности',description=f'Личная шизнь вышла из чата\n\n{playerlist}',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=False)
	
	@exception_group.command(name='nick',description='исключить малого на срок по нику')
	@app_commands.rename(nick='игровой_ник',days='длительность',reason='причина')
	@app_commands.describe(days='количество дней исключения, поддерживает дробные значения')
	async def exception_nick(self, interaction: discord.Interaction, nick: str, days: float = 1.0, reason: str = None):
		user = await self.add_exception(nick=nick,reason=reason,days=days)
		if not user:
			embed = discord.Embed(description='Пользователь с указанным ником не зарегистрирован на игровом сервере.',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		reason = f'\nПо причине {reason}' if reason else ''
		time = relativeTimeParser(days=days)
		if user:
			embed = discord.Embed(description=f'**{nick}** ({user.mention}) исключен с игрового сервера на срок {time}{reason}', color=dsicord.Colour.green())
		else:
			embed = discord.Embed(description=f'**{nick}** исключен с игрового сервера на срок {time}{reason}', color=dsicord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=False)
				
	@exception_group.command(name='member',description='исключить малого на срок по discord аккаунту')
	@app_commands.rename(member='пользователь',days='длительность',reason='причина')
	@app_commands.describe(days='количество дней исключения, поддерживает дробные значения')
	async def exception_member(self, interaction: discord.Interaction, member: discord.Member, days: float = 1.0, reason: str = None):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT nick FROM mc_accounts WHERE discordid={member.id}')
			data = await cursor.fetchone()
		if not data:
			embed = discord.Embed(description='У указанного пользователя отсутствует игровой аккаунт',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		await self.exception_nick.callback(self,interaction=interaction,nick=data[0],days=days,reason=reason)
		
	@unexception_group.command(name='nick',description='снять все грехи с малого по нику')
	@app_commands.rename(nick='игровой_ник')
	async def unexception_nick(self, interaction: discord.Interaction, nick: str):
		user = await self.remove_exception(nick=nick)
		if not user:
			embed = discord.Embed(description='Пользователь с указанным ником не найден в списке исключенных.',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		if user:
			embed = discord.Embed(description=f'**{nick}** ({user.mention}) отпустили все грехи', color=dsicord.Colour.green())
		else:
			embed = discord.Embed(description=f'**{nick}** отпустили все грехи', color=dsicord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=False)
		
	@unexception_group.command(name='member',description='снять все грехи с малого по discord аккаунту')
	@app_commands.rename(member='пользователь')
	async def unexception_member(self, interaction: discord.Interaction, member: discord.Member):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT nick FROM mc_accounts WHERE discordid={member.id}')
			data = await cursor.fetchone()
		if not data:
			embed = discord.Embed(description='У указанного пользователя отсутствует игровой аккаунт',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		await self.unexception_nick.callback(self, interaction=interaction,nick=data[0])

	@app_commands.command(name='exceptions',description='список исключенных, время исключения и причины')
	@app_commands.rename(page='страница')
	async def exceptions(self, interaction: discord.Interaction, page: int = 1):
		page = 0 if page < 1 else page-1
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT a.nick,a.discordid,e.start,e.end,e.reason FROM mc_exceptions AS e JOIN mc_accounts AS a ON a.id=e.id ORDER BY start LIMIT {page*25},25 ')
			players = await cursor.fetchall()
		if not players:
			embed = discord.Embed(description='Исключенные не найдены. Каждый пупсик ведет себя достойно.',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		playerlist = []
		for nick,discordid,start_time,end_time,reason in players:
			user = interaction.guild.get_member(discordid)
			nick = nick.replace('_','\\\\_')
			reason = f'\n**Причина:** ${reason}' if reason else ''
			if user:
				playerlist.append(f'**{nick}** ({user.mention})\n**Получено:** <t:{start_time}:R>\n**Истекает:** <t:{end_time}:R>{reason}')
			else:
				playerlist.append(f'**{nick}**\n**Получено:** <t:{start_time}:R>\n**Истекает:** <t:{end_time}:R>{reason}')
		playerlist = '\n'.join(playerlist)
		embed = discord.Embed(title='Список исключенных',description=f'Вот они, игровые импотенты.\n\n{playerlist}',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=False)

	@top_group.command(name='inviters',description='топ пользователей по приглашённым игрокам')
	@app_commands.rename(page='страница')
	async def top_inviters(self, interaction: discord.Interaction, page: int = 1):
		page = 0 if page < 1 else page-1
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT a.nick,r.user,COUNT(r.referal) as cnt FROM mc_referals AS r JOIN mc_accounts AS a ON a.discordid=r.user GROUP BY user ORDER BY cnt DESC LIMIT {page*25},25')
			players = await cursor.fetchall()
		if not players:
			embed = discord.Embed(description='Никто никого не приглашал. Молчат дома.',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		playerlist = []
		for nick,discordid,count in players:
			user = interaction.guild.get_member(discordid)
			nick = nick.replace('_','\\\\_')
			if user:
				playerlist.append(f'**{nick}** ({user.mention}): **{count}**')
			else:
				playerlist.append(f'**{nick}**: **{count}**')
		playerlist = '\n'.join(playerlist)
		embed = discord.Embed(title='Топ активности',description=f'У них похоже много друзей, не так-ли?\n\n{playerlist}',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=False)
		
	@app_commands.command(name='referals',description='список приглашенных вами игроков')
	@app_commands.rename(page='страница')
	async def referals(self, interaction: discord.Interaction, page: int = 1):
		page = 0 if page < 1 else page-1
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT nick,discordid FROM mc_referals JOIN mc_accounts ON discordid=referal WHERE user={interaction.user.id} LIMIT {page*25},25')
			players = await cursor.fetchall()
			await cursor.execute(f'SELECT COUNT(*) FROM mc_referals WHERE user={interaction.user.id}')
			count = (await cursor.fetchone())[0]
		if not players:
			embed = discord.Embed(description='Похоже у вас нету поклонников, но вы можете это исправить.\nПопросите указать ваш игровой ник при регистрации\nВы и ваш товарищ получите премиум',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		playerlist = []
		for nick,discordid in players:
			user = interaction.guild.get_member(discordid)
			nick = nick.replace('_','\\\\_')
			if user:
				playerlist.append(f'**{nick}** ({user.mention})')
			else:
				playerlist.append(f'**{nick}**')
		playerlist = '\n'.join(l)
		embed = discord.Embed(title='Приглашенные вами',description=f'Всего: {count}\n\n{playerlist}',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=False)

	@commands.Cog.listener()
	async def on_interaction(self,interaction: discord.Interaction):
		if interaction.type == discord.InteractionType.component:
			customid = interaction.data['custom_id']
			if customid == "inactive_recovery_start":
				await self.recovery.callback(self,interaction)
			elif customid == "authorize":
				await self.authorize.callback(self,interaction)
			elif customid == "authcode":
				await self.authcode.callback(self,interaction)
			elif customid == "logout":
				await self.logout.callback(self,interaction)
			elif customid == "inactive_recovery_approve":
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с заявками',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id FROM mc_inactive_recovery WHERE messageid={interaction.message.id}')
					if (id:=await cursor.fetchone()):
						await self.recovery_accept.callback(self,interaction,id[0])
			elif customid == "inactive_recovery_disapprove":
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с заявками',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await interaction.response.send_modal(self.recovery_decline_modal())
			elif customid == "registration_start_bedrock":
				await interaction.response.send_modal(self.bedrock_registration_modal())
			elif customid == "registration_start_java":
				await interaction.response.send_modal(self.java_registration_modal())
			elif customid == "registration_stage_open":
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT stage FROM mc_registrations WHERE discordid={interaction.user.id} AND channelid={interaction.channel_id}')
					stage = await cursor.fetchone()
					if stage:
						current_stage = stage[0]
						content,embeds,component = self.parseQuestions(current_stage)
						if self.isFormStage(current_stage):
							await interaction.response.send_modal(component)
						else:
							await interaction.response.edit_message(embeds=embeds,content=content,view=component)
					else:
						embed = discord.Embed(description='Вы не являетесь участником данной регистрации',color=discord.Colour.red())
						await interaction.response.send_message(embed=embed, ephemeral=True)
			elif customid == "registration_skip_stage":
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id,stage,nick,referal FROM mc_registrations WHERE discordid={interaction.user.id} AND channelid={interaction.channel.id}')
					values = await cursor.fetchone()
					if values:
						id,stage,nick,referal = values
						if (next_stage:= self.getNextStage(stage)) != None:
							await cursor.execute(f'UPDATE mc_registrations SET stage=\'{next_stage}\' WHERE id={id}')
							if self.isFormStage(next_stage):
								content,embeds,component = self.registrationButton(next_stage)
								await interaction.response.edit_message(embeds=embeds,content=content,view=component)
							else:
								content,embeds,component = self.parseQuestions(next_stage)
								await interaction.response.edit_message(embeds=embeds,content=content,view=component)
						else:
							if referal:
								referal = interaction.guild.get_member(referal)
							await self.create_register(interaction,nick,id,referal)	
					else:
						embed = discord.Embed(description='Вы не являетесь участником данной регистрации',color=discord.Colour.red())
						await interaction.response.send_message(embed=embed, ephemeral=True)
			elif customid == "registration_stage":
				question = interaction.data['values'][0]
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id,stage,nick,referal FROM mc_registrations WHERE discordid={interaction.user.id} AND channelid={interaction.channel.id}')
					values = await cursor.fetchone()
					if values:
						id,stage,nick,referal = values
						await cursor.execute(f'INSERT INTO mc_registrations_answers (id,stage,question) VALUES({id},\'{stage}\',\'{question}\')')
						if (next_stage:= self.getNextStage(stage,question)) != None:
							await cursor.execute(f'UPDATE mc_registrations SET stage=\'{next_stage}\' WHERE id={id}')
							if self.isFormStage(next_stage):
								content,embeds,component = self.registrationButton(next_stage)
								await interaction.response.edit_message(embeds=embeds,content=content,view=component)
							else:
								content,embeds,component = self.parseQuestions(next_stage)
								await interaction.response.edit_message(embeds=embeds,content=content,view=component)
						else:
							if referal:
								referal = interaction.guild.get_member(referal)
							await self.create_register(interaction,nick,id,referal)	
					else:
						embed = discord.Embed(description='Вы не являетесь участником данной регистрации',color=discord.Colour.red())
						await interaction.response.send_message(embed=embed, ephemeral=True)
			elif customid == 'registration_disapprove':
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с заявками',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				await interaction.response.send_modal(self.registration_decline_modal())
			elif customid == 'registration_approve':
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с заявками',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id FROM mc_registrations WHERE messageid={interaction.message.id}')
					if (id:=await cursor.fetchone()):
						await self.registration_accept.callback(self,interaction,id[0])
			elif customid == 'unlink_account':
				await self.unlink.callback(interaction, app_commands.Choice(name='маня мирок', value=int(interaction.data['values'][0])))
		elif interaction.type == discord.InteractionType.modal_submit:
			customid = interaction.data['custom_id']
			if customid == "inactive_recovery_submit":
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id FROM mc_inactive_recovery WHERE discordid={interaction.user.id} AND closed IS NULL')
					if not cursor.fetchone():
						await cursor.execute(f'SELECT ((SUM(closed)-SUM(sended))/COUNT(*)) FROM mc_inactive_recovery WHERE closed IS NOT NULL') 
						if (time:=(await cursor.fetchone()[0])):
							time = relativeTimeParser(seconds=time,greater=True)
							time = f'Среднее время обработки заявки {time}'
						else:
							time = None

						embed = discord.Embed(description='Заявка на восстановление создана!\nОжидайте решение модерации.',color=discord.Colour.green())
						if time:
							embed.set_footer(text=time)
						await interaction.response.send_message(embed=embed,ephemeral=True)	
						
						embed = discord.Embed(color=discord.Colour.green())
						embed.add_field(name='Восстановление игрового аккаунта',value='Заявка на восстановление создана!\nОжидайте решение модерации.')
						if time:
							embed.set_footer(text=time)
						try:
							await interaction.user.send(embed=embed)
						except:
							pass

						answers = [component['components'][0]['value'] for component in interaction.data['components']]
						await self.create_inactive_recovery(interaction.user, answers)
					else:
						embed = discord.Embed(description=f'У вас уже есть активная заявка на восстановление аккаунта',color=discord.Colour.red())
						await interaction.response.send_message(embed=embed, ephemeral=True)
			elif customid == "inactive_recovery_disapprove":
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с заявками',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				reason = interaction.data['components'][0]['components'][0]['value']
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id FROM mc_inactive_recovery WHERE messageid={interaction.message.id}')
					if (id:=await cursor.fetchone()):
						await self.recovery_accept.callback(self,interaction,id[0],reason)
			elif customid == "registration_start_bedrock":
				nick = interaction.data['components'][0]['components'][0]['value']
				referal = interaction.data['components'][1]['components'][0]['value']
				referal = referal if referal.replace(' ','') != '' else None
				await self.register.callback(self,interaction, app_commands.Choice(name='bedrock edition', value=1), nick, referal)
			elif customid == "registration_start_java":
				nick = interaction.data['components'][0]['components'][0]['value']
				referal = interaction.data['components'][1]['components'][0]['value']
				referal = referal if referal.replace(' ','') != '' else None
				await self.register.callback(self,interaction, app_commands.Choice(name='java edition', value=0), nick, referal)
			elif customid == "registration_stage":
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id,stage,nick,referal FROM mc_registrations WHERE discordid={interaction.user.id} AND channelid={interaction.channel.id}')
					values = await cursor.fetchone()
					if values:
						id,stage,nick, referal = values
						
						request = []
						for component in interaction.data['components']:
							component = component['components'][0]
							answer = component['value']
							if answer:
								answer = answer.replace("\\","/")
								question = component['custom_id'] 
								request.append(f'({id},\'{stage}\',\'{question}\',\'{answer}\')')
						if request:
							request = ','.join(request)
							await cursor.execute(f'INSERT INTO mc_registrations_answers (id,stage,question,answer) VALUES {request}')
						
						if (next_stage:= self.getNextStage(stage)) != None:
							await cursor.execute(f'UPDATE mc_registrations SET stage=\'{next_stage}\' WHERE id={id}')
							if self.isFormStage(next_stage):
								content,embeds,component = self.registrationButton(next_stage)
								await interaction.response.edit_message(embeds=embeds,content=content,view=component)
							else:
								content,embeds,component = self.parseQuestions(next_stage)
								await interaction.response.edit_message(embeds=embeds,content=content,view=component)
						else:
							if referal:
								referal = interaction.guild.get_member(referal)
							await self.create_register(interaction,nick,id,referal)	
					else:
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['invalid-registration-user'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
			elif customid == "registration_disapprove":
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с заявками',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				reason = interaction.data['components'][0]['components'][0]['value']
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id FROM mc_registrations WHERE messageid={interaction.message.id}')
					if (id:=await cursor.fetchone()):
						await self.registration_accept.callback(self,interaction,id[0],reason)

	async def on_check(self):
		guild = self.bot.guild()
		registered_role = guild.get_role(self.registered_role)

		async with self.bot.cursor() as cursor:
			if self.counter['enabled']:
				await cursor.execute('SELECT 0+COUNT(*) FROM mc_accounts WHERE inactive=FALSE')
				count = (await cursor.fetchone())[0]
				for channel in self.counter['channels']:
					if (channel:=guild.get_channel(channel)):
						await channel.edit(name=self.counter['format'].format(count=count))
			#
			# check inactives		
			#
			if self.inactive['enabled']:
				if 'premium' in self.bot.enabled_modules:
					await cursor.execute(f'SELECT a.discordid FROM mc_accounts AS a LEFT JOIN discord_premium AS p ON p.discordid=a.discordid WHERE COALESCE(p.end,0)<UNIX_TIMESTAMP() AND a.inactive=FALSE AND UNIX_TIMESTAMP()-a.last_join>{self.inactive["time"]}')
				else:
					await cursor.execute(f'SELECT discordid FROM mc_accounts WHERE mc_accounts.inactive=FALSE AND UNIX_TIMESTAMP()-mc_accounts.last_join>{self.inactive["time"]}')
				if (ids:=await cursor.fetchall()):
					if 'premium' in self.bot.enabled_modules:
						await cursor.execute(f'UPDATE mc_accounts,discord_premium SET mc_accounts.inactive=TRUE WHERE mc_accounts.discordid=discord_premium.discordid AND COALESCE(discord_premium.end,0)<UNIX_TIMESTAMP() AND mc_accounts.inactive=FALSE AND UNIX_TIMESTAMP()-mc_accounts.last_join>{self.inactive["time"]}')
					else:
						await cursor.execute(f'UPDATE mc_accounts SET mc_accounts.inactive=TRUE WHERE mc_accounts.inactive=FALSE AND UNIX_TIMESTAMP()-mc_accounts.last_join>{self.inactive["time"]}')
					
					inactive_role = guild.get_role(self.inactive["role"])
					for discordid in ids:
						if (member:=guild.get_member(discordid[0])):
							try:
								await member.remove_roles(self.registered_role)
								await member.add_roles(inactive_role)
							except:
								pass
			#
			# check exceptions
			#
			await cursor.execute(f'SELECT a.nick,a.id,a.discordid FROM mc_exceptions AS e JOIN mc_accounts AS a ON e.id=a.id WHERE e.end<UNIX_TIMESTAMP()')
			users = await cursor.fetchall()
			if users:
				await cursor.execute(f'DELETE FROM mc_exceptions WHERE end<UNIX_TIMESTAMP()')
				guild = self.bot.guild()
				role = guild.get_role(self.exception_role)
				for nick,id,discordid in users:
					member = guild.get_member(discordid)
					if member:
						try:
							player=await self.skcrewapi.player(id)
							await self.skcrewapi.signals(signals=[skcrew.Signal('unexceptioned',[str(id)])],servers=[player.server])
						except:
							pass
						await member.remove_roles(role)
			#
			# check registrations 
			#
			await cursor.execute(f'SELECT channelid FROM mc_registrations WHERE channel_deleted=FALSE AND approved=FALSE AND closed IS NULL AND sended IS NULL AND time+{self.request_duration}<UNIX_TIMESTAMP()')
			channels = await cursor.fetchall()
			await cursor.execute(f'UPDATE mc_registrations SET channel_deleted=TRUE, closed=UNIX_TIMESTAMP(), close_reason=\'Истечение срока прохождения регистрации\' WHERE channel_deleted=FALSE AND approved=FALSE AND closed IS NULL AND sended IS NULL AND time+{self.request_duration}<UNIX_TIMESTAMP()')
			for channelid in channels:
				if (channel:=guild.get_channel(channelid[0])):
					await channel.delete()

			await cursor.execute(f'SELECT channelid FROM mc_registrations WHERE channel_deleted=FALSE AND approved=FALSE AND closed IS NOT NULL AND closed+{self.disapproved_time}<UNIX_TIMESTAMP()')
			channels = await cursor.fetchall()
			await cursor.execute(f'UPDATE mc_registrations SET channel_deleted=TRUE WHERE channel_deleted=FALSE AND approved=FALSE AND closed IS NOT NULL AND closed+{self.disapproved_time}<UNIX_TIMESTAMP()')
			for channelid in channels:
				if (channel:=guild.get_channel(channelid[0])):
					await channel.delete()

			await cursor.execute(f'SELECT channelid FROM mc_registrations WHERE channel_deleted=FALSE AND approved=TRUE AND closed IS NOT NULL AND closed+{self.approved_time}<UNIX_TIMESTAMP()')
			channels = await cursor.fetchall()
			await cursor.execute(f'UPDATE mc_registrations SET channel_deleted=TRUE WHERE channel_deleted=FALSE AND approved=TRUE AND closed IS NOT NULL AND closed+{self.approved_time}<UNIX_TIMESTAMP()')
			for channelid in channels:
				if (channel:=guild.get_channel(channelid[0])):
					await channel.delete()

	@commands.Cog.listener()	
	async def on_member_remove(self, member: discord.Member):
		if not self.inactive["on_leave"]:
			return
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={member.id}')
			data = await cursor.fetchone()
			if not data:
				return
			id,nick = data
			try:
				player=await self.skcrewapi.player(id)
				await self.skcrewapi.signals(signals=[skcrew.Signal('leaved',[str(id)])],servers=[player.server])
			except:
				pass
			await cursor.execute(f'UPDATE mc_accounts SET mc_accounts.inactive=TRUE WHERE discordid={member.id}')

	async def fetchDiscordByNick(self,nick: str):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM mc_accounts WHERE LOWER(nick) LIKE LOWER(%s)',(nick,))
			discordid = await cursor.fetchone()
		if discordid:
			return discordid[0]
		nick = nick.lower()
		member = discord.utils.find(lambda m: re.match('.*'+nick+'.*',m.display_name.lower()) or re.match('.*'+nick+'.*',m.name.lower()), self.bot.guild().members)
		if member:
			return member.id
		return None
	async def getBedrockUUID(self, gamertag: str):
		gamertag = gamertag[1:] if gamertag.startswith('.') else gamertag
		async with aiohttp.ClientSession() as session:
			try:
				async with session.get(url=f'https://api.geysermc.org/v2/xbox/xuid/{gamertag}') as response:
					return await response.json()
			except:
				return None
			if len(str(gamertag)) > 16:
				return None
		left = hex(gamertag)[2:]
		decades = [12,4,4,4,8]
		final = ['00000000','0000','0000','0000','000000000000']
		for i in range(5):
			l = len(left)
			s = l-decades[i]
			if s>0:
				left,right = left[:s],left[s:]
				final[4-i] = right
			else:
				final[4-i]= final[i][l:] + left
				break
		return '-'.join(final)
	def getJavaUUID(self,nickname: str):
		class NULL_NAMESPACE:
			bytes = b''
		return uuid.uuid3(NULL_NAMESPACE, "OfflinePlayer:"+nickname)
	
	def parseQuestions(self, stage:str):
		stage = self.stages['stages'][stage]

		content, reference, embeds, view = None, None, None, None
		if 'message' in stage:
			content, reference, embeds, view = json_to_message(stage['message'])

		if 'questions' in stage:
			component = discord.ui.Modal(timeout=None,title=stage['title'],custom_id='registration_stage')
			if stage['shuffle']:
				for key in random.sample(list(stage['questions'].keys()), stage['max']):
					question = stage['questions'][key]
					if 'description' in question:
						component.add_item(discord.ui.TextInput(custom_id=key, min_length=question['min'],max_length=question['max'],label=question['title'],style=discord.TextStyle.paragraph, placeholder=question['description'], required=question['required']))
					else:
						component.add_item(discord.ui.TextInput(custom_id=key, min_length=question['min'],max_length=question['max'],label=question['title'],style=discord.TextStyle.paragraph, required=question['required']))
			else:
				keys = list(stage['questions'].keys())
				for i in range(len(keys)):
					key = keys[i]
					question = stage['questions'][key]
					if 'description' in question:
						component.add_item(discord.ui.TextInput(custom_id=key, min_length=question['min'],max_length=question['max'],label=question['title'],style=discord.TextStyle.paragraph, placeholder=question['description'], required=question['required']))
					else:
						component.add_item(discord.ui.TextInput(custom_id=key, min_length=question['min'],max_length=question['max'],label=question['title'],style=discord.TextStyle.paragraph, required=question['required']))
		elif 'choose'in stage:
			component = discord.ui.View(timeout=None)
			options = []
			if stage['shuffle']:
				for key in random.sample(list(stage['choose'].keys()), stage['max']):
					choose = stage['choose'][key]
					if 'description' in choose:
						options.append(discord.SelectOption(label=choose['title'],value=key,description=choose['description']))
					else:
						options.append(discord.SelectOption(label=choose['title'],value=key))
			else:
				keys = list(stage['choose'].keys())
				for i in range(len(keys)):
					key = keys[i]
					choose = stage['choose'][key]
					if 'description' in choose:
						options.append(discord.SelectOption(label=choose['title'],value=key,description=choose['description']))
					else:
						options.append(discord.SelectOption(label=choose['title'],value=key))
			component.add_item(discord.ui.Select(custom_id='registration_stage',disabled=False, min_values=1, max_values=1, placeholder=stage['title'], options=options))

		return content,embeds,component
	def registrationButton(self, stage: str):
		stage = self.stages['stages'][stage]
		
		content, reference, embeds, view = None, None, None, None
		if 'message' in stage:
			content, reference, embeds, view = json_to_message(stage['message'])

		if 'button' in stage:
			button = stage['button']
			title = button['title'] if 'title' in button else 'Нажмите для продолжения'
			color = discord.ButtonStyle(button['color']) if 'color' in button else discord.ButtonStyle.green
		else:
			title = 'Нажмите для продолжения'
			color = discord.ButtonStyle.green

		component = discord.ui.View(timeout=None)
		if 'questions' in stage: 
			component.add_item(discord.ui.Button(disabled=False,custom_id="registration_stage_open",label=title,style=color))
		else:
			component.add_item(discord.ui.Button(disabled=False,custom_id="registration_skip_stage",label=title,style=color))

		return content,embeds,component
	def isFormStage(self, stage: str):
		if 'choose' in (self.stages['stages'][stage]):
			return False
		return True
	def getNextStage(self, stage:str, question: str = None):
		stage = self.stages['stages'][stage]
		if question:
			if 'choose' in stage:
				question = stage['choose'][question]
				if 'next_stage' in question:
					return question['next_stage']
		return stage['next_stage'] if 'next_stage' in stage else None
	async def parseAnswers(self,id: int):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT DISTINCT a.stage,a.question,a.answer FROM mc_registrations_answers AS a JOIN mc_registrations AS s ON s.id=a.id WHERE a.id={id}')
			answers = await cursor.fetchall()
		final = []
		stages = self.stages['stages']
		for stage,question,answer in answers:
			stage = stages[stage]
			if answer:
				final.append([stage['questions'][question]['title'],answer])
			else:
				final.append([stage['title'],stage['choose'][question]['title']])
		return final
	
	async def create_register(self,interaction,nick, id, referal):
		async with self.bot.cursor() as cursor:
			await cursor.execute("SELECT ((SUM(closed)-SUM(sended))/COUNT(*)) FROM mc_registrations WHERE closed IS NOT NULL AND sended IS NOT NULL")
			if (time:=((await cursor.fetchone())[0])):
				time = relativeTimeParser(seconds=time,greater=True)
				time = f'Среднее время обработки заявки {time}'
			else:
				time = None

			embed = discord.Embed(description='Заявка на регистрацию создана!\nОжидайте решение модерации.',color=discord.Colour.green())
			if time:
				embed.set_footer(text=time)
			await interaction.response.edit_message(embed=embed,content=None,view=None)	
			
			embed = discord.Embed(color=discord.Colour.green())
			embed.add_field(name='Регистрация на игровом сервере',value='Заявка на регистрацию создана!\nОжидайте решение модерации.')
			if time:
				embed.set_footer(text=time)
			try:
				await interaction.user.send(embed=embed)
			except:
				pass

			attributes = []
			attributes.append(f'**Discord аккаунт:** {interaction.user.mention}')
			nick = nick.replace('_','\\_')
			attributes.append(f'**Никнейм:** {nick}')
			if referal:
				attributes.append(f'**Приглашён:** {referal.mention}')
			attributes = '\n'.join(attributes)
			embed = discord.Embed(title=f'Заявка на регистрацию \#{id}',description=f'{attributes}',color=discord.Colour.greyple())

			for answer in await self.parseAnswers(id):
				embed.add_field(name=answer[0],value=answer[1],inline=False)
			
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="registration_approve",label='Принять',style=discord.ButtonStyle(3)))
			view.add_item(discord.ui.Button(disabled=False,custom_id="registration_disapprove",label='Отклонить',style=discord.ButtonStyle(4)))
			message = await self.bot.guild().get_channel(self.channel).send(embed=embed,view=view)
			await cursor.execute(f'UPDATE mc_registrations SET sended=UNIX_TIMESTAMP(), messageid={message.id} WHERE id={id}')
	
	async def remove_inactive(self, member):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'UPDATE mc_accounts SET inactive=FALSE, last_join=UNIX_TIMESTAMP() WHERE discordid={member.id}')
			await cursor.execute(f'UPDATE mc_inactive_recovery SET approved=TRUE,closed=UNIX_TIMESTAMP(),close_reason=\'Ваша заявка о восстановлении была одобрена\' WHERE discordid={member.id} AND closed IS NULL AND approved IS FALSE')
			await member.remove_roles(interaction.guild.get_role(self.inactive['role']))
			await member.add_roles(interaction.guild.get_role(self.registered_role))
			await cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={member.id}')
			id,nick = await cursor.fetchone()
			try:
				player=await self.skcrewapi.player(id)
				await self.skcrewapi.signals(signals=[skcrew.Signal('inactive_remove',[str(id)])],servers=[player.server])
			except:
				pass

	async def create_inactive_recovery(self, member, answers: [str,...] = None):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id, nick, time_played, first_join, last_join FROM mc_accounts WHERE discordid = {member.id}')
			if not (data:=await cursor.fetchone()):
				return False
			id, nick, time_played, first_join, last_join = data

			await cursor.execute('SELECT AUTO_INCREMENT FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = \'mc_inactive_recovery\'')
			newid = await cursor.fetchone()[0]
			await cursor.execute(f'SELECT bedrockUsername FROM LinkedPlayers WHERE javaUniqueId=UNHEX(REPLACE(\'{id}\', \'-\', \'\'))')
			data = await cursor.fetchone()
			
			attributes = []
			attributes.append(f'**Discord аккаунт:** {member.mention}')
			nick = nick.replace('_','\\_')
			if data[0]:
				subname = data[0].replace('_','\\')
				attributes.append(f'**Никнейм:** {nick} ({subname})')
			else:
				attributes.append(f'**Никнейм:** {nick}')
			if first_join!=last_join:
				attributes.append(f'**Был(а) онлайн:** <t:{last_join}:R>')
			attributes.append(f'**Регистрация:** <t:{first_join}:R>')
			if time_played > 0:
				time_played = relativeTimeParser(seconds=time_played,greater=True)
				attributes.append(f'**Время игры:** {time_played}')

			attributes = '\n'.join(attributes)
			embed = discord.Embed(title=f'Заявка на восстановление \#{id}',description=f'{attributes}',color=discord.Colour.greyple())

			questions = self.recovery_questions()
			if answers:
				for i in range(len(questions)):
					embed.add_field(name=questions[i]['label'],value=answers[i],inline=False)
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="inactive_recovery_approve",label='Принять',style=discord.ButtonStyle(3)))
			view.add_item(discord.ui.Button(disabled=False,custom_id="inactive_recovery_disapprove",label='Отклонить',style=discord.ButtonStyle(4)))
			message = await self.bot.guild().get_channel(self.channel).send(embed=embed,view=view)
			await cursor.execute(f'INSERT INTO mc_inactive_recovery (discordid,messageid) VALUES ({member.id},{message.id})')

	def bedrock_registration_modal(self):
		modal = discord.ui.Modal(title='Регистрация Bedrock Edition', custom_id = "registration_start_bedrock")
		modal.add_item(discord.ui.TextInput(min_length=1,max_length=17,label='Ваш никнейм',style=discord.TextStyle.short, placeholder='Введите его сюда'))
		modal.add_item(discord.ui.TextInput(min_length=1,max_length=17,label='Кто вас пригласил?',style=discord.TextStyle.short,required=False, placeholder='Введите ник (необязательно)'))
		return modal
	def java_registration_modal(self):
		modal = discord.ui.Modal(title='Регистрация Java Edition', custom_id = "registration_start_java")
		modal.add_item(discord.ui.TextInput(min_length=3,max_length=16,label='Ваш никнейм',style=discord.TextStyle.short, placeholder='Введите его сюда'))
		modal.add_item(discord.ui.TextInput(min_length=1,max_length=17,label='Кто вас пригласил?',style=discord.TextStyle.short,required=False, placeholder='Введите ник (необязательно)'))
		return modal
	def registration_decline_modal(self):
		modal = discord.ui.Modal(title='Отказ заявки', custom_id = "registration_disapprove")
		modal.add_item(discord.ui.TextInput(max_length=512,label='Опишите причину отказа',style=discord.TextStyle.paragraph, placeholder='Шизик не сможет играть? похуй'))
		return modal
	
	def recovery_questions(self):
		recovery = self.stages['recovery']
		size = len(recovery)
		size = size if size<5 else 5
		return [recovery[i] for i in range(size)]
	def recovery_modal(self):
		modal = discord.ui.Modal(title='Восстановление аккаунта', custom_id = "inactive_recovery_submit")
		for question in self.recovery_questions():
			modal.add_item(discord.ui.TextInput(min_length=question['min'],max_length=question['max'],label=question['label'],style=discord.TextStyle.paragraph, placeholder=question['placeholder']))
		return modal
	def recovery_decline_modal(self):
		modal = discord.ui.Modal(title='Отказ заявки', custom_id = "inactive_recovery_disapprove")
		modal.add_item(discord.ui.TextInput(max_length=512,label='Опишите причину отказа',style=discord.TextStyle.paragraph, placeholder='Шизик не сможет вернуться? Грустно (х2).'))
		return modal

	async def add_exception(self, nick: str, reason: str = None, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0, years: int = 0):
		time = seconds+(minutes*60)+(hours*3600)+(days*86400)+(years*31536000)
		id = self.getJavaUUID(nick) if not nick.startswith('.') else getBedrockUUID(nick)
		if not id:
			return False
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM mc_accounts WHERE id=\'{id}\'')
			if not (data:=await cursor.fetchone()):
				return False
			if reason:
				await cursor.execute(f'INSERT INTO mc_exceptions (id,end,reason) VALUES (\'{id}\',UNIX_TIMESTAMP()+{time},%s) ON DUPLICATE KEY UPDATE end=end+{time}, reason=%s',(reason,reason,))
			else:
				await cursor.execute(f'INSERT INTO mc_exceptions (id,end) VALUES (\'{id}\',UNIX_TIMESTAMP()+{time}) ON DUPLICATE KEY UPDATE end=end+{time}')
			try:
				player=await self.skcrewapi.player(id)
				await self.skcrewapi.signals(signals=[skcrew.Signal('exceptioned',[str(id)])],servers=[player.server])
			except:
				pass
			if(member:=self.bot.guild().get_member(data[0])):
				await member.add_roles(self.bot.guild().get_role(self.exception_role))
				return member
			return True
	async def remove_exception(self, nick: str):
		id = self.getJavaUUID(nick) if not nick.startswith('.') else getBedrockUUID(nick)
		if not id:
			return False
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT a.discordid FROM mc_exceptions AS e JOIN mc_accounts AS a on a.id=e.id WHERE e.id=\'{id}\'')
			if (data:=await cursor.fetchone()):
				await cursor.execute(f'DELETE FROM mc_exceptions WHERE id=\'{id}\'')
				try:
					player=await self.skcrewapi.player(id)
					await self.skcrewapi.signals(signals=[skcrew.Signal('unexceptioned',[str(id)])],servers=[player.server])
				except:
					pass
				if(member:=self.bot.guild().get_member(data[0])):
					await member.remove_roles(self.bot.guild().get_role(self.exception_role))
					return member
				return True
		return False

	async def check_manage_permissions(self, member: discord.Member):
		roles = []
		guild = self.bot.guild()
		for application_command in await self.bot.tree.fetch_commands(guild=guild):
			if application_command.name == Minecraft.minecraft_group.name:
				try:
					roles = [permission.id for permission in (await application_command.fetch_permissions(guild)).permissions if permission.permission]
				except:
					return True
				break
		if not bool(set(role.id for role in member.roles) & set(roles)):
			return False
		return True

	async def sync_roles(self):
		guild = self.bot.guild()
		
		registered_role = guild.get_role(self.registered_role)

		async with self.bot.cursor() as cursor:
			if self.inactive['enabled']:
				await cursor.execute(f'SELECT a.discordid FROM mc_accounts AS a LEFT JOIN mc_exceptions AS e ON a.id=e.id WHERE (e.end IS NULL OR e.end<UNIX_TIMESTAMP()) AND inactive=FALSE')
			else:
				await cursor.execute(f'SELECT a.discordid FROM mc_accounts AS a LEFT JOIN mc_exceptions AS e ON a.id=e.id WHERE (e.end IS NULL OR e.end<UNIX_TIMESTAMP())')
			users = await cursor.fetchall()
		users = [id[0] for id in users] if users else []
		for member in registered_role.members:
			fetched = None
			for i in range(len(users)):
				if member.id == users[i]:
					fetched = i
			if fetched != None:
				users.pop(fetched)
			else:
				await member.remove_roles(registered_role)
		for id in users:
			if (member:= guild.get_member(id)):
				await member.add_roles(registered_role)

		if self.inactive['enabled']:
			inactive_role = guild.get_role(self.inactive['role'])
			async with self.bot.cursor() as cursor:
				await cursor.execute(f'SELECT a.discordid FROM mc_accounts AS a LEFT JOIN mc_exceptions AS e ON a.id=e.id WHERE (e.end IS NULL OR e.end<UNIX_TIMESTAMP()) AND inactive=TRUE')
				users = await cursor.fetchall()
			users = [id[0] for id in users] if users else []
			for member in inactive_role.members:
				fetched = None
				for i in range(len(users)):
					if member.id == users[i]:
						fetched = i
				if fetched != None:
					users.pop(fetched)
				else:
					await member.remove_roles(inactive_role)
			for id in users:
				if (member:= guild.get_member(id)):
					await member.add_roles(inactive_role)

		exception_role = guild.get_role(self.exception_role)

		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT a.discordid FROM mc_accounts AS a LEFT JOIN mc_exceptions AS e ON a.id=e.id WHERE e.end>UNIX_TIMESTAMP()')
			users = await cursor.fetchall()
		users = [id[0] for id in users] if users else []
		for member in exception_role.members:
			fetched = None
			for i in range(len(users)):
				if member.id == users[i]:
					fetched = i
			if fetched != None:
				users.pop(fetched)
			else:
				await member.remove_roles(exception_role)
		for id in users:
			if (member:= guild.get_member(id)):
				await member.add_roles(exception_role)
