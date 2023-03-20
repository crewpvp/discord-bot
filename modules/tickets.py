from discord import app_commands
import discord
from datetime import datetime
from modules.utils import relativeTimeParser
from manager import DiscordManager
from string import Template
from io import BytesIO
from language import DiscordLanguage
class DiscordTickets:
	def __init__(self, bot,channel: int, category: int,check_every_seconds: int, answer_roles: [int,...] = [], max_opened_per_user: int = 5):
		self.bot = bot
		self.answer_roles = answer_roles
		self.max_opened_per_user = max_opened_per_user
		self.category = category
		self.channel = channel
		self.check_every_seconds = check_every_seconds
		
		with self.bot.cursor() as cursor:
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_tickets (id INT NOT NULL AUTO_INCREMENT, discordid BIGINT NOT NULL, time INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(),messageid BIGINT, channelid BIGINT, receiver BIGINT, closer BIGINT, receiver_time INT(11), closed INT(11), PRIMARY KEY(id))")
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_tickets_blocks (discordid BIGINT NOT NULL, time INT(11) NOT NULL, PRIMARY KEY(discordid))")

		@DiscordLanguage.command
		async def ticket_button(interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
			label = label[:80] if label else self.bot.language.commands['ticket_button']['messages']['default-button-text']
			color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_create",label=label,style=color))
			await interaction.channel.send(view=view)
			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_button']['messages']['button-created'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
		
		@DiscordLanguage.command
		async def ticket_active(interaction: discord.Interaction):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id, messageid, channelid FROM discord_tickets WHERE closed IS NULL ORDER BY id')
				tickets = cursor.fetchall()
			if tickets:
				text = []
				for id, messageid, channelid in tickets:
					message_link = f'https://discord.com/channels/{self.bot.guild_id}/{self.channel}/{messageid}'
					if channelid:
						channel_link = f'https://discord.com/channels/{self.bot.guild_id}/{channelid}'
						text.append(Template(self.bot.language.commands['ticket_active']['messages']['opened-ticket-format']).safe_substitute(id=id,channel_link=channel_link,message_link=message_link))
					else:
						text.append(Template(self.bot.language.commands['ticket_active']['messages']['opened-ticket-format']).safe_substitute(id=id,message_link=message_link))
				text = (self.bot.language.commands['ticket_active']['messages']['join-by']).join(text)
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['ticket_active']['messages']['active-tickets']).safe_substitute(tickets=text))
			else:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_active']['messages']['no-active-tickets'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def ticket_pardon(interaction: discord.Interaction, member: discord.Member):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT discordid FROM discord_tickets_blocks WHERE discordid={member.id}')
				if cursor.fetchone():
					cursor.execute(f'DELETE FROM discord_tickets_blocks WHERE discordid={member.id}')
					content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['ticket_pardon']['messages']['user-pardonned']).safe_substitute(user=member.mention))
				else:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_pardon']['messages']['user-not-banned'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
		
		@DiscordLanguage.command
		async def ticket_create(interaction: discord.Interaction, text: str):
			cursor = self.bot.cursor()
			cursor.execute(f'SELECT COUNT(*) FROM discord_tickets WHERE discordid={interaction.user.id} AND (closed IS NULL)')
			count = cursor.fetchone()[0]
			cursor.execute(f'SELECT time FROM discord_tickets_blocks WHERE discordid={interaction.user.id} AND time>UNIX_TIMESTAMP()')
			time = cursor.fetchone()
			if time:
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['ticket_create']['messages']['ticket-banned-error']).safe_substitute(time=time[0]))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
			elif count >= self.max_opened_per_user:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_create']['messages']['ticket-limit-error'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
			else:
				cursor.execute('SELECT MAX(id) FROM discord_tickets')
				values = cursor.fetchone()
				id = values[0]+1 if values[0] else 1
				text = text[:1500] if len(text) > 1500 else text
				view = discord.ui.View(timeout=None)
				label = self.bot.language.commands['ticket_create']['messages']['accept-button-label']
				color = discord.ButtonStyle(self.bot.language.commands['ticket_create']['messages']['accept-button-color'])
				view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_accept",label=label,style=color))
				label = self.bot.language.commands['ticket_create']['messages']['decline-button-label']
				color = discord.ButtonStyle(self.bot.language.commands['ticket_create']['messages']['decline-button-color'])
				view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_close",label=label,style=color))
				label = self.bot.language.commands['ticket_create']['messages']['block-button-label']
				color = discord.ButtonStyle(self.bot.language.commands['ticket_create']['messages']['block-button-color'])
				view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_block",label=label,style=color))

				embed_title = Template(self.bot.language.commands['ticket_create']['messages']['ticket-embed-title-format']).safe_substitute(id=id,text=text,user=interaction.user.mention)
				embed_description = Template(self.bot.language.commands['ticket_create']['messages']['ticket-embed-description-format']).safe_substitute(id=id,text=text,user=interaction.user.mention)
				content = Template(self.bot.language.commands['ticket_create']['messages']['ticket-content-format']).safe_substitute(id=id,text=text,user=interaction.user.mention)
				embed = discord.Embed(title = embed_title,description = embed_description,colour = discord.Colour.from_rgb(255,255,255))
				message = await interaction.guild.get_channel(self.channel).send(content=content, embed=embed, view=view)
				cursor.execute(f'INSERT INTO discord_tickets (discordid,messageid) VALUES ({interaction.user.id},{message.id})')
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_create']['messages']['ticket-created'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
			cursor.close()

		async def interaction(interaction: discord.Interaction):
			if interaction.type == discord.InteractionType.modal_submit and interaction.data['custom_id'] == "ticket_create":
				if not await self.check_permissions(interaction.user):
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_create']['messages']['no-ticket-permission'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				text = interaction.data['components'][0]['components'][0]['value']
				await command_ticket_create.callback(interaction,text)
			elif interaction.type == discord.InteractionType.component:
				customid = interaction.data['custom_id']
				if customid == "ticket_create":
					if not await self.check_permissions(interaction.user):
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_create']['messages']['no-ticket-permission'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor = self.bot.cursor()
					cursor.execute(f'SELECT COUNT(*) FROM discord_tickets WHERE discordid={interaction.user.id} AND (closed IS NULL)')
					count = cursor.fetchone()[0]
					cursor.execute(f'SELECT time FROM discord_tickets_blocks WHERE discordid={interaction.user.id} AND time>UNIX_TIMESTAMP()')
					time = cursor.fetchone()
					if time:
						content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['ticket_create']['messages']['ticket-banned-error']).safe_substitute(time=time[0]))
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					elif count >= self.max_opened_per_user:
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_create']['messages']['ticket-limit-error'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					else:
						cursor.execute("SELECT ((SUM(receiver_time)-SUM(time))/COUNT(*)) FROM discord_tickets WHERE receiver IS NOT NULL")
						values = cursor.fetchone()
						time = relativeTimeParser(seconds=values[0],greater=True) if values[0] else None
						time = Template(self.bot.language.commands['ticket_create']['messages']['average-time-format']).safe_substitute(time=time) if time else ''
						form_title = Template(self.bot.language.commands['ticket_create']['messages']['form-title']).safe_substitute(time=time)
						form_label = Template(self.bot.language.commands['ticket_create']['messages']['form-label']).safe_substitute(time=time)
						form_placeholder = Template(self.bot.language.commands['ticket_create']['messages']['form-placeholder']).safe_substitute(time=time)
						modal = discord.ui.Modal(title=form_title, custom_id = "ticket_create")
						modal.add_item(discord.ui.TextInput(min_length=1,label=form_label,style=discord.TextStyle.paragraph, placeholder=form_placeholder))
						await interaction.response.send_modal(modal)
					cursor.close()
				elif customid == 'ticket_close':
					if not bool(set(role.id for role in interaction.user.roles) & set(self.answer_roles)):
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_create']['messages']['no-ticket-permission'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT channelid,id FROM discord_tickets WHERE messageid=\'{interaction.message.id}\'')
						values = cursor.fetchone()
						cursor.execute(f'UPDATE discord_tickets SET receiver_time=COALESCE(receiver_time, UNIX_TIMESTAMP()), channelid=NULL, receiver=COALESCE(receiver, \'{interaction.user.id}\'), closer=\'{interaction.user.id}\', closed=UNIX_TIMESTAMP() WHERE id={values[1]}')
					embed = interaction.message.embeds[0]
					time = int(datetime.now().timestamp())
					field_name = Template(self.bot.language.commands['ticket_create']['messages']['ticket-closed-field-name']).safe_substitute(time=time,user=interaction.user.mention)
					field_value = Template(self.bot.language.commands['ticket_create']['messages']['ticket-closed-field-value']).safe_substitute(time=time,user=interaction.user.mention)
					embed.add_field(name=field_name,value=field_value)
					await interaction.response.edit_message(view=None,embed=embed)

					if values and values[0]:
						if (channel:=interaction.guild.get_channel(values[0])):
							thread_name = self.bot.language.commands['ticket_create']['messages']['ticket-history-thread-name']
							thread = await interaction.message.create_thread(name=thread_name)
							authors = {}
							skip_first = True
							async for message in channel.history(limit=None,oldest_first=True):
								if skip_first:
									skip_first = False
									continue
								if message.content or message.embeds or message.attachments:
									files = [discord.File(BytesIO(await attachment.read(use_cached=False)),filename=attachment.filename) for attachment in message.attachments]
									if message.author.id not in authors:
										authors[message.author.id] = await interaction.message.channel.create_webhook(name=str(message.author),avatar=(await message.author.avatar.read() if message.author.avatar else None))
									await authors[message.author.id].send(wait=False,content=message.content,embeds=message.embeds,files=files,thread=thread)
							await thread.edit(archived=True, locked=True, pinned=False)
							await channel.delete()
							for webhook in authors.values():
								await webhook.delete()
					
				elif customid == 'ticket_block':
					if not bool(set(role.id for role in interaction.user.roles) & set(self.answer_roles)):
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_create']['messages']['no-ticket-permission'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT channelid, discordid, messageid FROM discord_tickets WHERE discordid=(SELECT discordid FROM discord_tickets WHERE messageid={interaction.message.id} LIMIT 1) AND (closed IS NULL)')
						values = cursor.fetchall()
						cursor.execute(f'UPDATE discord_tickets SET closed=UNIX_TIMESTAMP(), channelid=NULL, closer=\'{interaction.user.id}\',receiver=COALESCE(receiver, \'{interaction.user.id}\'), receiver_time=COALESCE(receiver_time, UNIX_TIMESTAMP()) WHERE discordid=\'{values[0][1]}\' AND (closed IS NULL)')
						cursor.execute(f'INSERT INTO discord_tickets_blocks (discordid,time) VALUES(\'{values[0][1]}\',UNIX_TIMESTAMP()+86400) ON DUPLICATE KEY UPDATE time=UNIX_TIMESTAMP()+86400')

					time = int(datetime.now().timestamp())
					field_name = Template(self.bot.language.commands['ticket_create']['messages']['user-blocked-field-name']).safe_substitute(time=time,user=interaction.user.mention)
					field_value = Template(self.bot.language.commands['ticket_create']['messages']['user-blocked-field-value']).safe_substitute(time=time,user=interaction.user.mention)
					
					embed = interaction.message.embeds[0]
					embed.add_field(name=field_name,value=field_value)
					await interaction.response.edit_message(view=None,embed=embed)

					thread_name = self.bot.language.commands['ticket_create']['messages']['ticket-history-thread-name']
					authors = {}
					for channelid, discordid, messageid in values:
						if (message:=await interaction.channel.fetch_message(messageid)):
							if message.id != interaction.message.id:
								embed = message.embeds[0]
								embed.add_field(name=field_name,value=field_value)
								await message.edit(view=None,embed=embed)
						if (channel:=interaction.guild.get_channel(channelid)):
							if message:
								thread = await message.create_thread(name=thread_name)
								skip_first = True
								async for message in channel.history(limit=None,oldest_first=True):
									if skip_first:
										skip_first = False
										continue
									if message.content or message.embeds or message.attachments:
										files = [discord.File(BytesIO(await attachment.read(use_cached=False)),filename=attachment.filename) for attachment in message.attachments]
										if message.author.id not in authors:
											authors[message.author.id] = await interaction.message.channel.create_webhook(name=str(message.author),avatar=(await message.author.avatar.read() if message.author.avatar else None))
										await authors[message.author.id].send(wait=False,content=message.content,embeds=message.embeds,files=files,thread=thread)
								await thread.edit(archived=True, locked=True, pinned=False)
							await channel.delete()
					for webhook in authors.values():
						await webhook.delete()
				elif customid == 'ticket_accept':
					if not bool(set(role.id for role in interaction.user.roles) & set(self.answer_roles)):
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['ticket_create']['messages']['no-ticket-permission'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor = self.bot.cursor()
					cursor.execute(f'SELECT id,discordid FROM discord_tickets WHERE messageid={interaction.message.id} LIMIT 1')
					values = cursor.fetchone()
					id = values[0]
					member = interaction.guild.get_member(values[1])
					if member:
						category = interaction.guild.get_channel(self.category)
						overwrites = {
						    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
						    member: discord.PermissionOverwrite(read_messages=True, send_messages=True)
						}
						channel = await interaction.guild.create_text_channel(name=f'Тикет #{id}',category=category, overwrites=overwrites)
						cursor.execute(f'UPDATE discord_tickets SET channelid={channel.id},receiver={interaction.user.id},receiver_time=UNIX_TIMESTAMP() WHERE id={id}')
						embed = interaction.message.embeds[0]
						time = int(datetime.now().timestamp())
						field_name = Template(self.bot.language.commands['ticket_create']['messages']['ticket-accepted-field-name']).safe_substitute(time=time,user=interaction.user.mention)
						field_value = Template(self.bot.language.commands['ticket_create']['messages']['ticket-accepted-field-value']).safe_substitute(time=time,user=interaction.user.mention)
						embed.add_field(name=field_name,value=field_value)
						await channel.send(content=member.mention,embed=embed)
						view = discord.ui.View(timeout=None)
						label = self.bot.language.commands['ticket_create']['messages']['decline-button-label']
						color = discord.ButtonStyle(self.bot.language.commands['ticket_create']['messages']['decline-button-color'])
						view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_close",label=label,style=color))
						label = self.bot.language.commands['ticket_create']['messages']['block-button-label']
						color = discord.ButtonStyle(self.bot.language.commands['ticket_create']['messages']['block-button-color'])
						view.add_item(discord.ui.Button(disabled=False,custom_id="ticket_block",label=label,style=color))
						await interaction.message.edit(view=view,embed=embed)
						channel_link = f'https://discord.com/channels/{self.bot.guild_id}/{channel.id}'
						content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['ticket_create']['messages']['ticket-accepted']).safe_substitute(channel_link=channel_link))
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					else:
						cursor.execute(f'UPDATE discord_tickets SET receiver_time=COALESCE(receiver_time, UNIX_TIMESTAMP()), channelid=NULL, receiver=COALESCE(receiver, \'{interaction.user.id}\'), closer=\'{interaction.user.id}\', closed=UNIX_TIMESTAMP() WHERE id={id}')
						embed = interaction.message.embeds[0]
						time = int(datetime.now().timestamp())
						field_name = Template(self.bot.language.commands['ticket_create']['messages']['ticket-author-leaved-field-name']).safe_substitute(time=time,user=interaction.user.mention)
						field_value = Template(self.bot.language.commands['ticket_create']['messages']['ticket-author-leaved-field-value']).safe_substitute(time=time,user=interaction.user.mention)
						embed.add_field(name=field_name,value=field_value)
						await interaction.response.edit_message(view=None,embed=embed)
					cursor.close()
		self.interaction = interaction
		
		async def check(num):
			if (num % self.check_every_seconds != 0):
				return
			with self.bot.cursor() as cursor:
				cursor.execute("DELETE FROM discord_tickets_blocks WHERE time>UNIX_TIMESTAMP()")
		self.check = check

	async def check_permissions(self, member: discord.Member):
		roles = []
		guild = self.bot.guild()
		for appcmd in await self.bot.tree.fetch_commands(guild= guild):
			if appcmd.name == self.bot.language.commands['ticket_create']['initargs']['name']:
				try:
					roles = [permission.id for permission in (await appcmd.fetch_permissions(guild)).permissions if permission.permission]
				except:
					return True
				break
		if not bool(set(role.id for role in member.roles) & set(roles)):
			return False
		return True
