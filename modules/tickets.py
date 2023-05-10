import discord
from discord import app_commands
from discord.ext import commands,tasks
from datetime import datetime
from utils import relativeTimeParser
from io import BytesIO

class Tickets(commands.Cog):
	def __init__(self, bot,channel: int, category: int,check_every_seconds: int, max_opened_per_user: int = 5):
		self.bot = bot
		self.max_opened_per_user = max_opened_per_user
		self.category = category
		self.channel = channel
		
		self.check_every_seconds = check_every_seconds
		self.ticket_block_check = tasks.loop(seconds=self.check_every_seconds)(self.on_ticket_block_check)
	
	@commands.Cog.listener()
	async def on_ready(self):	
		async with self.bot.cursor() as cursor:
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_tickets (id INT NOT NULL AUTO_INCREMENT, discordid BIGINT NOT NULL, ticket_text TEXT NOT NULL, time INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(),messageid BIGINT, channelid BIGINT, receiver BIGINT, closer BIGINT, receiver_time INT(11), closed INT(11), PRIMARY KEY(id))")
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_tickets_blocks (discordid BIGINT NOT NULL, time INT(11) NOT NULL, PRIMARY KEY(discordid))")
		self.ticket_block_check.start()

	def cog_unload(self):
		self.ticket_block_check.cancel()

	tickets_group = app_commands.Group(name='tickets', description='Управление тикетами')

	@tickets_group.command(name='button',description='Создать кнопку создания тикетов')
	@app_commands.rename(label='название',color='цвет')
	@app_commands.describe(label='максимальная длина 80 символов')
	@app_commands.choices(color=[app_commands.Choice(name=name,value=value) for name,value in (('синяя',1),('серая',2),('зеленая',3),('красная',4))])
	async def tickets_button(self, interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
		label = label[:80] if label else 'Создать тикет'
		color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
		view = discord.ui.View(timeout=None)
		view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_create",label=label,style=color))
		await interaction.channel.send(view=view)
		embed = discord.Embed(description='Кнопка создания тикетов создана',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)
		
	@tickets_group.command(name='active',description='показать активные тикеты')
	async def tickets_active(self, interaction: discord.Interaction):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id, messageid, channelid FROM discord_tickets WHERE closed IS NULL ORDER BY id')
			tickets = await cursor.fetchall()
		if tickets:
			tickets_list = []
			for id, messageid, channelid in tickets:
				message_link = f'https://discord.com/channels/{self.bot.guild_id}/{self.channel}/{messageid}'
				if channelid:
					channel_link = f'https://discord.com/channels/{self.bot.guild_id}/{channelid}'
					tickets_list.append(f'[Тикет \#{id}]({message_link}): [открыт]({channel_link})')
				else:
					tickets_.append(f'[Тикет \#{id}]({message_link})')
			tickets_list = '\n'.join(text)
			embed = discord.Embed(title='Активные тикеты',description=tickets_list,color=discord.Colour.green())
		else:
			embed = discord.Embed(description='Активные тикеты отсутствуют',color=discord.Colour.red())
		await interaction.response.send_message(embed=embed, ephemeral=True)

	@tickets_group.command(name='unblock',description='разблокировать пользователя')
	@app_commands.rename(member='пользователь')
	async def tickets_unblock(self, interaction: discord.Interaction, member: discord.Member):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid FROM discord_tickets_blocks WHERE discordid={member.id}')
			if await cursor.fetchone():
				await cursor.execute(f'DELETE FROM discord_tickets_blocks WHERE discordid={member.id}')
				embed = discord.Embed(description=f'Пользователь {member.mention} снова может засирать мозги админам своей хуйней',color=discord.Colour.green())
			else:
				embed = discord.Embed(description=f'Пользователь не имеет блокировки создания тикетов',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
	
	@tickets_group.command(name='close',description='закрыть тикет')
	@app_commands.rename(id='номер_тикета')
	async def tickets_close(self, interaction: discord.Interaction, id: int):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT channelid,messageid FROM discord_tickets WHERE id={id} AND closed IS NULL')
			if not (ticket_data:=await cursor.fetchone()):
				embed = discord.Embed(description='Указанный тикет не найден',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			await cursor.execute(f'UPDATE discord_tickets SET receiver_time=COALESCE(receiver_time, UNIX_TIMESTAMP()), channelid=NULL, receiver=COALESCE(receiver, {interaction.user.id}), closer={interaction.user.id}, closed=UNIX_TIMESTAMP() WHERE id={id}')
		
		embed = discord.Embed(description=f'Тикет закрыт',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)

		ticket_channel = interaction.guild.get_channel(ticket_data[0]) if ticket_data[0] else None
		try:
			ticket_message = await interaction.guild.get_channel(self.channel).fetch_message(ticket_data[1])
		except:
			ticket_message = None

		if ticket_message and ticket_channel:
			thread = await ticket_message.create_thread(name='История тикета')
			authors = {}
			skip_first = True
			async for message in ticket_channel.history(limit=None,oldest_first=True):
				if skip_first:
					skip_first = False
					continue
				if message.content or message.embeds or message.attachments:
					files = [discord.File(BytesIO(await attachment.read(use_cached=False)),filename=attachment.filename) for attachment in message.attachments]
					if message.author.id not in authors:
						authors[message.author.id] = await ticket_message.channel.create_webhook(name=str(message.author),avatar=(await message.author.avatar.read() if message.author.avatar else None))
					await authors[message.author.id].send(wait=False,content=message.content,embeds=message.embeds,files=files,thread=thread)
			await thread.edit(archived=True, locked=True, pinned=False)
			await ticket_channel.delete()
			for webhook in authors.values():
				await webhook.delete()
		if ticket_message:
			embed = ticket_message.embeds[0]
			time = int(datetime.now().timestamp())
			embed.add_field(name=f'Закрыт <t:{time}:R>',value=f'{interaction.user.mention}')
			await ticket_message.edit(view=None,embed=embed)
					
	@tickets_group.command(name='accept',description='принять тикет')
	@app_commands.rename(id='номер_тикета')
	async def tickets_accept(self, interaction: discord.Interaction, id: int):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT discordid,messageid,ticket_text FROM discord_tickets WHERE id={id} AND channelid IS NULL AND closed IS NULL')
			if not (ticket_data:=await cursor.fetchone()):
				embed = discord.Embed(description='Указанный тикет не найден',color=discord.Colour.red())
				interaction.response.send_message(embed=embed,ephemeral=True)
				return
			
			ticket_member = interaction.guild.get_member(ticket_data[0])
			try:
				ticket_message = await interaction.guild.get_channel(self.channel).fetch_message(ticket_data[1])
			except:
				ticket_message = None
			ticket_text = ticket_data[2]

			if ticket_member:
				category = interaction.guild.get_channel(self.category)
				overwrites = {
				    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
				    ticket_member: discord.PermissionOverwrite(read_messages=True, send_messages=True)
				}
				ticket_channel = await interaction.guild.create_text_channel(name=f'Тикет #{id}',category=category, overwrites=overwrites)
				await cursor.execute(f'UPDATE discord_tickets SET channelid={ticket_channel.id},receiver={interaction.user.id},receiver_time=UNIX_TIMESTAMP() WHERE id={id}')
				embed = discord.Embed(description=ticket_text,color=discord.Colour.greyple())
				await ticket_channel.send(content=ticket_member.mention,embed=embed)

				if ticket_message:
					time = int(datetime.now().timestamp())
					embed = ticket_message.embeds[0]
					embed.add_field(name=f'Принят <t:{time}:R>',value=f'{interaction.user.mention}')
					view = discord.ui.View(timeout=None)
					view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_close",label='Закрыть',style=discord.ButtonStyle(4)))
					view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_block",label='Заблокировать',style=discord.ButtonStyle(3)))
					await ticket_message.edit(view=view,embed=embed)
				
				channel_link = f'https://discord.com/channels/{self.bot.guild_id}/{ticket_channel.id}'
				embed = discord.Embed(description=f'Тикет принят, перейдите в [канал]({channel_link})',color=discord.Colour.green())
				try:
					notify_embed = discord.Embed(title='Система тикетов',description=f'Ваш тикет был принят, перейдите в [канал]({channel_link})',color=discord.Colour.green())
					await ticket_member.send(embed=embed)
				except:
					pass
			else:
				cursor.execute(f'UPDATE discord_tickets SET receiver_time=COALESCE(receiver_time, UNIX_TIMESTAMP()), channelid=NULL, receiver=COALESCE(receiver, \'{interaction.user.id}\'), closer=\'{interaction.user.id}\', closed=UNIX_TIMESTAMP() WHERE id={id}')
				
				if ticket_message:
					embed = ticket_message.embeds[0]
					time = int(datetime.now().timestamp())
					embed.add_field(name=f'Тикет закрыт <t:{time}:R>',value='Автор тикета покинул Discord сервер')
					await ticket_message.edit(view=None,embed=embed)

				embed = discord.Embed(description=f'Тикет был автоматически закрыт, так как пользователь покинул Discord сервер',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@tickets_group.command(name='block',description='заблокировать пользователя')
	@app_commands.rename(member='пользователь',hours='длительность')
	@app_commands.describe(hours='количество часов блокировки (поддерживает дробные значения)')
	async def tickets_block(self, interaction: discord.Interaction, member: discord.Member, hours: float = 24.0):
		async with self.bot.cursor() as cursor:
			duration = hours*3600
			await cursor.execute(f'SELECT channelid, discordid, messageid FROM discord_tickets WHERE discordid={member.id} AND closed IS NULL')
			tickets_data = await cursor.fetchall()
			await cursor.execute(f'UPDATE discord_tickets SET closed=UNIX_TIMESTAMP(), channelid=NULL, closer={interaction.user.id},receiver=COALESCE(receiver, {interaction.user.id}), receiver_time=COALESCE(receiver_time, UNIX_TIMESTAMP()) WHERE discordid={member.id} AND (closed IS NULL)')
			await cursor.execute(f'INSERT INTO discord_tickets_blocks (discordid,time) VALUES({member.id},UNIX_TIMESTAMP()+{duration}) ON DUPLICATE KEY UPDATE time=UNIX_TIMESTAMP()+{duration}')

		embed = discord.Embed(description='Пользователь заблокирован',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed,ephemeral=True)
		
		duration = relativeTimeParser(hours=hours,greater=True)
		tickets_channel = interaction.guild.get_channel(self.channel)
		if tickets_data:
			time = int(datetime.now().timestamp())
			authors = {}
			for channelid, discordid, messageid in tickets_data:
				try:
					ticket_message = await tickets_channel.fetch_message(messageid)
				except:
					ticket_message = None
				if ticket_message:
					embed = ticket_message.embeds[0]
					embed.add_field(name=f'Заблокировал автора на {duration} <t:{time}:R>',value=f'{interaction.user.mention}')
					await ticket_message.edit(view=None,embed=embed)
					if (ticket_channel:=interaction.guild.get_channel(channelid)):
						thread = await ticket_message.create_thread(name='История тикета')
						skip_first = True
						async for message in ticket_channel.history(limit=None,oldest_first=True):
							if skip_first:
								skip_first = False
								continue
							if message.content or message.embeds or message.attachments:
								files = [discord.File(BytesIO(await attachment.read(use_cached=False)),filename=attachment.filename) for attachment in message.attachments]
								if message.author.id not in authors:
									authors[message.author.id] = await ticket_message.channel.create_webhook(name=str(message.author),avatar=(await message.author.avatar.read() if message.author.avatar else None))
								await authors[message.author.id].send(wait=False,content=message.content,embeds=message.embeds,files=files,thread=thread)
						await thread.edit(archived=True, locked=True, pinned=False)
						await ticket_channel.delete()
			for webhook in authors.values():
				await webhook.delete()
	
	@app_commands.command(name='ticket',description='создать тикет')
	@app_commands.rename(text='текст_проблемы')
	async def ticket(self, interaction: discord.Interaction, text: str):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT COUNT(*) FROM discord_tickets WHERE discordid={interaction.user.id} AND (closed IS NULL)')
			if (await cursor.fetchone())[0] >= self.max_opened_per_user:
				embed = discord.Embed(description='У вас достигнут лимит созданных тикетов, ожидайте ответа',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return

			await cursor.execute(f'SELECT time FROM discord_tickets_blocks WHERE discordid={interaction.user.id} AND time>UNIX_TIMESTAMP()')
			if (time:=await cursor.fetchone()):
				time = time[0]
				embed = discord.Embed(description=f'Вы сможете создать новый тикет <t:{time}:R>',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			
			await cursor.execute('SELECT AUTO_INCREMENT FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = \'discord_tickets\'')
			id = (await cursor.fetchone())[0]

			text = text[:1500] if len(text) > 1500 else text
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_accept",label='Принять',style=discord.ButtonStyle(1)))
			view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_close",label='Закрыть',style=discord.ButtonStyle(4)))
			view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_block",label='Заблокировать',style=discord.ButtonStyle(3)))

			embed = discord.Embed(title=f'Тикет \#{id}',description=text,color=discord.Colour.greyple())
			message = await interaction.guild.get_channel(self.channel).send(content=f'Создан пользователем {interaction.user.mention}', embed=embed, view=view)
			await cursor.execute(f'INSERT INTO discord_tickets (discordid,messageid,ticket_text) VALUES ({interaction.user.id},{message.id},%s)',(text,))

			embed = discord.Embed(description='Тикет создан, вы получите уведомление как только его примут.',color=discord.Colour.green())
			await interaction.response.send_message(embed=embed, ephemeral=True)

	@commands.Cog.listener()
	async def on_interaction(self, interaction: discord.Interaction):
		if interaction.type == discord.InteractionType.modal_submit and interaction.data['custom_id'] == "ticket_create":
			if not await self.check_create_permissions(interaction.user):
				embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с тикетами',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			text = interaction.data['components'][0]['components'][0]['value']
			await self.ticket.callback(self,interaction,text)
		elif interaction.type == discord.InteractionType.component:
			customid = interaction.data['custom_id']
			if customid == "ticket_create":
				if not await self.check_create_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с тикетами',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT COUNT(*) FROM discord_tickets WHERE discordid={interaction.user.id} AND (closed IS NULL)')
					if (await cursor.fetchone())[0] >= self.max_opened_per_user:
						embed = discord.Embed(description='У вас достигнут лимит созданных тикетов, ожидайте ответа',color=discord.Colour.red())
						await interaction.response.send_message(embed=embed, ephemeral=True)
						return
					await cursor.execute(f'SELECT time FROM discord_tickets_blocks WHERE discordid={interaction.user.id} AND time>UNIX_TIMESTAMP()')
					if (time:=await cursor.fetchone()):
						time = time[0]
						embed = discord.Embed(description=f'Вы сможете создать новый тикет <t:{time}:R>',color=discord.Colour.red())
						await interaction.response.send_message(embed=embed, ephemeral=True)
						return

					await cursor.execute("SELECT ((SUM(receiver_time)-SUM(time))/COUNT(*)) FROM discord_tickets WHERE receiver IS NOT NULL")
					avg_time = await cursor.fetchone()
				
				modal = discord.ui.Modal(title='Создание тикета', custom_id = "ticket_create")
				if avg_time[0]:
					avg_time = relativeTimeParser(seconds=avg_time[0],greater=True) if avg_time[0] else None
					modal.add_item(discord.ui.TextInput(min_length=1,max_length=1500,label='Опишите вашу проблему',style=discord.TextStyle.paragraph, placeholder=f'Среднее время ответа {avg_time}'))
				else:
					modal.add_item(discord.ui.TextInput(min_length=1,max_length=1500,label='Опишите вашу проблему',style=discord.TextStyle.paragraph))
				await interaction.response.send_modal(modal)
			elif customid == 'ticket_close':
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с тикетами',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id FROM discord_tickets WHERE messageid={interaction.message.id} AND closed IS NULL')
					id = await cursor.fetchone()
				if id:
					await self.tickets_close.callback(self,interaction,id[0])
				else:
					embed = discord.Embed(description=f'Тикет уже был закрыт, либо не существует',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
			elif customid == 'ticket_accept':
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с тикетами',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT id FROM discord_tickets WHERE messageid={interaction.message.id} AND channelid IS NULL AND closed IS NULL')
					id = await cursor.fetchone()
				if id:
					await self.tickets_accept.callback(self,interaction,id[0])
				else:
					embed = discord.Embed(description=f'Тикет уже был принят, либо не существует',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
			elif customid == 'ticket_block':
				if not await self.check_manage_permissions(interaction.user):
					embed = discord.Embed(description=f'У вас недостаточно прав для взаимодействия с тикетами',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				async with self.bot.cursor() as cursor:
					await cursor.execute(f'SELECT discordid FROM discord_tickets WHERE messageid={interaction.message.id}')
					discordid = await cursor.fetchone()
				if discordid and (member:=interaction.guild.get_member(discordid[0])):
					await self.tickets_block.callback(self,interaction,member,24)
				else:
					embed = discord.Embed(description=f'Автор тикета покинул Discord сервер, либо тикета не существует',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)

	async def on_ticket_block_check(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute("DELETE FROM discord_tickets_blocks WHERE time<UNIX_TIMESTAMP()")

	async def check_create_permissions(self, member: discord.Member):
		roles = []
		guild = self.bot.guild()
		for application_command in await self.bot.tree.fetch_commands(guild=guild):
			if application_command.name == self.ticket.name:
				try:
					roles = [permission.id for permission in (await application_command.fetch_permissions(guild)).permissions if permission.permission]
				except:
					return True
				break
		if not bool(set(role.id for role in member.roles) & set(roles)):
			return False
		return True

	async def check_manage_permissions(self, member: discord.Member):
		roles = []
		guild = self.bot.guild()
		for application_command in await self.bot.tree.fetch_commands(guild=guild):
			if application_command.name == Tickets.tickets_group.name:
				try:
					roles = [permission.id for permission in (await application_command.fetch_permissions(guild)).permissions if permission.permission]
				except:
					return True
				break
		if not bool(set(role.id for role in member.roles) & set(roles)):
			return False
		return True
