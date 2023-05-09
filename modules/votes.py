import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime

class Votes(commands.Cog):
	def __init__(self, bot, vote_roles: [int,...],check_every_seconds: int):
		self.bot = bot
		self.vote_roles = vote_roles
		self.check_every_seconds = check_every_seconds
		self.vote_check = tasks.loop(seconds=self.check_every_seconds)(self.vote_check)

	@commands.Cog.listener()
	async def on_ready(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_votes (id BIGINT NOT NULL,channelid BIGINT NOT NULL, start INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), end INT(11) NOT NULL,placeholder CHAR(150), CONSTRAINT id PRIMARY KEY(id))")
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_votes_values (id BIGINT NOT NULL, value INT NOT NULL, label CHAR(100) NOT NULL, description CHAR(100), FOREIGN KEY(id) REFERENCES discord_votes(id) ON DELETE CASCADE)")
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_votes_answers (id BIGINT NOT NULL, discordid BIGINT NOT NULL, value INT NOT NULL, FOREIGN KEY(id) REFERENCES discord_votes(id) ON DELETE CASCADE)")
		self.vote_check.start()
	
	def cog_unload(self):
		self.vote_check.cancel()		
		
	@app_commands.command(name='vote',description='создать голосование')
	@app_commands.rename(values='пункты',min='минимум',max='максимум',hours='длительность',placeholder='текст_заполнитель')
	@app_commands.describe(values='пункты голосования в формате [Текст пункта 1|пояснение][Текст пункта 2]',min='минимальное количество выбранных пунктов',max='максимальное количество выбранных пунктов',hours='сколько часов проводится голосование (поддерживает дробные значения)',placeholder='текст который будет внутри окна голосования изначально')
	async def vote(self,interaction: discord.Interaction,values: str, min: int = 1, max: int = 1, hours: float = 0.5, placeholder: str = None):
		values = values.replace("\\","/")
		if placeholder and len(placeholder) > 150:
			embed = discord.Embed(description='Максимальная длина текста-заполнителя: **150 символов**',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		min = 1 if min < 1 else min
		max = 1 if max < 1 else max
			
		length = len(values)
		if length < 3:
			embed = discord.Embed(description='Ошибка в пунктах, значение не может быть менее **3 символов**',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		duration = round(hours*3600)
		crop = values[1:length-1]
		crop = crop.split("][")
		length = len(crop)
		if length > 25:
			embed = discord.Embed(description='Максимальное количество пунктов: **25**',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return
		min = length if length < min else min
		max = length if length < max else max

		values = []
		
		i = 0
		for value in crop:
			value = value.split("|")
			length = len(value)
			if length > 2:
				embed = discord.Embed(description='В одном из пунктов указано три значения, допустимое количество: **2**',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			if length < 1:
				embed = discord.Embed(description='В одном из пунктов не указано значений',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			if len(value[0]) > 100:
				value = value[0]
				embed = discord.Embed(description=f'В пункте `{value}` превышен лимит символов: **100**',color=discord.Colour.red())
				await interaction.response.send_message(embed=embed, ephemeral=True)
				return
			if length < 2:	
				values.append({'label':value[0],'value':i,'description':None})
			else:
				if len(value[1]) > 100:
					value = value[1]
					embed = discord.Embed(description='В пункте `{value}` превышен лимит символов: **100**',color=discord.Colour.red())
					await interaction.response.send_message(embed=embed, ephemeral=True)
					return
				values.append({'label':value[0],'value':i,'description':value[1]})
			i+=1

		start_time = int(datetime.now().timestamp())
		end_time = start_time+duration

		embed = discord.Embed(description=f'Голосование закончится <t:{end_time}:R>',color=discord.Colour.green())
		view = discord.ui.View(timeout=None)
		options = [discord.SelectOption(label=value['label'],value=value['value'],description=value['description']) for value in values]
		view.add_item(discord.ui.Select(custom_id="vote",disabled=False, min_values=min, max_values=max, placeholder=placeholder, options=options))
		message = await interaction.channel.send(embed=embed,view=view)

		request = []
		for value in values:
			label,description,value = value['label'], value['description'], value['value']
			if description:
				request.append(f'(\'{message.id}\',\'{value}\',\'{label}\',\'{description}\')')
			else:
				request.append(f'(\'{message.id}\',\'{value}\',\'{label}\',null)')

		request = ','.join(request)
		async with self.bot.cursor() as cursor:
			if placeholder:
				await cursor.execute(f'INSERT INTO discord_votes (id,channelid,end,placeholder) VALUES({message.id},{interaction.channel_id},{end_time},%s)',(placeholder,))
			else:
				await cursor.execute(f'INSERT INTO discord_votes (id,channelid,end) VALUES({message.id},{interaction.channel_id},{end_time})')
			await cursor.execute(f'INSERT INTO discord_votes_values VALUES {request}')	

		embed = discord.Embed(description='Голосование создано',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed,ephemeral=True)
	
	@commands.Cog.listener()
	async def on_interaction(self,interaction: discord.Interaction):
		if interaction.type != discord.InteractionType.component or interaction.data['custom_id'] != "vote":
			return
		if not bool(set(self.vote_roles) & set([role.id for role in interaction.user.roles])):
			embed = discord.Embed(description='У вас недостаточно прав для участия в голосовании',color=discord.Colour.red())
			await interaction.response.send_message(embed=embed, ephemeral=True)
			return

		request = []
		id = interaction.message.id
		for value in interaction.data['values']:
			request.append(f'({id},{interaction.user.id},{value})')
		request = ','.join(request)
		
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id FROM discord_votes WHERE id=\'{id}\'')
			if not await cursor.fetchone():
				embed = discord.Embed(description='Голосование, в котором вы участвуете уже не существует',color=discord.Colour.red())
				await interaction.message.delete()
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			await cursor.execute(f'DELETE FROM discord_votes_answers WHERE discordid={interaction.user.id} AND id={id}')
			await cursor.execute(f'INSERT INTO discord_votes_answers VALUES {request}')

		embed = discord.Embed(description='Ваш голос записан. Вы сможете изменить его до конца голосования.',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed, ephemeral=True)

	async def vote_check(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT id,channelid,start,end,placeholder FROM discord_votes WHERE end<UNIX_TIMESTAMP()')
			votes = await cursor.fetchall()
			if votes:
				for id, channelid, start_time, end_time, placeholder in votes:
					message = await self.bot.guild().get_channel(channelid).fetch_message(id)
					if message:
						
						values = []
						labels = []
						descriptions = []

						await cursor.execute(f'SELECT value,label,description FROM discord_votes_values WHERE id={id}')
						for value, label, description in await cursor.fetchall():
							labels.insert(value,label)
							values.insert(value,0)
							if description:
								descriptions.insert(value,description)
							else:
								descriptions.insert(value,None)

						await cursor.execute(f'SELECT value FROM discord_votes_answers WHERE id={id}')
						answers = cursor.fetchall()
						if answers:
							for value in answers:
								values[value[0]]+=1

						embed = discord.Embed(title='Результаты голосования',description=f'Начато в <t:{start_time}:f>\nЗавершено в <t:{end_time}:f>', color=discord.Colour.green())
						for i in range(len(labels)):
							label, description,amount = labels[i],descriptions[i],values[i]
							if description:
								embed.add_field(name=f'{label} ({description})',value=f'Количество голосов: {amount}')
							else:
								embed.add_field(name=f'{label}',value=f'Количество голосов: {amount}')
						await message.edit(embed=embed,view=None)

				await cursor.execute(f'DELETE FROM discord_votes WHERE end<UNIX_TIMESTAMP()')
	
