import discord, json
from discord.ext import commands, tasks

class AutoVoice(commands.Cog):
	def __init__(self, bot, channel: int, category: int, lifetime: int):
		self.bot = bot
		self.channel = channel
		self.category = category
		self.lifetime = lifetime
		self.voice_check = tasks.loop(seconds=self.lifetime)(self.voice_check)
		self.voice_check.after_loop(self.on_voice_check_cancel)

	@commands.Cog.listener()
	async def on_ready(self):
		async with self.bot.cursor() as cursor:
			await cursor.execute("CREATE TABLE IF NOT EXISTS discord_voices (discordid BIGINT NOT NULL, created_time INT(11) DEFAULT UNIX_TIMESTAMP(), channel_id BIGINT UNIQUE, channel_deleted BOOLEAN DEFAULT FALSE, channel_name CHAR(100), overwrites TEXT, PRIMARY KEY (discordid))")
		self.voice_check.start()

	def cog_unload(self):
		self.voice_check.cancel()

	@commands.Cog.listener()
	async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
		if after.channel == None or member.bot:
			return
		async with self.bot.cursor() as cursor:
			if after.channel.id == self.channel:
				await cursor.execute(f'SELECT channel_deleted, channel_name, channel_id, overwrites FROM discord_voices WHERE discordid={member.id}')
				guild = self.bot.guild()
				if data:= await cursor.fetchone():
					channel_deleted, channel_name, channel_id, overwrites = data
					if overwrites:
						overwrites = self.overwrites_from_json(overwrites)
					else:
						overwrites = {}
				else:
					channel_deleted, channel_name, overwrites = True, f'Чат {member.name}', {}

				if channel_deleted:
					category = guild.get_channel(self.category)	
					overwrites[member] = discord.PermissionOverwrite(manage_channels=True,manage_permissions=True,mute_members=True,move_members=True)
					
					channel = await guild.create_voice_channel(category=category,overwrites=overwrites, name=channel_name,position=500)
					await cursor.execute(f'INSERT INTO discord_voices (discordid,channel_id,channel_name) VALUES ({member.id},{channel.id},%s) ON DUPLICATE KEY UPDATE channel_name=%s, channel_id={channel.id}, created_time=UNIX_TIMESTAMP(), channel_deleted=FALSE',(channel_name,channel_name,))
					await member.move_to(channel=channel)
				else:
					await member.move_to(channel=guild.get_channel(channel_id))
			else:
				if before.channel:
					await cursor.execute(f'UPDATE discord_voices SET created_time=UNIX_TIMESTAMP() WHERE channel_id={before.channel.id} OR channel_id={after.channel.id}')
				else:
					await cursor.execute(f'UPDATE discord_voices SET created_time=UNIX_TIMESTAMP() WHERE channel_id={after.channel.id}')	

	async def voice_check(self):
		guild = self.bot.guild()
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT channel_id FROM discord_voices WHERE channel_deleted = FALSE AND created_time+{self.lifetime}<UNIX_TIMESTAMP()')
			for data in await cursor.fetchall():
				channel_id = data[0]
				channel = guild.get_channel(channel_id)
				if channel:
					if len([member for member in channel.members if not member.bot]) <= 0:
						overwrites = self.overwrites_to_json(channel.overwrites)
						await cursor.execute(f'UPDATE discord_voices SET channel_name=%s , channel_deleted=TRUE, overwrites=%s WHERE channel_id={channel_id}',(channel.name,overwrites,))
						await channel.delete()
				else:
					await cursor.execute(f'UPDATE discord_voices SET channel_deleted=TRUE WHERE channel_id={channel_id}')

	async def on_voice_check_cancel(self):
		if not self.voice_check.is_being_cancelled():
			return
		async with self.bot.cursor() as cursor:
			await cursor.execute(f'SELECT channel_id FROM discord_voices WHERE channel_deleted = FALSE')
			for data in await cursor.fetchall():
				channel_id = data[0]
				channel = guild.get_channel(channel_id)
				if channel:
					overwrites = self.overwrites_to_json(channel.overwrites)
					await cursor.execute(f'UPDATE discord_voices SET channel_name=%s , channel_deleted=TRUE, overwrites=%s WHERE channel_id={channel_id}',(channel.name,overwrites,))
					await channel.delete()
				else:
					await cursor.execute(f'UPDATE discord_voices SET channel_deleted=TRUE WHERE channel_id={channel_id}')

	def overwrites_to_json(self,overwrites):
		json_list = []
		for key in overwrites:
			if isinstance(key, discord.Role):
				pair = overwrites[key].pair()
				json_list.append({'type':0,'id':key.id,'allow':pair[0].value,'deny':pair[1].value})
			elif isinstance(key, discord.Member):
				pair = overwrites[key].pair()
				json_list.append({'type':1,'id':key.id,'allow':pair[0].value,'deny':pair[1].value})
		return json.dumps(json_list,indent=0,ensure_ascii=False)
	
	def overwrites_from_json(self,stored_overwrites: str):
		overwrites = {}
		guild = self.bot.guild()
		for overwrite in json.loads(stored_overwrites):
			if overwrite['type']==0:
				subject = guild.get_role(overwrite['id'])
			else:
				subject = guild.get_member(overwrite['id'])
			if not subject:
				continue
			overwrites[subject] = discord.PermissionOverwrite.from_pair(discord.Permissions(permissions=overwrite['allow']),discord.Permissions(permissions=overwrite['deny']))
		return overwrites
