import discord,re
from discord import app_commands
from utils import json_to_message, message_to_json
from discord.ext import commands

class Manager(commands.Cog):
	def __init__(self,bot,guild_object):
		self.bot = bot
		self.bot.tree.add_command(app_commands.ContextMenu(name='Получить JSON',callback=self.context_messages_view),guild=guild_object)

	messages_group = app_commands.Group(name='messages', description='Менеджер сообщений')
	
	@messages_group.command(name='send', description='отправить сообщение из JSON')
	@app_commands.describe(json='сообщение в формате JSON')
	@app_commands.checks.has_permissions(manage_messages=True)
	async def messages_send(self,interaction: discord.Interaction, json: str):
		try:
			content, reference, embeds, components = json_to_message(json)
			message = await interaction.channel.send(content=content, reference=reference, embeds = embeds, view=components)
			embed = discord.Embed(description='Сообщение отправлено', color=discord.Colour.green())
		except:
			embed = discord.Embed(description='Ошибка в обработке JSON, проверьте правильность вашего сообщения', color=discord.Colour.red())
		await interaction.response.send_message(embeds=embed,ephemeral=True)
	
	@messages_group.command(name='view', description='получить JSON сообщения')
	@app_commands.rename(id='id_сообщения')
	async def messages_view(self, interaction: discord.Interaction,id: str):
		if not re.match('[0-9]*',id) is not None:
			embed = discord.Embed(description='Неверный ID сообщения', color=discord.Colour.red())
			await interaction.response.send_message(embed=embed,ephemeral=True)
			return
		id = int(id)
		message = await interaction.channel.fetch_message(id)
		if not message:
			embed = discord.Embed(description='Сообщение с данным ID не найдено в канале', color=discord.Colour.red())
			await interaction.response.send_message(embed=embed,ephemeral=True)
			return
		embed = discord.Embed(description = f'```json\n{message_to_json(message)}```',colour = discord.Colour.green())	
		await interaction.response.send_message(embed=embed,ephemeral=True)
	
	@messages_group.command(name='purge', description='очистить сообщения')
	@app_commands.rename(limit='количество')
	@app_commands.checks.has_permissions(manage_messages=True)
	async def messages_purge(self, interaction: discord.Interaction, limit: int, author: discord.Member = None):
		await interaction.response.defer(ephemeral=True)
		limit = abs(limit)
		limit = 100 if limit > 100 else limit
		async for message in interaction.channel.history(limit=limit):
			if not author:
				await message.delete()
				continue
			if message.author == author:
				await message.delete()
		embed = discord.Embed(description='Сообщения очищены',color=discord.Colour.green())
		await interaction.followup.send(embed=embed,ephemeral=True)

	async def context_messages_view(self, interaction: discord.Interaction, message: discord.Message):
		await self.messages_view.callback(self,interaction,str(message.id))
	
