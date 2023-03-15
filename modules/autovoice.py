import discord

class DiscordAutoVoice:
	def __init__(self, bot, channel: int, category: int, lifetime: int):
		self.bot = bot
		self.channel = channel
		self.category = category
		self.lifetime = lifetime

		with self.bot.cursor() as cursor:
			cursor.execute("CREATE TABLE IF NOT EXISTS discord_voices (discordid BIGINT NOT NULL, created_time INT(11) DEFAULT UNIX_TIMESTAMP(), channel_id BIGINT UNIQUE, channel_deleted BOOLEAN DEFAULT FALSE, channel_name CHAR(100), PRIMARY KEY (discordid))")

		async def voice_state_update(member, before, after):
			if after.channel == None:
				return
			if member.bot:
				return
			with self.bot.cursor() as cursor:
				if after.channel.id == self.channel:
					cursor.execute(f'SELECT channel_deleted, channel_name, channel_id FROM discord_voices WHERE discordid=?',(member.id,))
					guild = self.bot.guild()
					if data:=cursor.fetchone():
						channel_deleted, channel_name, channel_id = data
					else:
						channel_deleted, channel_name = True, f'Чат {member.name}'

					if channel_deleted:
						category = guild.get_channel(self.category)	
						overwrites = {member: discord.PermissionOverwrite(manage_channels=True)} 
						channel = await guild.create_voice_channel(category=category,overwrites=overwrites, name=channel_name,position=500)
						cursor.execute(f'INSERT INTO discord_voices (discordid,channel_id,channel_name) VALUES (?,?,?) ON DUPLICATE KEY UPDATE channel_id=?, created_time=UNIX_TIMESTAMP(), channel_deleted=FALSE',(member.id,channel.id,channel_name,channel.id,))
						await member.move_to(channel=channel)
					else:
						await member.move_to(channel=guild.get_channel(channel_id))
				else:
					if before.channel:
						cursor.execute(f'UPDATE discord_voices SET created_time=UNIX_TIMESTAMP() WHERE channel_id={before.channel.id} OR channel_id={after.channel.id}')
					else:
						cursor.execute(f'UPDATE discord_voices SET created_time=UNIX_TIMESTAMP() WHERE channel_id={after.channel.id}')
		self.voice_state_update = voice_state_update
		
		async def check(num):
			if (num % self.lifetime != 0):
				return
			guild = self.bot.guild()
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT channel_id FROM discord_voices WHERE channel_deleted = FALSE AND created_time+{self.lifetime}<UNIX_TIMESTAMP()')
				for data in cursor.fetchall():
					channel_id = data[0]
					channel = guild.get_channel(channel_id)
					if channel and len([member for member in channel.members if not member.bot]) <= 0:
						cursor.execute("UPDATE discord_voices SET channel_name=? , channel_deleted=TRUE WHERE channel_id=?",(channel.name,channel_id,))
						await channel.delete()
					else:
						cursor.execute(f'UPDATE discord_voices SET channel_deleted=TRUE WHERE channel_id={channel_id}')			
		self.check = check			