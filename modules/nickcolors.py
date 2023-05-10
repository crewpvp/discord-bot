import discord
from discord import app_commands
from discord.ext import commands

class NickColors(commands.Cog):
	def __init__(self, bot, colors: [[str,int],...]):
		self.bot = bot
		self.colors = colors
		self.nickcolor = app_commands.choices(color=[app_commands.Choice(name=colors[i][0].lower(), value=i) for i in range(len(colors))])(self.nickcolor)

	@app_commands.command(name='nickcolor',description='изменить цвет своего никнейма')
	@app_commands.rename(color='цвет')
	async def nickcolor(self,interaction: discord.Interaction, color: app_commands.Choice[int] = None):
		guild = interaction.guild
		roles = tuple(set(guild.get_role(col[1]) for col in self.colors) & set(interaction.user.roles))
		if color==None:
			await interaction.user.remove_roles(*roles)
			embed = discord.Embed(description='Цвет вашего ника сброшен',color=discord.Colour.green())
		else:
			await interaction.user.remove_roles(*roles)
			color_name = self.colors[color.value][0]
			await interaction.user.add_roles(guild.get_role(self.colors[color.value][1]))
			embed = discord.Embed(description=f'Цвет вашего ника изменен на {color_name}',color=discord.Colour.green())
		await interaction.response.send_message(embed=embed,ephemeral=True)

	@commands.Cog.listener()
	async def on_member_update(self, before: discord.Member, after: discord.Member):
		roles = []
		guild = self.bot.guild()
		for application_command in await self.bot.tree.fetch_commands(guild= guild):
			if application_command.name == self.nickcolor.name:
				try:
					roles = [permission.id for permission in (await application_command.fetch_permissions(guild)).permissions if permission.permission]
				except:
					return
				break
		if not bool(set(role.id for role in after.roles) & set(roles)):
			roles = tuple(set(guild.get_role(col[1]) for col in self.colors) & set(after.roles))
			await after.remove_roles(*roles)
