  message_send:
    group: 'message'
    name: 'send'
    description: 'отправить сообщение в этот канал'
    arguments:
      content:
        rename: 'текст_сообщения'
      reference:
        describe: 'ID сообщения в этом канале на которое нужно ответить'
    messages:
      message-sended: '{"embeds": [{"description": "Сообщение отправлено","color": 65280}]}'
  message_edit:
    group: 'message'
    name: 'edit'
    description: 'изменить текст сообщения бота'
    arguments:
      id:
        describe: 'ID сообщения в данном канале'
        rename: 'id_сообщения'
      content:
        describe: 'новый текст для сообщения, оставьте пустым чтобы удалить'
    messages:
      incorrect-id-error: '{"embeds": [{"description": "Неверный формат ID сообщения. ID должно быть целочисленным положительным числом","color": 16711680}]}'
      message-not-found: '{"embeds": [{"description": "Указанное сообщение не найдено в данном канале","color": 16711680}]}'
      empty-message-error: '{"embeds": [{"description": "Нельзя изменить сообщение отправленное не этим ботом","color": 16711680}]}'
      author-isnt-bot-error: '{"embeds": [{"description": "Сообщение не может быть пустым, если не указан Embed или Component","color": 16711680}]}'
      # ${message_link} - ссылка на измененное сообщение
      message-edited: '{"embeds": [{"description": "[Сообщение](${message_link}) изменено","color": 65280}]}'


		command_init = self.bot.language.commands['message_send']['init']
		@command_init.command(**self.bot.language.commands['message_send']['initargs'])
		@app_commands.choices(**self.bot.language.commands['message_send']['choices'])
		@app_commands.describe(**self.bot.language.commands['message_send']['describe'])
		@app_commands.rename(**self.bot.language.commands['message_send']['rename'])
		async def command_message_send(interaction: discord.Interaction, content: str, reference: str=None):
			if reference and re.match('[0-9]*',reference) is not None:
				reference = discord.MessageReference(message_id=int(reference), channel_id=interaction.channel.id)	
			message = await interaction.channel.send(content=content, reference=reference)
			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_send']['messages']['message-sended'])
			await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)

		command_init = self.bot.language.commands['message_edit']['init']
		@command_init.command(**self.bot.language.commands['message_edit']['initargs'])
		@app_commands.choices(**self.bot.language.commands['message_edit']['choices'])
		@app_commands.describe(**self.bot.language.commands['message_edit']['describe'])
		@app_commands.rename(**self.bot.language.commands['message_edit']['rename'])
		async def command_message_edit(interaction: discord.Interaction,id: str, content: str=None):
			if not re.match('[0-9]*',id) is not None:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_edit']['messages']['incorrect-id-error'])
				await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_edit']['messages']['message-not-found'])
				await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
				return
			if message.author != self.bot.user:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_edit']['messages']['author-isnt-bot-error'])
				await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
				return
			if not (message.embed or message.components) and not content:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['message_edit']['messages']['empty-message-error'])
				await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
				return
			await message.edit(content=content)
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['message_edit']['messages']['message-edited']).safe_substitute(message_link=f'https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}'))
			await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
		
		self.bot.tree.add_command(self.message_group, guild = self.bot.guild_object())

		self.embed_group = app_commands.Group(name="embed", description="Менеджмент Embed")

		@self.embed_group.command(name="send", description="Отравить Embed сообщение в этот канал")
		async def command_embed_send(interaction: discord.Interaction, title: str = None, description: str = None, footer: str = None,thumbnail: str = None, image: str = None, red: int = 255, green: int = 255, blue: int = 255, footer_icon: str = None,author_name: str = None, author_url: str = None, author_icon: str = None):
			try:
				embed = discord.Embed(title = title,description = description,colour = discord.Colour.from_rgb(red, green, blue))
				if author_name:
					embed.set_author(name=author_name,url=author_url,icon_url=author_icon)
				embed.set_thumbnail(url=thumbnail)
				embed.set_image(url=image)
				embed.set_footer(text=footer,icon_url=footer_icon)
				message = await interaction.channel.send(embed=embed)
				embed = discord.Embed(description = f'Сообщение с Embed отправлено',colour = discord.Colour.green())
			except:
				embed = discord.Embed(description = f'Неверные параметры Embed\'а',colour = discord.Colour.red())	
			await interaction.response.send_message(embed=embed,ephemeral=True)

		@self.embed_group.command(name="append", description="Добавить к сообщению Embed")
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		async def command_embed_append(interaction: discord.Interaction,id: str, title: str = None, description: str = None, footer: str = None,thumbnail: str = None, image: str = None, red: int = 255, green: int = 255, blue: int = 255, footer_icon: str = None, author_name: str = None, author_url: str = None, author_icon: str = None):
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			try:
				embed = embed = discord.Embed(title = title,description = description,colour = discord.Colour.from_rgb(red, green, blue))
				if author_name:
					embed.set_author(name=author_name,url=author_url,icon_url=author_icon)
				embed.set_thumbnail(url=thumbnail)
				embed.set_image(url=image)
				embed.set_footer(text=footer,icon_url=footer_icon)
				if message.embeds:
					embeds = message.embeds
					embeds.append(embed)
					await message.edit(embeds=embeds)
				else:
					await message.edit(embed=embed)
				embed = discord.Embed(description = f'В сообщение добавлен Embed',colour = discord.Colour.green())
			except:
				embed = discord.Embed(description = f'Неверные параметры Embed\'а',colour = discord.Colour.red())
			
			await interaction.response.send_message(embed=embed,ephemeral=True)
		
		@self.embed_group.command(name="remove", description="Удалить Embed из сообщения")
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		@app_commands.describe(embed='Номер удаляемого Embed\'a, если не указано - удалит последний в сообщении')
		@app_commands.rename(embed='номер_embed')
		async def command_embed_remove(interaction: discord.Interaction, id: str, embed: int = None):
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if not message.embeds:
				embed = discord.Embed(description = f'Embed\'ы отсутствуют в указанном сообщении',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			embeds = message.embeds
			embed = embed-1 if embed else embed
			embed = len(embeds)-1 if not embed or embed>len(embeds) else embed
			embed = 0 if embed<0 else embed
			del embeds[embed]
			if not (message.content or embeds or message.components):
				embed = discord.Embed(description = f'Сообщение не может быть пустым, если не указан Component или Content',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			await message.edit(embeds=embeds)
			embed = discord.Embed(description = f'[Сообщение](https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}) изменено',colour = discord.Colour.green())
			await interaction.response.send_message(embed=embed,ephemeral=True)

		@self.embed_group.command(name="edit", description="Изменить Embed в сообщении")
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		@app_commands.describe(embed='Номер изменяемого Embed\'a, если не указано - изменит последний в сообщении')
		@app_commands.rename(embed='номер_embed')
		async def command_embed_edit(interaction: discord.Interaction, id: str, embed: int = None, title: str = None, description: str = None, footer: str = None,thumbnail: str = None, image: str = None, red: int = 255, green: int = 255, blue: int = 255, footer_icon: str = None, author_name: str = None, author_url: str = None, author_icon: str = None):
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if not message.embeds:
				embed = discord.Embed(description = f'Embed\'ы отсутствуют в указанном сообщении',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			embeds = message.embeds
			embed = embed-1 if embed else embed
			embed = len(embeds)-1 if not embed or embed>len(embeds) else embed
			embed = 0 if embed<0 else embed
			try:
				embeds[embed].title = title
				embeds[embed].description = description
				if author_name:
					embeds[embed].set_author(name=author_name,url=author_url,icon_url=author_icon)
				else:
					embeds[embed].remove_author()
				embeds[embed].set_thumbnail(url=thumbnail)
				embeds[embed].set_image(url=image)
				if footer:
					embeds[embed].set_footer(text=footer,icon_url=footer_icon)
				else:
					embeds[embed].remove_footer()
				await message.edit(embeds=embeds)
				embed = discord.Embed(description = f'[Сообщение](https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}) изменено',colour = discord.Colour.green())
			except:
				embed = discord.Embed(description = f'Неверные параметры Embed\'а',colour = discord.Colour.red())
			await interaction.response.send_message(embed=embed,ephemeral=True)

		self.bot.tree.add_command(self.embed_group, guild = self.bot.guild_object())

		self.field_group = app_commands.Group(name="field", description="Менеджмент Field")

		@self.field_group.command(name="append", description="Добавить Field к Embed")
		@app_commands.choices(inline=[app_commands.Choice(name="нет", value=0),app_commands.Choice(name="да", value=1)])
		@app_commands.describe(embed='Номер Embed\'a к которому будет добавлен Field, если не указано - добавит к последнему в сообщении')
		@app_commands.rename(embed='номер_embed')
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		async def command_field_append(interaction: discord.Interaction, id: str, name: str, value: str, embed: int = None, inline: app_commands.Choice[int] = None):
			inline = inline.value == 1 if inline else False
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if not message.embeds:
				embed = discord.Embed(description = f'Embed\'ы отсутствуют в указанном сообщении',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			embeds = message.embeds
			embed= embed-1 if embed else embed
			embed = len(embeds)-1 if not embed or embed>len(embeds) else embed
			embed = 0 if embed<0 else embed
			embeds[embed].add_field(name=name,value=value, inline=inline)
			await message.edit(embeds=embeds)
			embed = discord.Embed(description = f'[Сообщение](https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}) изменено',colour = discord.Colour.green())
			await interaction.response.send_message(embed=embed,ephemeral=True)

		@self.field_group.command(name="remove", description="Удалить Field из Embed в сообщении")
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		@app_commands.describe(embed='Номер Embed\'a из которого будет удален Field, если не указано - удалит из последнего в сообщении')
		@app_commands.rename(embed='номер_embed')
		@app_commands.describe(field='Номер Field\'a который будет удален из Embed, если не указано - удалит последний в Embed')
		@app_commands.rename(field='номер_field')
		async def command_field_remove(interaction: discord.Interaction, id: str, embed: int = None, field: int = None):
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if not message.embeds:
				embed = discord.Embed(description = f'Embed\'ы отсутствуют в указанном сообщении',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			embeds = message.embeds
			embed= embed-1 if embed else embed
			embed = len(embeds)-1 if not embed or embed>len(embeds) else embed
			embed = 0 if embed<0 else embed
			if not embeds[embed].fields:
				embed = discord.Embed(description = f'Field\'ы отсутствуют в указанном Embed',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			fields = embeds[embed].fields
			field = field-1 if field else field
			field = len(fields)-1 if not field or field>len(fields) else field
			field = 0 if field<0 else field
			embeds[embed].remove_filed(field)
			await message.edit(embeds=embeds)
			embed = discord.Embed(description = f'[Сообщение](https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}) изменено',colour = discord.Colour.green())	
			await interaction.response.send_message(embed=embed,ephemeral=True)

		@self.field_group.command(name="edit", description="Изменить Field в Embed в сообщении")
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		@app_commands.describe(embed='Номер Embed\'a из которого будет удален Field, если не указано - удалит из последнего в сообщении')
		@app_commands.rename(embed='номер_embed')
		@app_commands.describe(field='Номер Field\'a который будет удален из Embed, если не указано - удалит последний в Embed')
		@app_commands.rename(field='номер_field')
		@app_commands.choices(inline=[app_commands.Choice(name="нет", value=0),app_commands.Choice(name="да", value=1)])
		async def command_field_edit(interaction: discord.Interaction, id: str, name: str, value: str, embed: int = None, field: int = None,inline: app_commands.Choice[int] = None):
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if not message.embeds:
				embed = discord.Embed(description = f'Embed\'ы отсутствуют в указанном сообщении',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			embeds = message.embeds
			embed= embed-1 if embed else embed
			embed = len(embeds)-1 if not embed or embed>len(embeds) else embed
			embed = 0 if embed<0 else embed
			if not embeds[embed].fields:
				embed = discord.Embed(description = f'Field\'ы отсутствуют в указанном Embed',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			fields = embeds[embed].fields
			field = field-1 if field else field
			field = len(fields)-1 if not field or field>len(fields) else field
			field = 0 if field<0 else field
			embeds[embed].remove_filed(field)
			embeds[embed].insert_field_at(index=field,name=name,value=value, inline=inline)
			await message.edit(embeds=embeds)
			embed = discord.Embed(description = f'[Сообщение](https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}) изменено',colour = discord.Colour.green())	
			await interaction.response.send_message(embed=embed,ephemeral=True)

		self.bot.tree.add_command(self.field_group, guild = self.bot.guild_object())
		
		self.button_group = app_commands.Group(name="button", description="Менеджмент Кнопок")

		@self.button_group.command(name="send", description="Отправить Кнопку в сообщении")
		@app_commands.choices(style=[app_commands.Choice(name="синяя", value=1),app_commands.Choice(name="серая", value=2),app_commands.Choice(name="зеленая", value=3),app_commands.Choice(name="красная", value=4)])
		async def command_button_send(interaction: discord.Interaction, custom_id:str = None,url: str = None, label:str = None, style: app_commands.Choice[int] = None):
			style = discord.ButtonStyle(style.value) if style else discord.ButtonStyle(2)
			try:
				view = discord.ui.View(timeout=None)
				view.add_item(discord.ui.Button(disabled=False,style=style,url=url,label=label,custom_id=custom_id))
				await interaction.channel.send(view=view)
				embed = discord.Embed(description = f'Сообщение отправлено',colour = discord.Colour.green())
			except:
				embed = discord.Embed(description = f'Неверные параметры кнопки',colour = discord.Colour.red())
			await interaction.response.send_message(embed=embed,ephemeral=True)

		@self.button_group.command(name="append", description="Добавить Кнопку к сообщению")
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		@app_commands.choices(style=[app_commands.Choice(name="синяя", value=1),app_commands.Choice(name="серая", value=2),app_commands.Choice(name="зеленая", value=3),app_commands.Choice(name="красная", value=4)])
		async def command_button_append(interaction: discord.Interaction, id: str,custom_id:str = None,url: str = None, label:str = None, style: app_commands.Choice[int] = None):
			style = discord.ButtonStyle(style.value) if style else discord.ButtonStyle(2)
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			try:
				view = discord.ui.View.from_message(message,timeout=None)
				view.add_item(discord.ui.Button(disabled=False,style=style,url=url,label=label,custom_id=custom_id))
				await message.edit(view=view)
				embed = discord.Embed(description = f'[Сообщение](https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}) изменено',colour = discord.Colour.green())
			except:
				embed = discord.Embed(description = f'Неверные параметры кнопки',colour = discord.Colour.red())
			await interaction.response.send_message(embed=embed,ephemeral=True)

		@self.button_group.command(name="edit", description="Изменить Кнопку из сообщения")
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		@app_commands.describe(button='Номер Кнопки которая будет изменена, если не указано - изменит последнюю из сообщения')
		@app_commands.rename(button='номер_кнопки')
		@app_commands.choices(style=[app_commands.Choice(name="синяя", value=1),app_commands.Choice(name="серая", value=2),app_commands.Choice(name="зеленая", value=3),app_commands.Choice(name="красная", value=4)])
		async def command_button_edit(interaction: discord.Interaction, id: str, button: int = None,custom_id:str = None,url: str = None, label:str = None, style: app_commands.Choice[int] = None):
			style = discord.ButtonStyle(style.value) if style else discord.ButtonStyle(2)
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if not message.components:
				embed = discord.Embed(description = f'Компоненты отсутствуют в указанном сообщении',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			try:
				oldview = discord.ui.View.from_message(message,timeout=None)
				buttons = oldview.children
				button = button-1 if button else button
				button = len(buttons)-1 if not button or button>len(buttons) else button
				button = 0 if button<0 else button
				view = discord.ui.View(timeout=None)
				for i in range(len(buttons)):
					if i == button:
						view.add_item(discord.ui.Button(disabled=False,style=style,url=url,label=label,custom_id=custom_id))
					else:
						view.add_item(buttons[i])
				await message.edit(view=view)
				embed = discord.Embed(description = f'[Сообщение](https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}) изменено',colour = discord.Colour.green())
			except:
				embed = discord.Embed(description = f'Неверные параметры кнопки',colour = discord.Colour.red())
			await interaction.response.send_message(embed=embed,ephemeral=True)		

		@self.button_group.command(name="remove", description="Удалить Кнопку из сообщения")
		@app_commands.describe(id='ID сообщения в данном канале')
		@app_commands.rename(id='id_сообщения')
		@app_commands.describe(button='Номер Кнопки которая будет удалена, если не указано - удалит последнюю из сообщения')
		@app_commands.rename(button='номер_кнопки')
		async def command_button_remove(interaction: discord.Interaction, id: str, button: int = None):
			if not re.match('[0-9]*',id) is not None:
				embed = discord.Embed(description = f'Неверный формат ID сообщения. ID должно быть целочисленным положительным числом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			id = int(id)
			message = await interaction.channel.fetch_message(id)
			if not message:
				embed = discord.Embed(description = f'Указанное сообщение не найдено в данном канале',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			if message.author != self.bot.user:
				embed = discord.Embed(description = f'Нельзя изменить сообщение отправленное не этим ботом',colour = discord.Colour.red())
				await interaction.response.send_message(embed=embed,ephemeral=True)
				return
			try:
				view = discord.ui.View.from_message(message,timeout=None)
				buttons = view.children
				button = button-1 if button else button
				button = len(buttons)-1 if not button or button>len(buttons) else button
				button = 0 if button<0 else button
				if not (message.content or message.embeds or len(buttons)>1):
					embed = discord.Embed(description = f'Сообщение не может быть пустым, если не указан Content или Embed',colour = discord.Colour.red())
					await interaction.response.send_message(embed=embed,ephemeral=True)
					return
				view.remove_item(buttons[button])
				await message.edit(view=view)
				embed = discord.Embed(description = f'[Сообщение](https://discord.com/channels/{self.bot.guild_id}/{interaction.channel.id}/{message.id}) изменено',colour = discord.Colour.green())
			except:
				embed = discord.Embed(description = f'Неверные параметры кнопки',colour = discord.Colour.red())
			await interaction.response.send_message(embed=embed,ephemeral=True)		

		self.bot.tree.add_command(self.button_group, guild = self.bot.guild_object())

		
	
