from discord import app_commands
import discord

from string import Template
from language import DiscordLanguage
from manager import DiscordManager
from language import DiscordLanguage
class DiscordNickColor:
	def __init__(self, bot, colors: [[str,int],...]):
		self.bot = bot
		self.colors = colors

		@DiscordLanguage.command
		@app_commands.choices(color=[app_commands.Choice(name=colors[i][0].lower(), value=i) for i in range(len(colors))])
		async def nickcolor(interaction: discord.Interaction, color: app_commands.Choice[int] = None):
			guild = interaction.guild
			roles = tuple(set(guild.get_role(col[1]) for col in self.colors) & set(interaction.user.roles))
			if color==None:
				await interaction.user.remove_roles(*roles)
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['nickcolor']['messages']['color-reset'])
			else:
				await interaction.user.remove_roles(*roles)
				color_name = self.colors[color.value][0]
				await interaction.user.add_roles(guild.get_role(self.colors[color.value][1]))
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['nickcolor']['messages']['color-set']).safe_substitute(color_name=color_name))
			await interaction.response.send_message(content=content,embeds=embeds,ephemeral=True)

		async def member_update(before, after):
			roles = []
			guild = self.bot.guild()
			for appcmd in await self.bot.tree.fetch_commands(guild= guild):
				if appcmd.name == self.bot.language.commands['nickcolor']['initargs']['name']:
					try:
						roles = [permission.id for permission in (await appcmd.fetch_permissions(guild)).permissions if permission.permission]
					except:
						return
					break
			if not bool(set(role.id for role in after.roles) & set(roles)):
				roles = tuple(set(guild.get_role(col[1]) for col in self.colors) & set(after.roles))
				await after.remove_roles(*roles)
		self.member_update = member_update
