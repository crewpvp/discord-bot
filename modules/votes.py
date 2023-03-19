from discord import app_commands
from discord.ext import tasks
import discord
from datetime import datetime
from string import Template
from manager import DiscordManager

class DiscordVotes:
	def __init__(self, bot, vote_roles: [int,...],check_every_seconds: int):
		self.bot = bot
		self.vote_roles = vote_roles
		self.check_every_seconds = check_every_seconds
		with self.bot.cursor() as cursor:
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_votes (id BIGINT NOT NULL,channelid BIGINT NOT NULL, start INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), end INT(11) NOT NULL,placeholder CHAR(150), CONSTRAINT id PRIMARY KEY(id))")
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_votes_values (id BIGINT NOT NULL, value INT NOT NULL, label CHAR(100) NOT NULL, description CHAR(100), FOREIGN KEY(id) REFERENCES discord_votes(id) ON DELETE CASCADE)")
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_votes_answers (id BIGINT NOT NULL, discordid BIGINT NOT NULL, value INT NOT NULL, FOREIGN KEY(id) REFERENCES discord_votes(id) ON DELETE CASCADE)")
		
		command_init = self.bot.language.commands['vote']['init']
		@command_init.command(**self.bot.language.commands['vote']['initargs'])
		@app_commands.choices(**self.bot.language.commands['vote']['choices'])
		@app_commands.describe(**self.bot.language.commands['vote']['describe'])
		@app_commands.rename(**self.bot.language.commands['vote']['rename'])
		async def command_vote(interaction: discord.Interaction,values: str, min: int = 1, max: int = 1, hours: float = 0.5, placeholder: str = None):
			values = values.replace("\\","/")
			if placeholder and len(placeholder) > 150:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['placeholder-length-error'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			min = 1 if min < 1 else min
			max = 1 if max < 1 else max
				
			length = len(values)
			if length < 3:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['value-min-length-error'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			time = round(hours*3600)
			crop = values[1:length-1]
			crop = crop.split("][")
			length = len(crop)
			if length > 25:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['values-limit-error'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			min = length if length < min else min
			max = length if length < max else max

			values = []
			
			i = 0
			for value in crop:
				value = value.split("|")
				length = len(value)
				if length > 2:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['values-value-amount-error'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				if length < 1:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['value-not-found'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				if len(value[0]) > 100:
					content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['vote']['messages']['value-max-length-error']).safe_substitute(value=value[0]))
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				if length < 2:	
					values.append({'label':value[0],'value':i,'description':None})
				else:
					if len(value[1]) > 100:
						content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['vote']['messages']['value-max-length-error']).safe_substitute(value=value[1]))
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					values.append({'label':value[0],'value':i,'description':value[1]})
				i+=1

			start = int(datetime.now().timestamp())
			end = start+time

			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['vote']['messages']['vote-format']).safe_substitute(time=end))
			view = discord.ui.View(timeout=None)
			options = [discord.SelectOption(label=value['label'],value=value['value'],description=value['description']) for value in values]
			view.add_item(discord.ui.Select(custom_id="vote",disabled=False, min_values=min, max_values=max, placeholder=placeholder, options=options))
			message = await interaction.channel.send(embeds=embeds,content=content,view=view)

			request = []
			for value in values:
				label = value['label']
				description = value['description']
				value = value['value']
				if description:
					request.append(f'(\'{message.id}\',\'{value}\',\'{label}\',\'{description}\')')
				else:
					request.append(f'(\'{message.id}\',\'{value}\',\'{label}\',null)')

			request = ','.join(request)
			with self.bot.cursor() as cursor:
				if placeholder:
					cursor.execute(f'INSERT INTO discord_votes (id,channelid,end,placeholder) VALUES(\'{message.id}\',\'{interaction.channel_id}\',\'{end}\',\'{placeholder}\')')
				else:
					cursor.execute(f'INSERT INTO discord_votes (id,channelid,end) VALUES(\'{message.id}\',\'{interaction.channel_id}\',\'{end}\')')
				cursor.execute(f'INSERT INTO discord_votes_values VALUES {request}')

			

			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['vote-created'])
			await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)
	
		async def interaction(interaction: discord.Interaction):
			if interaction.type != discord.InteractionType.component or interaction.data['custom_id'] != "vote":
				return
			if not bool(set(self.vote_roles) & set([role.id for role in interaction.user.roles])):
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['no-vote-permission'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return

			request = []
			id = interaction.message.id
			for value in interaction.data['values']:
				request.append(f'(\'{id}\',\'{interaction.user.id}\',\'{value}\')')
			request = ','.join(request)
			
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id FROM discord_votes WHERE id=\'{id}\'')
				if not cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['vote-not-found'])
					await interaction.message.delete()
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				cursor.execute(f'DELETE FROM discord_votes_answers WHERE discordid=\'{interaction.user.id}\' AND id=\'{id}\'')
				cursor.execute(f'INSERT INTO discord_votes_answers VALUES {request}')

			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['vote']['messages']['on-vote'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
		self.interaction = interaction

		async def check(num):
			if (num % self.check_every_seconds != 0):
				return
			cursor = self.bot.cursor()
			cursor.execute(f'SELECT id,channelid,start,end,placeholder FROM discord_votes WHERE end<UNIX_TIMESTAMP()')
			votes = cursor.fetchall()
			if votes:
				for id, channelid, start, end, placeholder in votes:
					message = await self.bot.guild().get_channel(channelid).fetch_message(id)
					if message:
						values = []
						labels = []
						descriptions = []

						cursor.execute(f'SELECT value,label,description FROM discord_votes_values WHERE id=\'{id}\'')
						for value, label, description in cursor.fetchall():
							labels.insert(value,label)
							values.insert(value,0)
							if description:
								descriptions.insert(value,description)
							else:
								descriptions.insert(value,None)

						cursor.execute(f'SELECT value FROM discord_votes_answers WHERE id=\'{id}\'')
						answers = cursor.fetchall()
						if answers:
							for value in answers:
								values[value[0]]+=1

						voices = []
						for i in range(len(labels)):
							description = Template(self.bot.language.commands['vote']['messages']['description']).safe_substitute(description=descriptions[i]) if descriptions[i] else ''
							voices.append(Template(self.bot.language.commands['vote']['messages']['vote-voice-format']).safe_substitute(label=labels[i],description=description,amount=values[i]))
						voices = (self.bot.language.commands['vote']['messages']['join-by']).join(voices)
						
						content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['vote']['messages']['ended-vote-format']).safe_substitute(end_time=end,start_time=start,voices=voices))

						await message.edit(embeds=embeds, content=content,view=None)
				cursor.execute(f'DELETE FROM discord_votes WHERE end<UNIX_TIMESTAMP()')
			cursor.close()
		self.check = check
	
