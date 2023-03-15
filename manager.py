from discord import app_commands
import discord
import json
import re
class DiscordManager():
	def __init__(self,bot):
		self.bot = bot
		
		command_init = self.bot.language.commands['message_sendraw']['init']
		@command_init.command(**self.bot.language.commands['message_sendraw']['initargs'])
		@app_commands.choices(**self.bot.language.commands['message_sendraw']['choices'])
		@app_commands.describe(**self.bot.language.commands['message_sendraw']['describe'])
		@app_commands.rename(**self.bot.language.commands['message_sendraw']['rename'])
		async def command_message_rawsend(interaction: discord.Interaction, content: str):
			try:
				content, reference, embeds, components = DiscordManager.json_to_message(content)
				message = await interaction.channel.send(content=content, reference=reference, embeds = embeds, view=components)
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_sendraw']['messages']['message-sended'])
			except:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_sendraw']['messages']['parse-error'])
			await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
		
		command_init = self.bot.language.commands['message_raw']['init']
		@command_init.command(**self.bot.language.commands['message_raw']['initargs'])
		@app_commands.describe(**self.bot.language.commands['message_raw']['describe'])
		@app_commands.rename(**self.bot.language.commands['message_raw']['rename'])
		async def command_message_raw(interaction: discord.Interaction,id: str):
			if not re.match('[0-9]*',id) is not None:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_raw']['messages']['incorrect-id-error'])
				await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_raw']['messages']['message-not-found'])
				await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
				return
			embed = discord.Embed(description = f'```json\n{DiscordManager.message_to_json(message)}```',colour = discord.Colour.green())	
			await interaction.response.send_message(embed=embed,ephemeral=True)
		@self.bot.tree.context_menu(name = self.bot.language.commands['message_raw']['messages']['context'], guild = self.bot.guild_object())
		async def context_message_raw(interaction: discord.Interaction, message: discord.Message):
			await command_message_raw.callback(interaction,str(message.id))
	@staticmethod
	def message_to_json(message):
		msg = {}
		if message.content:
			msg['content'] = message.content
		if message.reference:
			msg['reference'] = {'message_id':message.reference.message_id}
		if message.embeds:
			msg['embeds'] = [embed.to_dict() for embed in message.embeds]
		if message.components:
			components = []
			for component in message.components:
				if isinstance(component , discord.Button):
					components.append({
							'custom_id':component.custom_id,
							'url': component.url,
							'label': component.label,
							'type': int(component.type),
							'style': int(component.style)
						})
				elif isinstance(component, discord.SelectMenu):
					options = [{'label': option.label,'value': option.value,'description': option.description} for option in component.options]
					components.append({
							'custom_id':component.custom_id,
							'placeholder': component.placeholder,
							'min_values': component.min_values,
							'max_values': component.max_values,
							'type': int(component.type),
							'options': options
						})
				elif isinstance(component, discord.ActionRow):
					childrens = []
					for children in component.children:
						if isinstance(children , discord.Button):
							childrens.append({
									'custom_id':children.custom_id,
									'url': children.url,
									'label': children.label,
									'type': int(children.type),
									'style': int(children.style)
								})
						elif isinstance(children, discord.SelectMenu):
							options = [{'label': option.label,'value': option.value,'description': option.description} for option in children.options]
							childrens.append({
									'custom_id':children.custom_id,
									'placeholder': children.placeholder,
									'min_values': children.min_values,
									'max_values': children.max_values,
									'type': int(children.type),
									'options': options
								})
					components.append({'type': int(component.type),'children': childrens})
			msg['components'] = components
		return json.dumps(msg,indent=1,ensure_ascii=False)	
	@staticmethod
	def json_to_message(message: str):
		content, reference, embeds, view = None, None, [], None
		try:
			msg = json.loads(message)
			if 'content' in msg:
				content = msg['content']
			if 'reference' in msg:
				reference = msg['reference']
			if 'embeds' in msg:
				embeds = [discord.Embed.from_dict(embed) for embed in msg['embeds']]
			if 'components' in msg:
				view = discord.ui.View(timeout=None)
				for component in msg['components']:
					if component['type'] == 2:
						view.add_item(discord.ui.Button(disabled=False,url=component['url'],custom_id=component['custom_id'],label=component['label'],style=discord.ButtonStyle(component['style'])))
					elif component['type'] == 4:
						options = [discord.SelectOption(label=option['title'],value=option['value'],description=option['description']) for option in component['options']]
						view.add_item(discord.ui.Select(custom_id=component['custom_id'],placeholder=component['placeholder'],min_values=component['min_values'],max_values=component['max_values'],options=options))
					elif component['type'] == 1:
						for children in component['children']:
							if children['type'] == 2:
								view.add_item(discord.ui.Button(disabled=False,url=children['url'],custom_id=children['custom_id'],label=children['label'],style=discord.ButtonStyle(children['style'])))
							elif children['type'] == 4:
								options = [discord.SelectOption(label=option['title'],value=option['value'],description=option['description']) for option in children['options']]
								view.add_item(discord.ui.Select(custom_id=children['custom_id'],placeholder=children['placeholder'],min_values=children['min_values'],max_values=children['max_values'],options=options))


		except:
			pass
		return content, reference, embeds, view
