from discord import app_commands
import discord,re,requests,uuid,random,yaml
from datetime import datetime
from modules.utils import relativeTimeParser
from manager import DiscordManager
from modules.MinecraftWebAPI import MinecraftWebAPI
from string import Template
from manager import DiscordManager
from language import DiscordLanguage

class DiscordMinecraft:
	def __init__(self, bot, category: int, channel: int, cooldown: int, registered_role: int,approved_time:int, disapproved_time: int,request_duration: int,exception_role: int,inactive_role: int, inactive_time: int,inactive_on_leave:bool,counter_enabled: bool, counter_format:str, counter_channels:int, check_every_seconds: int, web_host: str, web_login: str, web_password: str, link_cooldown: int, nick_change_cooldown: int):
		self.bot = bot
		self.stages = yaml.load(open('verification.yml'), Loader=yaml.FullLoader)
		self.category = category
		self.channel = channel
		self.cooldown = cooldown
		self.inactive_role = inactive_role
		self.registered_role = registered_role
		self.inactive_time = inactive_time
		self.counter_format = counter_format
		self.counter_channels = counter_channels
		self.counter_enabled = counter_enabled
		self.disapproved_time = disapproved_time
		self.link_cooldown = link_cooldown
		self.nick_change_cooldown = nick_change_cooldown
		self.request_duration = request_duration
		self.approved_time = approved_time
		self.inactive_on_leave = inactive_on_leave
		self.check_every_seconds = check_every_seconds
		self.exception_role = exception_role
		self.webapi = MinecraftWebAPI(web_host, web_login,web_password)
		
		with self.bot.cursor() as cursor:
			cursor.execute("CREATE TABLE IF NOT EXISTS mc_accounts (id UUID NOT NULL,nick CHAR(16) UNIQUE,discordid BIGINT UNIQUE NOT NULL,pseudonym CHAR(64),ip CHAR(36),first_join INT(11) DEFAULT UNIX_TIMESTAMP() NOT NULL,last_join INT(11) DEFAULT UNIX_TIMESTAMP() NOT NULL,time_played INT(11) DEFAULT 0 NOT NULL,last_server VARCHAR(32),timezone INT(2) DEFAULT 0 NOT NULL,chat_global BOOL NOT NULL DEFAULT TRUE,chat_local BOOL NOT NULL DEFAULT TRUE,chat_private BOOL NOT NULL DEFAULT TRUE,inactive BOOL NOT NULL DEFAULT FALSE, purged BOOL NOT NULL DEFAULT FALSE, code INT(5), code_time INT(11), country VARCHAR(32) DEFAULT 'Unknown' NOT NULL,city VARCHAR(32) DEFAULT 'Unknown' NOT NULL, operator BOOL NOT NULL DEFAULT FALSE,PRIMARY KEY (id))")
			cursor.execute("CREATE TABLE IF NOT EXISTS mc_playerdata (id UUID NOT NULL, server VARCHAR(32) NOT NULL, playerdata LONGTEXT NOT NULL, advancements LONGTEXT NOT NULL, PRIMARY KEY (id,server), FOREIGN KEY(id) REFERENCES mc_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE)")
			cursor.execute("CREATE TABLE IF NOT EXISTS mc_playerstats (id UUID NOT NULL, stats LONGTEXT NOT NULL, PRIMARY KEY(id), FOREIGN KEY(id) REFERENCES mc_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE)")

			cursor.execute("CREATE TABLE IF NOT EXISTS mc_exceptions (id UUID NOT NULL, start INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), end INT(11) NOT NULL, reason TEXT, PRIMARY KEY(id), FOREIGN KEY(id) REFERENCES mc_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE)")

			cursor.execute("CREATE TABLE IF NOT EXISTS mc_registrations (id INT NOT NULL AUTO_INCREMENT, discordid BIGINT NOT NULL,uuid UUID NOT NULL, nick CHAR(32) NOT NULL, referal BIGINT, channelid BIGINT UNIQUE, channel_deleted BOOL NOT NULL DEFAULT FALSE, messageid BIGINT UNIQUE, time INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), stage TEXT NOT NULL,sended INT(11), approved BOOL NOT NULL DEFAULT FALSE, closed INT(11), close_reason TEXT, PRIMARY KEY (id))")
			cursor.execute("CREATE TABLE IF NOT EXISTS mc_registrations_answers (id INT NOT NULL, stage TEXT NOT NULL, question TEXT NOT NULL, answer TEXT, FOREIGN KEY(id) REFERENCES mc_registrations(id) ON DELETE CASCADE)")
			
			cursor.execute("CREATE TABLE IF NOT EXISTS mc_inactive_recovery (id INT NOT NULL AUTO_INCREMENT, discordid BIGINT NOT NULL,messageid BIGINT NOT NULL, sended INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), approved BOOL NOT NULL DEFAULT FALSE, closed INT(11), close_reason TEXT, PRIMARY KEY(id), FOREIGN KEY(discordid) REFERENCES mc_accounts(discordid) ON DELETE CASCADE ON UPDATE CASCADE)")
			
			cursor.execute("CREATE TABLE IF NOT EXISTS mc_referals (user BIGINT NOT NULL,referal BIGINT NOT NULL UNIQUE, FOREIGN KEY(referal) REFERENCES mc_accounts(discordid) ON DELETE CASCADE ON UPDATE CASCADE)")
			
			cursor.execute("CREATE TABLE IF NOT EXISTS LinkedPlayers (bedrockId BINARY(16) NOT NULL ,javaUniqueId BINARY(16) NOT NULL UNIQUE,javaUsername VARCHAR(16) NOT NULL UNIQUE, bedrockUsername VARCHAR(17), PRIMARY KEY (bedrockId), INDEX (bedrockId, javaUniqueId)) ENGINE = InnoDB")
			cursor.execute("CREATE OR REPLACE TRIGGER LinkedPlayers_UPDATE AFTER UPDATE ON mc_accounts FOR EACH ROW UPDATE LinkedPlayers SET javaUniqueId=UNHEX(REPLACE(NEW.id, \'-\', \'\')), javaUsername=NEW.nick WHERE javaUniqueId=UNHEX(REPLACE(OLD.id, \'-\', \'\'))")
			cursor.execute("CREATE OR REPLACE TRIGGER LinkedPlayers_DELETE AFTER DELETE ON mc_accounts FOR EACH ROW DELETE FROM LinkedPlayers WHERE javaUniqueId=UNHEX(REPLACE(OLD.id, \'-\', \'\'))")
			
			cursor.execute("CREATE TABLE IF NOT EXISTS mc_last_link (id BIGINT NOT NULL, time INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), PRIMARY KEY (id), FOREIGN KEY(id) REFERENCES mc_accounts(discordid) ON DELETE CASCADE ON UPDATE CASCADE)")
			cursor.execute("CREATE OR REPLACE TRIGGER mc_last_link_UPDATE AFTER UPDATE ON LinkedPlayers FOR EACH ROW BEGIN IF NEW.javaUniqueId != OLD.javaUniqueId THEN INSERT INTO mc_last_link (id,time) VALUES((SELECT discordid FROM mc_accounts WHERE id=HEX(NEW.javaUniqueId)),UNIX_TIMESTAMP()+?) ON DUPLICATE KEY UPDATE id=(SELECT discordid FROM mc_accounts WHERE id=HEX(NEW.javaUniqueId)), time=UNIX_TIMESTAMP()+?; END IF; END",(self.link_cooldown,self.link_cooldown,))
			cursor.execute("CREATE OR REPLACE TRIGGER mc_last_link_INSERT AFTER INSERT ON LinkedPlayers FOR EACH ROW INSERT INTO mc_last_link (id,time) VALUES((SELECT discordid FROM mc_accounts WHERE id=HEX(NEW.javaUniqueId)),UNIX_TIMESTAMP()+?) ON DUPLICATE KEY UPDATE id=(SELECT discordid FROM mc_accounts WHERE id=HEX(NEW.javaUniqueId)), time=UNIX_TIMESTAMP()+?",(self.link_cooldown,self.link_cooldown,))

			cursor.execute("CREATE TABLE IF NOT EXISTS mc_last_nick_change (id BIGINT NOT NULL, time INT(11) NOT NULL DEFAULT UNIX_TIMESTAMP(), PRIMARY KEY (id), FOREIGN KEY(id) REFERENCES mc_accounts(discordid) ON DELETE CASCADE ON UPDATE CASCADE)")
			cursor.execute("CREATE OR REPLACE TRIGGER mc_last_nick_change_UPDATE AFTER UPDATE ON mc_accounts FOR EACH ROW BEGIN IF NEW.id != OLD.id THEN INSERT INTO mc_last_nick_change (id,time) VALUES(NEW.discordid,UNIX_TIMESTAMP()+?) ON DUPLICATE KEY UPDATE id=NEW.discordid, time=UNIX_TIMESTAMP()+?; END IF; END",(self.nick_change_cooldown,self.nick_change_cooldown,))

		@DiscordLanguage.command
		async def registration_startbuttons(interaction: discord.Interaction, java_label: str = None, java_color: app_commands.Choice[int] = None,bedrock_label: str = None, bedrock_color: app_commands.Choice[int] = None):
			java_label = java_label[:80] if java_label else self.bot.language.commands['registration_startbuttons']['messages']['default-java-text']
			bedrock_label = bedrock_label[:80] if bedrock_label else self.bot.language.commands['registration_startbuttons']['messages']['default-bedrock-text']
			java_color = discord.ButtonStyle(java_color.value) if java_color else discord.ButtonStyle(2)
			bedrock_color = discord.ButtonStyle(bedrock_color.value) if bedrock_color else discord.ButtonStyle(2)
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="registration_start_java",label=java_label,style=java_color))
			view.add_item(discord.ui.Button(disabled=False,custom_id="registration_start_bedrock",label=bedrock_label,style=bedrock_color))
			await interaction.channel.send(view=view)
			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['registration_startbuttons']['messages']['buttons-created'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def registration_recoverybutton(interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
			label = label[:80] if label else self.bot.language.commands['registration_recoverybutton']['messages']['default-button-text']
			color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="inactive_recovery_start",label=label,style=color))
			await interaction.channel.send(view=view)
			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['registration_recoverybutton']['messages']['button-created'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def registration_authorizebutton(interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
			label = label[:80] if label else self.bot.language.commands['registration_authorizebutton']['messages']['default-button-text']
			color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="authorize",label=label,style=color))
			await interaction.channel.send(view=view)
			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['registration_authorizebutton']['messages']['button-created'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def registration_authcodebutton(interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
			label = label[:80] if label else self.bot.language.commands['registration_authcodebutton']['messages']['default-button-text']
			color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="authcode",label=label,style=color))
			await interaction.channel.send(view=view)
			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['registration_authcodebutton']['messages']['button-created'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def registration_logoutbutton(interaction: discord.Interaction, label: str = None, color: app_commands.Choice[int] = None):
			label = label[:80] if label else self.bot.language.commands['registration_logoutbutton']['messages']['default-button-text']
			color = discord.ButtonStyle(color.value) if color else discord.ButtonStyle(2)
			view = discord.ui.View(timeout=None)
			view.add_item(discord.ui.Button(disabled=False,custom_id="logout",label=label,style=color))
			await interaction.channel.send(view=view)
			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['registration_logoutbutton']['messages']['button-created'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def recovery(interaction: discord.Interaction):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id FROM mc_accounts WHERE discordid={interaction.user.id} AND inactive=TRUE')
				if not cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['recovery']['messages']['account-not-found'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				cursor.execute(f'SELECT id FROM mc_inactive_recovery WHERE discordid=\'{interaction.user.id}\' AND closed IS NULL')
				if cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['recovery']['messages']['active-recovery-exists'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				await interaction.response.send_modal(self.recovery_modal())
					
		@DiscordLanguage.command
		async def authorize(interaction: discord.Interaction):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={interaction.user.id}')
				data = cursor.fetchone()
			if not data:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['authorize']['messages']['not-registered'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			uuid,nick = data
			if not (server:=await self.webapi.fetch_player(nick)):
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['authorize']['messages']['not-on-server'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			await self.webapi.send_signal(server,'authorize',str(uuid))
			content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['authorize']['messages']['authorized'])
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
		
		@DiscordLanguage.command
		async def logout(interaction: discord.Interaction):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id,nick,ip FROM mc_accounts WHERE discordid={interaction.user.id}')
				data = cursor.fetchone()
				if not data:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['logout']['messages']['account-not-found'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				uuid,nick,ip = data
				if not ip:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['logout']['messages']['not-logged'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				if (server:=await self.webapi.fetch_player(nick)):
					await self.webapi.send_signal(server,'logout',str(uuid))
				cursor.execute(f'UPDATE mc_accounts SET ip=NULL WHERE id=\'{uuid}\'')
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['logout']['messages']['unlogon'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def authcode(interaction: discord.Interaction, minutes: int = 60):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={interaction.user.id}')
				data = cursor.fetchone()
				if not data:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['authcode']['messages']['account-not-found'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				uuid,nick = data
				code = random.randrange(10000,99999)
				code_time = int(datetime.now().timestamp())+(minutes*60)
				cursor.execute(f'UPDATE mc_accounts SET code={code}, code_time={code_time} WHERE id=\'{uuid}\'')
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['authcode']['messages']['code-sended']).safe_substitute(time=code_time,code=code))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def register(interaction: discord.Interaction, environment: app_commands.Choice[int], nick:str, referal: str = None):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id FROM mc_accounts WHERE discordid={interaction.user.id}')
				if cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['nick-already-registered'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				cursor.execute(f'SELECT id FROM mc_registrations WHERE discordid={interaction.user.id} AND closed IS NULL')
				if cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['registration-exists'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				cursor.execute(f'SELECT closed+{self.cooldown} FROM mc_registrations WHERE discordid={interaction.user.id} AND closed+{self.cooldown} > UNIX_TIMESTAMP()')
				time = cursor.fetchone()
				if time:
					content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['register']['messages']['registration-cooldown']).safe_substitute(time=time[0]))
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				if referal:
					if not (referal:=self.fetchDiscordByNick(referal)):
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['referal-not-found'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor.execute(f'SELECT user,referal FROM mc_referals WHERE user={interaction.user.id} AND referal={referal}')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['referal-not-referal'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return

				if environment.value == 1:
					if not re.match("^\.?[A-Za-z][A-Za-z0-9]{0,11}[0-9]{0,4}",nick) is not None:
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['incorrect-bedrock-nick'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					if not (uuid:=self.getBedrockUUID(nick[1:] if nick.startswith('.') else nick)):
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['incorrect-bedrock-nick'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor.execute(f'SELECT bedrockId FROM LinkedPlayers WHERE bedrockId=UNHEX(REPLACE(\'{uuid}\', \'-\', \'\'))')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['nick-already-registered'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					if not nick.startswith("."):
						nick = "."+nick
					cursor.execute(f'SELECT id FROM mc_accounts WHERE discordid={interaction.user.id}')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['already-registered'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
				else:
					if not re.match("[A-Za-z_0-9]{3,16}", nick) is not None:
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['incorrect-java-nick'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					uuid = self.getJavaUUID(nick)
				cursor.execute(f'SELECT id FROM mc_accounts WHERE id=\'{uuid}\'')
				if cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['already-registered'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				cursor.execute(f'SELECT id FROM mc_registrations WHERE uuid=\'{uuid}\' AND closed IS NULL')
				if cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['already-registered'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				category = interaction.guild.get_channel(self.category)
				overwrites = {
				    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
				    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
				}
				channel = await interaction.guild.create_text_channel(name=nick[1:] if nick.startswith('.') else nick,category=category, overwrites=overwrites)
				start_stage = self.stages['start_stage']
				if referal:
					cursor.execute(f'INSERT INTO mc_registrations (discordid,nick,channelid,stage,uuid,referal) VALUES({interaction.user.id},\'{nick}\',{channel.id},\'{start_stage}\',\'{uuid}\',{referal})')	
				else:
					cursor.execute(f'INSERT INTO mc_registrations (discordid,nick,channelid,stage,uuid) VALUES({interaction.user.id},\'{nick}\',{channel.id},\'{start_stage}\',\'{uuid}\')')	
				if self.isFormStage(start_stage):
					content,embeds,component = self.registrationButton(start_stage)
				else:
					content,embeds,component = self.parseQuestions(start_stage)
				await channel.send(content = content, embeds = embeds, view = component)
				channel_link = f'https://discord.com/channels/{self.bot.guild_id}/{channel.id}'
				channel_name = channel.name
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['register']['messages']['registration-started']).safe_substitute(channel_name=channel_name,channel_link=channel_link))
				await interaction.response.send_message(content = content, embeds = embeds, ephemeral=True)

		@DiscordLanguage.command
		async def link(interaction: discord.Interaction, nick: str):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={interaction.user.id}')
				data = cursor.fetchone()
				if not data:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['account-not-found'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				id, nickname = data
				
				cursor.execute(f'SELECT time FROM mc_last_link WHERE id=? AND time>UNIX_TIMESTAMP()',(interaction.user.id,))
				data = cursor.fetchone()
				if data:
					time = data[0]
					content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['link']['messages']['link-cooldown']).safe_substitute(time=time))
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				if nickname.startswith('.'):
					bedrock_uuid, bedrock_nick = id, nickname
					java_nick, java_uuid = nick, self.getJavaUUID(nick)

					cursor.execute(f'SELECT id FROM mc_registrations WHERE uuid=\'{java_uuid}\' AND closed IS NULL')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['nick-already-registered'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return

					if not re.match("[A-Za-z_0-9]{3,16}", nick) is not None:
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['incorrect-java-nick'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor.execute(f'SELECT id FROM mc_accounts WHERE id=\'{java_uuid}\'')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['nick-already-registered'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor.execute(f'SELECT bedrockId FROM LinkedPlayers WHERE bedrockId=UNHEX(REPLACE(\'{bedrock_uuid}\', \'-\', \'\'))')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['nick-already-registered'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor.execute(f'UPDATE mc_accounts SET id = \'{java_uuid}\', nick = \'{java_nick}\', pseudonym=\'{java_nick}\' WHERE discordid={interaction.user.id}')
					if (server:=await self.webapi.fetch_player(bedrock_nick)):
						await self.webapi.send_signal(server,'link_account',str(bedrock_uuid))
				else:
					java_uuid, java_nick = id, nickname
					if not re.match("^\.?[A-Za-z][A-Za-z0-9]{0,11}[0-9]{0,4}",nick) is not None:
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['incorrect-bedrock-nick'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					if not (bedrock_uuid:=self.getBedrockUUID(nick[1:] if nick.startswith('.') else nick)):
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['incorrect-bedrock-nick'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor.execute(f'SELECT id FROM mc_registrations WHERE uuid=\'{bedrock_uuid}\' AND closed IS NULL')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['nick-already-registered'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor.execute(f'SELECT bedrockId FROM LinkedPlayers WHERE bedrockId=UNHEX(REPLACE(\'{bedrock_uuid}\', \'-\', \'\'))')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['nick-already-registered'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					cursor.execute(f'SELECT id FROM mc_accounts WHERE id=\'{bedrock_uuid}\'')
					if cursor.fetchone():
						content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['nick-already-registered'])
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
						return
					if not nick.startswith("."):
						nick = '.'+nick
					bedrock_nick = nick
				cursor.execute(f'INSERT INTO LinkedPlayers VALUES(UNHEX(REPLACE(\'{bedrock_uuid}\', \'-\', \'\')),UNHEX(REPLACE(\'{java_uuid}\', \'-\', \'\')),\'{java_nick}\',\'{bedrock_nick}\')')
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['link']['messages']['account-linked'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def unlink(interaction: discord.Interaction, environment: app_commands.Choice[int] = None):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT bedrockId,javaUniqueId,javaUsername,bedrockUsername FROM LinkedPlayers WHERE javaUniqueId = (SELECT UNHEX(REPLACE(id, \'-\', \'\')) FROM mc_accounts WHERE discordid = {interaction.user.id} LIMIT 1)')
				data = cursor.fetchone()
				if not data:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['unlink']['messages']['account-not-found'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				bedrock_uuid, java_uuid, java_nick, bedrock_nick = data
				bedrock_uuid, java_uuid = uuid.UUID(bytes=bedrock_uuid), uuid.UUID(bytes=java_uuid)
				if not environment:
					component = discord.ui.View(timeout=None)
					options = []
					label = Template(self.bot.language.commands['unlink']['messages']['select-java-label']).safe_substitute(nick=java_nick)
					description = Template(self.bot.language.commands['unlink']['messages']['select-java-description']).safe_substitute(nick=java_nick)
					options.append(discord.SelectOption(label=label,value=0,description=description))
					label = Template(self.bot.language.commands['unlink']['messages']['select-bedrock-label']).safe_substitute(nick=bedrock_nick)
					description = Template(self.bot.language.commands['unlink']['messages']['select-bedrock-description']).safe_substitute(nick=bedrock_nick)
					options.append(discord.SelectOption(label=label,value=1,description=description))
					placeholder = self.bot.language.commands['unlink']['messages']['select-placeholder']
					component.add_item(discord.ui.Select(custom_id='unlink_account',disabled=False, min_values=1, max_values=1, placeholder=placeholder, options=options))
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['unlink']['messages']['select-message'])
					await interaction.response.send_message(view=component,content=content,embeds=embeds, ephemeral=True)
				else:
					environment = environment.value
					cursor.execute(f'DELETE FROM LinkedPlayers WHERE javaUniqueId = UNHEX(REPLACE(\'{java_uuid}\', \'-\', \'\')) AND bedrockId = UNHEX(REPLACE(\'{bedrock_uuid}\', \'-\', \'\'))')
					if environment == 0:
						cursor.execute(f'UPDATE mc_accounts SET id=\'{bedrock_uuid}\', nick=\'{bedrock_nick}\', pseudonym=\'{bedrock_nick}\' WHERE id=\'{java_uuid}\'')
						if (server:=await self.webapi.fetch_player(java_nick)):
							await self.webapi.send_signal(server,'unlink_account',str(java_uuid))
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['unlink']['messages']['account-unlinked'])
					if interaction.message:
						await interaction.response.edit_message(content=content,embeds=embeds,view=None)
					else:
						await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def change_nick(interaction: discord.Interaction, nick: str):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={interaction.user.id}')
				data = cursor.fetchone()
				if not data:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['change_nick']['messages']['account-not-found'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				previous_uuid,previous_nick = data
				if previous_nick.startswith("."):
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['change_nick']['messages']['no-java-account'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				cursor.execute(f'SELECT time FROM mc_last_nick_change WHERE id=? AND time>UNIX_TIMESTAMP()',(interaction.user.id,))
				data = cursor.fetchone()
				if data:
					time = data[0]
					content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['change_nick']['messages']['change-cooldown']).safe_substitute(time=time))
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				if not re.match("[A-Za-z_0-9]{3,16}", nick) is not None:
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['change_nick']['messages']['incorrect-java-nick'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				uuid = self.getJavaUUID(nick)
				cursor.execute(f'SELECT id FROM mc_accounts WHERE id=\'{uuid}\'')
				if cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['change_nick']['messages']['nick-already-registered'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return
				cursor.execute(f'SELECT id FROM mc_registrations WHERE uuid=\'{uuid}\' AND closed IS NULL')
				if cursor.fetchone():
					content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['change_nick']['messages']['nick-already-registered'])
					await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
					return

				cursor.execute(f'UPDATE mc_accounts SET id = \'{uuid}\', nick = \'{nick}\', pseudonym=\'{nick}\' WHERE discordid={interaction.user.id}')
				if (server:=await self.webapi.fetch_player(previous_nick)):
					await self.webapi.send_signal(server,'change_nick',str(previous_uuid))
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['change_nick']['messages']['nick-changed']).safe_substitute(nick=nick))
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		@DiscordLanguage.command
		async def shizotop(interaction: discord.Interaction, page: int = 1):
			page = 0 if page < 1 else page-1
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT nick,discordid,time_played FROM mc_accounts ORDER BY time_played DESC LIMIT {page*25},25')
				players = cursor.fetchall()
			if not players:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['shizotop']['messages']['empty-shizo-list'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			l = []
			for nick,discordid,time_played in players:
				user = interaction.guild.get_member(discordid)
				nick = nick.replace('_','\\\\_')
				if user:
					user = Template(self.bot.language.commands['shizotop']['messages']['user-format']).safe_substitute(user=user.mention)
					player = Template(self.bot.language.commands['shizotop']['messages']['player-format']).safe_substitute(user=user,time=relativeTimeParser(seconds=time_played,greater=True),nick=nick)
				else:
					player = Template(self.bot.language.commands['shizotop']['messages']['player-format']).safe_substitute(user='',time=relativeTimeParser(seconds=time_played,greater=True),nick=nick)
				l.append(player)
			l = (self.bot.language.commands['shizotop']['messages']['join-by']).join(l)
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['shizotop']['messages']['shizo-list']).safe_substitute(players=l))
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=False)
		
		@DiscordLanguage.command
		async def exception_nick(interaction: discord.Interaction, nick: str, days: float = 1.0, reason: str = None):
			user = await self.add_exception(nick=nick,reason=reason,days=days)
			if not user:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['exception_nick']['messages']['account-not-found'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			reason = Template(self.bot.language.commands['exception_nick']['messages']['reason-format']).safe_substitute(reason=reason) if reason else ''
			user = Template(self.bot.language.commands['exception_nick']['messages']['user-format']).safe_substitute(user=user.mention) if user!=True else ''
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['exception_nick']['messages']['player-exceptioned']).safe_substitute(user=user,nick=nick,reason=reason,time=relativeTimeParser(days=days)))
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=False)
				
		@DiscordLanguage.command
		async def exception_member(interaction: discord.Interaction, member: discord.Member, days: float = 1.0, reason: str = None):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT nick FROM mc_accounts WHERE discordid={member.id}')
				data=cursor.fetchone()
			if not data:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['exception_member']['messages']['account-not-found'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			await exception_nick.callback(interaction=interaction,nick=data[0],days=days,reason=reason)
		
		@DiscordLanguage.command
		async def unexception_nick(interaction: discord.Interaction, nick: str):
			user = await self.remove_exception(nick=nick)
			if not user:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['unexception_nick']['messages']['account-not-found'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			user = Template(self.bot.language.commands['unexception_nick']['messages']['user-format']).safe_substitute(user=user.mention) if user!=True else ''
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['unexception_nick']['messages']['player-unexceptioned']).safe_substitute(user=user,nick=nick))
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=False)
		
		@DiscordLanguage.command
		async def unexception_member(interaction: discord.Interaction, member: discord.Member):
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT nick FROM mc_accounts WHERE discordid={member.id}')
				data=cursor.fetchone()
			if not data:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['unexception_member']['messages']['account-not-found'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			await unexception_nick.callback(interaction=interaction,nick=data[0])

		@DiscordLanguage.command
		async def exceptions(interaction: discord.Interaction, page: int = 1):
			page = 0 if page < 1 else page-1
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT a.nick,a.discordid,e.start,e.end,e.reason FROM mc_exceptions AS e JOIN mc_accounts AS a ON a.id=e.id ORDER BY start LIMIT {page*25},25 ')
				players = cursor.fetchall()
			if not players:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['exceptions']['messages']['empty-exception-list'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			l = []
			for nick,discordid,start_time,end_time,reason in players:
				user = interaction.guild.get_member(discordid)
				nick = nick.replace('_','\\\\_')
				reason = Template(self.bot.language.commands['exceptions']['messages']['reason-format']).safe_substitute(reason=reason) if reason else ''
				if user:
					user = Template(self.bot.language.commands['exceptions']['messages']['user-format']).safe_substitute(user=user.mention)
					player = Template(self.bot.language.commands['exceptions']['messages']['player-format']).safe_substitute(start_time=start_time,end_time=end_time,reason=reason,user=user,nick=nick)
				else:
					player = Template(self.bot.language.commands['exceptions']['messages']['player-format']).safe_substitute(start_time=start_time,end_time=end_time,reason=reason,user='',nick=nick)
				l.append(player)
			l = (self.bot.language.commands['exceptions']['messages']['join-by']).join(l)
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['exceptions']['messages']['exception-list']).safe_substitute(players=l))
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=False)

		@DiscordLanguage.command
		async def referals_top(interaction: discord.Interaction, page: int = 1):
			page = 0 if page < 1 else page-1
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT a.nick,r.user,COUNT(r.referal) as cnt FROM mc_referals AS r JOIN mc_accounts AS a ON a.discordid=r.user GROUP BY user ORDER BY cnt DESC LIMIT {page*25},25')
				players = cursor.fetchall()
			if not players:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['referals_top']['messages']['empty-referals-list'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			l = []
			for nick,discordid,count in players:
				user = interaction.guild.get_member(discordid)
				nick = nick.replace('_','\\\\_')
				if user:
					user = Template(self.bot.language.commands['referals_top']['messages']['user-format']).safe_substitute(user=user.mention)
					player = Template(self.bot.language.commands['referals_top']['messages']['player-format']).safe_substitute(count=count,user=user,nick=nick)
				else:
					player = Template(self.bot.language.commands['referals_top']['messages']['player-format']).safe_substitute(count=count,user='',nick=nick)
				l.append(player)
			l = (self.bot.language.commands['referals_top']['messages']['join-by']).join(l)
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['referals_top']['messages']['referals-list']).safe_substitute(count=count,players=l))
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=False)
		
		@DiscordLanguage.command
		async def referals_mine(interaction: discord.Interaction, page: int = 1):
			page = 0 if page < 1 else page-1
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT nick,discordid FROM mc_referals JOIN mc_accounts ON discordid=referal WHERE user={interaction.user.id} LIMIT {page*25},25')
				players = cursor.fetchall()
				cursor.execute(f'SELECT COUNT(*) FROM mc_referals WHERE user={interaction.user.id}')
				count = cursor.fetchone()[0]
			if not players:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['referals_mine']['messages']['empty-referals-list'])
				await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				return
			l = []
			for nick,discordid in players:
				user = interaction.guild.get_member(discordid)
				nick = nick.replace('_','\\\\_')
				if user:
					user = Template(self.bot.language.commands['referals_mine']['messages']['user-format']).safe_substitute(user=user.mention)
					player = Template(self.bot.language.commands['referals_mine']['messages']['player-format']).safe_substitute(user=user,nick=nick)
				else:
					player = Template(self.bot.language.commands['referals_mine']['messages']['player-format']).safe_substitute(user='',nick=nick)
				l.append(player)
			l = (self.bot.language.commands['referals_mine']['messages']['join-by']).join(l)
			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['referals_mine']['messages']['referals-list']).safe_substitute(count=count,players=l))
			await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)

		async def interaction(interaction: discord.Interaction):
			if interaction.type == discord.InteractionType.component:
				customid = interaction.data['custom_id']
				if customid == "inactive_recovery_start":
					await recovery.callback(interaction)
				elif customid == "authorize":
					await authorize.callback(interaction)
				elif customid == "authcode":
					await authcode.callback(interaction)
				elif customid == "logout":
					await logout.callback(interaction)
				elif customid == "inactive_recovery_approve":
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT discordid FROM mc_inactive_recovery WHERE messageid={interaction.message.id}')
						member = interaction.guild.get_member(cursor.fetchone()[0])
						if member:
							cursor.execute(f'UPDATE mc_accounts SET inactive=FALSE, last_join=UNIX_TIMESTAMP() WHERE discordid=\'{member.id}\'')
							cursor.execute(f'UPDATE mc_inactive_recovery SET approved=TRUE,closed=UNIX_TIMESTAMP(),close_reason=\'Ваша заявка о восстановлении была одобрена\' WHERE messageid={interaction.message.id}')
							try:
								await member.remove_roles(interaction.guild.get_role(self.inactive_role))
								await member.add_roles(interaction.guild.get_role(self.registered_role))
							except:
								pass
							embed = interaction.message.embeds[0]
							time = int(datetime.now().timestamp())
							field_name = Template(self.bot.language.commands['recovery']['messages']['accepted-field-name']).safe_substitute(time=time,user=interaction.user.mention)
							field_value = Template(self.bot.language.commands['recovery']['messages']['accepted-field-value']).safe_substitute(time=time,user=interaction.user.mention)
							embed.add_field(name=field_name,value=field_value)
							await interaction.response.edit_message(content=None,view=None,embed=embed)

							content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['recovery']['messages']['dm-accepted-message'])
							try:
								await member.send(embeds=embeds,content=content)
							except:
								pass
						else:
							cursor.execute(f'UPDATE mc_inactive_recovery SET closed=UNIX_TIMESTAMP(), close_reason = \'Заявка автоматически отклонена в связи с покиданием Discord сервера\' WHERE messageid={interaction.message.id}')
							embed = interaction.message.embeds[0]
							time = int(datetime.now().timestamp())
							field_name = Template(self.bot.language.commands['recovery']['messages']['author-leaved-field-name']).safe_substitute(time=time,user=interaction.user.mention)
							field_value = Template(self.bot.language.commands['recovery']['messages']['author-leaved-field-value']).safe_substitute(time=time,user=interaction.user.mention)
							embed.add_field(name=field_name,value=field_value)
							await interaction.response.edit_message(view=None,embed=embed)
				elif customid == "inactive_recovery_disapprove":
					await interaction.response.send_modal(self.recovery_decline_modal())
				elif customid == "registration_start_bedrock":
					await interaction.response.send_modal(self.bedrock_registration_modal())
				elif customid == "registration_start_java":
					await interaction.response.send_modal(self.java_registration_modal())
				elif customid == "registration_stage_open":
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT stage FROM mc_registrations WHERE discordid={interaction.user.id} AND channelid={interaction.channel_id}')
						stage = cursor.fetchone()
						if stage:
							current_stage = stage[0]
							content,embeds,component = self.parseQuestions(current_stage)
							if self.isFormStage(current_stage):
								await interaction.response.send_modal(component)
							else:
								await interaction.response.edit_message(embeds=embeds,content=content,view=component)
						else:
							content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['invalid-registration-user'])
							await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				elif customid == "registration_skip_stage":
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT id,stage,nick,referal FROM mc_registrations WHERE discordid={interaction.user.id} AND channelid={interaction.channel.id}')
						values = cursor.fetchone()
						if values:
							id,stage,nick,referal = values
							if (next_stage:= self.getNextStage(stage)) != None:
								cursor.execute(f'UPDATE mc_registrations SET stage=\'{next_stage}\' WHERE id={id}')
								if self.isFormStage(next_stage):
									content,embeds,component = self.registrationButton(next_stage)
									await interaction.response.edit_message(embeds=embeds,content=content,view=component)
								else:
									content,embeds,component = self.parseQuestions(next_stage)
									await interaction.response.edit_message(embeds=embeds,content=content,view=component)
							else:
								if referal:
									referal = interaction.guild.get_member(referal)
								await self.create_register(interaction,nick,id,referal)	
						else:
							content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['invalid-registration-user'])
							await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				elif customid == "registration_stage":
					question = interaction.data['values'][0]
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT id,stage,nick,referal FROM mc_registrations WHERE discordid={interaction.user.id} AND channelid={interaction.channel.id}')
						values = cursor.fetchone()
						if values:
							id,stage,nick,referal = values
							cursor.execute(f'INSERT INTO mc_registrations_answers (id,stage,question) VALUES({id},\'{stage}\',\'{question}\')')
							if (next_stage:= self.getNextStage(stage,question)) != None:
								cursor.execute(f'UPDATE mc_registrations SET stage=\'{next_stage}\' WHERE id={id}')
								if self.isFormStage(next_stage):
									content,embeds,component = self.registrationButton(next_stage)
									await interaction.response.edit_message(embeds=embeds,content=content,view=component)
								else:
									content,embeds,component = self.parseQuestions(next_stage)
									await interaction.response.edit_message(embeds=embeds,content=content,view=component)
							else:
								if referal:
									referal = interaction.guild.get_member(referal)
								await self.create_register(interaction,nick,id,referal)	
						else:
							content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['invalid-registration-user'])
							await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				elif customid == 'registration_disapprove':
					await interaction.response.send_modal(self.registration_decline_modal())
				elif customid == 'registration_approve':
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT id,discordid, nick, uuid, channelid, referal FROM mc_registrations WHERE messageid={interaction.message.id}')
						id, discordid, nick, uuid, channelid, referal = cursor.fetchone()
						channel = interaction.guild.get_channel(channelid)
						member = interaction.guild.get_member(discordid)
						if member:
							cursor.execute(f'UPDATE mc_registrations SET approved=TRUE, closed=UNIX_TIMESTAMP(), close_reason = \'Заявка одобрена {interaction.user}\' WHERE messageid={interaction.message.id}')
							cursor.execute(f'INSERT INTO mc_accounts (id, nick, discordid, pseudonym) VALUES (\'{uuid}\',\'{nick}\',\'{discordid}\',\'{nick}\')')
							if referal:
								cursor.execute(f'SELECT user,referal FROM mc_referals WHERE user={member.id} AND referal={referal}')
								if not cursor.fetchone():
									cursor.execute(f'INSERT INTO mc_referals (user,referal) VALUES ({referal},{member.id})')
									referal = interaction.guild.get_member(referal)
									if 'premium' in self.bot.enabled_modules:
										await self.bot.modules['premium'].add_premium(member=member,hours=12,days=3)
										if referal:
											await self.bot.modules['premium'].add_premium(member=referal,days=7)

							try:
								await member.remove_roles(interaction.guild.get_role(self.inactive_role))
								await member.add_roles(interaction.guild.get_role(self.registered_role))
							except:
								pass
							embed = interaction.message.embeds[0]
							time = int(datetime.now().timestamp())
							field_name = Template(self.bot.language.commands['register']['messages']['accepted-field-name']).safe_substitute(time=time,user=interaction.user.mention)
							field_value = Template(self.bot.language.commands['register']['messages']['accepted-field-value']).safe_substitute(time=time,user=interaction.user.mention)
							embed.add_field(name=field_name,value=field_value)
							await interaction.response.edit_message(content=None,view=None,embed=embed)

							content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['dm-accepted-message'])
							try:
								await member.send(embeds=embeds,content=content)
							except:
								pass
							content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['channel-accepted-message'])
							await channel.send(embeds=embeds,content=content)
						else:
							cursor.execute(f'UPDATE mc_registrations SET closed=UNIX_TIMESTAMP(), close_reason = \'Заявка автоматически отклонена в связи с покиданием Discord сервера\' WHERE messageid={interaction.message.id}')
							embed = interaction.message.embeds[0]
							time = int(datetime.now().timestamp())
							field_name = Template(self.bot.language.commands['register']['messages']['author-leaved-field-name']).safe_substitute(time=time,user=interaction.user.mention)
							field_value = Template(self.bot.language.commands['register']['messages']['author-leaved-field-value']).safe_substitute(time=time,user=interaction.user.mention)
							embed.add_field(name=field_name,value=field_value)
							await interaction.response.edit_message(view=None,embed=embed)
							content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['register']['messages']['channel-leaved-message']).safe_substitute(unix_time=unix_time,relative_time=relative_time))
							await channel.send(embeds=embeds,content=content)
				elif customid == 'unlink_account':
					await unlink.callback(interaction, app_commands.Choice(name='маня мирок', value=int(interaction.data['values'][0])))
			elif interaction.type == discord.InteractionType.modal_submit:
				customid = interaction.data['custom_id']
				if customid == "inactive_recovery_submit":
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT id FROM mc_inactive_recovery WHERE discordid=\'{interaction.user.id}\' AND closed IS NULL')
						if not cursor.fetchone():
							with self.bot.cursor() as cursor:
								cursor.execute(f'SELECT ((SUM(closed)-SUM(sended))/COUNT(*)) FROM mc_inactive_recovery WHERE closed IS NOT NULL')
								values = cursor.fetchone()
							if values[0]:
								time = relativeTimeParser(seconds=values[0],greater=True)
								time = Template(self.bot.language.commands['recovery']['messages']['average-time-format']).safe_substitute(time=time)
							else:
								time = ""
							content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['recovery']['messages']['response-create-message']).safe_substitute(time=time))
							await interaction.response.send_message(embeds=embeds,content=content,ephemeral=True)	
							try:
								content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['recovery']['messages']['dm-create-message']).safe_substitute(time=time))
								await interaction.user.send(embeds=embeds,content=content)
							except:
								pass
							answers = [component['components'][0]['value'] for component in interaction.data['components']]
							await self.create_inactive_recovery(interaction.user, answers)
						else:
							content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['recovery']['messages']['active-recovery-exists'])
							await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				elif customid == "inactive_recovery_disapprove":
					reason = interaction.data['components'][0]['components'][0]['value']
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT discordid FROM mc_inactive_recovery WHERE messageid={interaction.message.id}')
						member = interaction.guild.get_member(cursor.fetchone()[0])
						if member:
							cursor.execute(f'UPDATE mc_inactive_recovery SET closed=UNIX_TIMESTAMP(), close_reason = \'{reason}\' WHERE messageid={interaction.message.id}')
							embed = interaction.message.embeds[0]
							time = int(datetime.now().timestamp())
							reason_format = Template(self.bot.language.commands['recovery']['messages']['declined-reason-format']).safe_substitute(reason=reason)
							field_name = Template(self.bot.language.commands['recovery']['messages']['declined-field-name']).safe_substitute(reason=reason_format,time=time,user=interaction.user.mention)
							field_value = Template(self.bot.language.commands['recovery']['messages']['declined-field-value']).safe_substitute(reason=reason_format,time=time,user=interaction.user.mention)
							embed.add_field(name=field_name,value=field_value)
							await interaction.response.edit_message(view=None,embed=embed)
							reason_format = Template(self.bot.language.commands['recovery']['messages']['dm-declined-reason-format']).safe_substitute(reason=reason)
							content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['recovery']['messages']['dm-declined-message']).safe_substitute(reason=reason_format))
							try:
								await member.send(embeds=embeds,content=content)
							except:
								pass
						else:
							cursor.execute(f'UPDATE mc_inactive_recovery SET closed=UNIX_TIMESTAMP(), close_reason = \'Заявка автоматически отклонена в связи с покиданием Discord сервера\' WHERE messageid={interaction.message.id}')
							embed = interaction.message.embeds[0]
							time = int(datetime.now().timestamp())
							field_name = Template(self.bot.language.commands['recovery']['messages']['author-leaved-field-name']).safe_substitute(time=time,user=interaction.user.mention)
							field_value = Template(self.bot.language.commands['recovery']['messages']['author-leaved-field-value']).safe_substitute(time=time,user=interaction.user.mention)
							embed.add_field(name=field_name,value=field_value)
							await interaction.response.edit_message(view=None,embed=embed)
				elif customid == "registration_start_bedrock":
					nick = interaction.data['components'][0]['components'][0]['value']
					referal = interaction.data['components'][1]['components'][0]['value']
					referal = referal if referal.replace(' ','') != '' else None
					await register.callback(interaction, app_commands.Choice(name='bedrock edition', value=1), nick, referal)
				elif customid == "registration_start_java":
					nick = interaction.data['components'][0]['components'][0]['value']
					referal = interaction.data['components'][1]['components'][0]['value']
					referal = referal if referal.replace(' ','') != '' else None
					await register.callback(interaction, app_commands.Choice(name='java edition', value=0), nick, referal)
				elif customid == "registration_stage":
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT id,stage,nick,referal FROM mc_registrations WHERE discordid={interaction.user.id} AND channelid={interaction.channel.id}')
						values = cursor.fetchone()
						if values:
							id,stage,nick, referal = values
							
							request = []
							for component in interaction.data['components']:
								component = component['components'][0]
								answer = component['value']
								if answer:
									answer = answer.replace("\\","/")
									question = component['custom_id'] 
									request.append(f'({id},\'{stage}\',\'{question}\',\'{answer}\')')
							if request:
								request = ','.join(request)
								cursor.execute(f'INSERT INTO mc_registrations_answers (id,stage,question,answer) VALUES {request}')
							
							if (next_stage:= self.getNextStage(stage)) != None:
								cursor.execute(f'UPDATE mc_registrations SET stage=\'{next_stage}\' WHERE id={id}')
								if self.isFormStage(next_stage):
									content,embeds,component = self.registrationButton(next_stage)
									await interaction.response.edit_message(embeds=embeds,content=content,view=component)
								else:
									content,embeds,component = self.parseQuestions(next_stage)
									await interaction.response.edit_message(embeds=embeds,content=content,view=component)
							else:
								if referal:
									referal = interaction.guild.get_member(referal)
								await self.create_register(interaction,nick,id,referal)	
						else:
							content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['register']['messages']['invalid-registration-user'])
							await interaction.response.send_message(content=content,embeds=embeds, ephemeral=True)
				elif customid == "registration_disapprove":
					reason = interaction.data['components'][0]['components'][0]['value']
					with self.bot.cursor() as cursor:
						cursor.execute(f'SELECT discordid,channelid FROM mc_registrations WHERE messageid={interaction.message.id}')
						discordid,channelid = cursor.fetchone()
						channel = interaction.guild.get_channel(channelid)
						member = interaction.guild.get_member(discordid)
						if member:
							cursor.execute(f'UPDATE mc_inactive_recovery SET closed=UNIX_TIMESTAMP(), close_reason = \'{reason}\' WHERE messageid={interaction.message.id}')
							embed = interaction.message.embeds[0]
							time = int(datetime.now().timestamp())
							unix_time = time+self.cooldown
							relative_time = relativeTimeParser(seconds=self.cooldown,greater=True)
							
							reason_format = Template(self.bot.language.commands['register']['messages']['declined-reason-format']).safe_substitute(reason=reason)
							field_name = Template(self.bot.language.commands['register']['messages']['declined-field-name']).safe_substitute(reason=reason_format,time=time,user=interaction.user.mention)
							field_value = Template(self.bot.language.commands['register']['messages']['declined-field-value']).safe_substitute(reason=reason_format,time=time,user=interaction.user.mention)
							embed.add_field(name=field_name,value=field_value)
							await interaction.response.edit_message(view=None,embed=embed)

							reason_format = Template(self.bot.language.commands['register']['messages']['dm-declined-reason-format']).safe_substitute(reason=reason)
							content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['register']['messages']['dm-declined-message']).safe_substitute(unix_time=unix_time,relative_time=relative_time,reason=reason_format))
							try:
								await member.send(embeds=embeds,content=content)
							except:
								pass
							reason_format = Template(self.bot.language.commands['register']['messages']['channel-declined-reason-format']).safe_substitute(reason=reason)
							content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['register']['messages']['channel-declined-message']).safe_substitute(unix_time=unix_time,relative_time=relative_time,reason=reason_format))
							await channel.send(embeds=embeds,content=content)
						else:
							cursor.execute(f'UPDATE mc_registrations SET closed=UNIX_TIMESTAMP(), close_reason = \'Заявка автоматически отклонена в связи с покиданием Discord сервера\' WHERE messageid={interaction.message.id}')
							embed = interaction.message.embeds[0]
							time = int(datetime.now().timestamp())
							field_name = Template(self.bot.language.commands['register']['messages']['author-leaved-field-name']).safe_substitute(time=time,user=interaction.user.mention)
							field_value = Template(self.bot.language.commands['register']['messages']['author-leaved-field-value']).safe_substitute(time=time,user=interaction.user.mention)
							embed.add_field(name=field_name,value=field_value)
							await interaction.response.edit_message(view=None,embed=embed)
							content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['register']['messages']['channel-leaved-message']).safe_substitute(unix_time=unix_time,relative_time=relative_time))
							await channel.send(embeds=embeds,content=content)
		self.interaction = interaction

		async def check(num):
			if (num % self.check_every_seconds != 0):
				return
			guild = self.bot.guild()
			registered_role = guild.get_role(self.registered_role)

			#
			# show whitelist users count in name of channel 
			#
			with self.bot.cursor() as cursor:
				if self.counter_enabled:
					cursor.execute('SELECT 0+COUNT(*) FROM mc_accounts WHERE inactive=FALSE')
					count = cursor.fetchone()[0]
					for channel in self.counter_channels:
						await guild.get_channel(channel).edit(name=self.counter_format.format(count=count))
			#
			# check inactives		
			#
			with self.bot.cursor() as cursor:
				if 'premium' in self.bot.enabled_modules:
					cursor.execute(f'SELECT a.discordid FROM mc_accounts AS a LEFT JOIN discord_premium AS p ON p.discordid=a.discordid WHERE COALESCE(p.end,0)<UNIX_TIMESTAMP() AND a.inactive=FALSE AND UNIX_TIMESTAMP()-a.last_join>{self.inactive_time}')
				else:
					cursor.execute(f'SELECT discordid FROM mc_accounts WHERE mc_accounts.inactive=FALSE AND UNIX_TIMESTAMP()-mc_accounts.last_join>{self.inactive_time}')
				ids = cursor.fetchall()
				if ids:
					if 'premium' in self.bot.enabled_modules:
						cursor.execute(f'UPDATE mc_accounts,discord_premium SET mc_accounts.inactive=TRUE WHERE mc_accounts.discordid=discord_premium.discordid AND COALESCE(discord_premium.end,0)<UNIX_TIMESTAMP() AND mc_accounts.inactive=FALSE AND UNIX_TIMESTAMP()-mc_accounts.last_join>{self.inactive_time}')
					else:
						cursor.execute(f'UPDATE mc_accounts SET mc_accounts.inactive=TRUE WHERE mc_accounts.inactive=FALSE AND UNIX_TIMESTAMP()-mc_accounts.last_join>{self.inactive_time}')
					
					inactive_role = guild.get_role(self.inactive_role)
					for discordid in ids:
						try:
							member = guild.get_member(discordid[0])
							await member.remove_roles(registered_role)
							await member.add_roles(inactive_role)
						except:
							pass
			#
			# check exceptions
			#
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT a.nick,a.id,a.discordid FROM mc_exceptions AS e JOIN mc_accounts AS a ON e.id=a.id WHERE e.end<UNIX_TIMESTAMP()')
				users = cursor.fetchall()
				if users:
					cursor.execute(f'DELETE FROM mc_exceptions WHERE end<UNIX_TIMESTAMP()')
					guild = self.bot.guild()
					role = guild.get_role(self.exception_role)
					for nick,id,discordid in users:
						member = guild.get_member(discordid)
						if member:
							if (server:=await self.webapi.fetch_player(nick)):
								await self.webapi.send_signal(server,'unexceptioned',str(id))
							await member.remove_roles(role)
			#
			# check registrations 
			#
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT channelid FROM mc_registrations WHERE channel_deleted=FALSE AND approved=FALSE AND closed IS NULL AND sended IS NULL AND time+{self.request_duration}<UNIX_TIMESTAMP()')
				channels = cursor.fetchall()
				cursor.execute(f'UPDATE mc_registrations SET channel_deleted=TRUE, closed=UNIX_TIMESTAMP(), close_reason=\'Истечение срока прохождения регистрации\' WHERE channel_deleted=FALSE AND approved=FALSE AND closed IS NULL AND sended IS NULL AND time+{self.request_duration}<UNIX_TIMESTAMP()')
				for channelid in channels:
					if (channel:=guild.get_channel(channelid[0])):
						await channel.delete()
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT channelid FROM mc_registrations WHERE channel_deleted=FALSE AND approved=FALSE AND closed IS NOT NULL AND closed+{self.disapproved_time}<UNIX_TIMESTAMP()')
				channels = cursor.fetchall()
				cursor.execute(f'UPDATE mc_registrations SET channel_deleted=TRUE WHERE channel_deleted=FALSE AND approved=FALSE AND closed IS NOT NULL AND closed+{self.disapproved_time}<UNIX_TIMESTAMP()')
				for channelid in channels:
					if (channel:=guild.get_channel(channelid[0])):
						await channel.delete()
			with self.bot.cursor() as cursor:
				cursor.execute(f'SELECT channelid FROM mc_registrations WHERE channel_deleted=FALSE AND approved=TRUE AND closed IS NOT NULL AND closed+{self.approved_time}<UNIX_TIMESTAMP()')
				channels = cursor.fetchall()
				cursor.execute(f'UPDATE mc_registrations SET channel_deleted=TRUE WHERE channel_deleted=FALSE AND approved=TRUE AND closed IS NOT NULL AND closed+{self.approved_time}<UNIX_TIMESTAMP()')
				for channelid in channels:
					if (channel:=guild.get_channel(channelid[0])):
						await channel.delete()
		self.check = check
		if self.inactive_on_leave:
			async def member_remove(member: discord.Member):
				with self.bot.cursor() as cursor:
					cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={member.id}')
					data = cursor.fetchone()
					if not data:
						return
					id,nick = data
					if (server:=await self.webapi.fetch_player(nick)):
						await self.webapi.send_signal(server,'leaved',str(id))
					cursor.execute(f'UPDATE mc_accounts SET mc_accounts.inactive=TRUE WHERE discordid={member.id}')
			self.member_remove = member_remove

	def fetchDiscordByNick(self,nick: str):
		cursor = self.bot.cursor()
		cursor.execute(f'SELECT discordid FROM mc_accounts WHERE LOWER(nick) LIKE LOWER(?)',(nick,))
		discordid = cursor.fetchone()
		cursor.close()
		if discordid:
			return discordid[0]
		nick = nick.lower()
		member = discord.utils.find(lambda m: re.match('.*'+nick+'.*',m.display_name.lower()) or re.match('.*'+nick+'.*',m.name.lower()), self.bot.guild().members)
		if member:
			return member.id
		return None
	def getBedrockUUID(self, gamertag: str):
	    gamertag = gamertag[1:] if gamertag.startswith('.') else gamertag
	    try:
	        gamertag = int(requests.get(f'https://api.geysermc.org/v2/xbox/xuid/{gamertag}').text[8:-1])
	    except:
	        return None
	    if len(str(gamertag)) > 16:
	        return None
	    left = hex(gamertag)[2:]
	    decades = [12,4,4,4,8]
	    final = ['00000000','0000','0000','0000','000000000000']
	    for i in range(5):
	        l = len(left)
	        s = l-decades[i]
	        if s>0:
	            left,right = left[:s],left[s:]
	            final[4-i] = right
	        else:
	            final[4-i]= final[i][l:] + left
	            break
	    return '-'.join(final)
	def getJavaUUID(self,nickname: str):
	    class NULL_NAMESPACE:
	        bytes = b''
	    return uuid.uuid3(NULL_NAMESPACE, "OfflinePlayer:"+nickname)
	
	def parseQuestions(self, stage:str):
		stage = self.stages['stages'][stage]

		content, reference, embeds, view = None, None, None, None
		if 'message' in stage:
			content, reference, embeds, view = DiscordManager.json_to_message(stage['message'])

		if 'questions' in stage:
			component = discord.ui.Modal(timeout=None,title=stage['title'],custom_id='registration_stage')
			if stage['shuffle']:
				for key in random.sample(list(stage['questions'].keys()), stage['max']):
					question = stage['questions'][key]
					if 'description' in question:
						component.add_item(discord.ui.TextInput(custom_id=key, min_length=question['min'],max_length=question['max'],label=question['title'],style=discord.TextStyle.paragraph, placeholder=question['description'], required=question['required']))
					else:
						component.add_item(discord.ui.TextInput(custom_id=key, min_length=question['min'],max_length=question['max'],label=question['title'],style=discord.TextStyle.paragraph, required=question['required']))
			else:
				keys = list(stage['questions'].keys())
				for i in range(len(keys)):
					key = keys[i]
					question = stage['questions'][key]
					if 'description' in question:
						component.add_item(discord.ui.TextInput(custom_id=key, min_length=question['min'],max_length=question['max'],label=question['title'],style=discord.TextStyle.paragraph, placeholder=question['description'], required=question['required']))
					else:
						component.add_item(discord.ui.TextInput(custom_id=key, min_length=question['min'],max_length=question['max'],label=question['title'],style=discord.TextStyle.paragraph, required=question['required']))
		elif 'choose'in stage:
			component = discord.ui.View(timeout=None)
			options = []
			if stage['shuffle']:
				for key in random.sample(list(stage['choose'].keys()), stage['max']):
					choose = stage['choose'][key]
					if 'description' in choose:
						options.append(discord.SelectOption(label=choose['title'],value=key,description=choose['description']))
					else:
						options.append(discord.SelectOption(label=choose['title'],value=key))
			else:
				keys = list(stage['choose'].keys())
				for i in range(len(keys)):
					key = keys[i]
					choose = stage['choose'][key]
					if 'description' in choose:
						options.append(discord.SelectOption(label=choose['title'],value=key,description=choose['description']))
					else:
						options.append(discord.SelectOption(label=choose['title'],value=key))
			component.add_item(discord.ui.Select(custom_id='registration_stage',disabled=False, min_values=1, max_values=1, placeholder=stage['title'], options=options))

		return content,embeds,component
	def registrationButton(self, stage: str):
		stage = self.stages['stages'][stage]
		
		content, reference, embeds, view = None, None, None, None
		if 'message' in stage:
			content, reference, embeds, view = DiscordManager.json_to_message(stage['message'])

		if 'button' in stage:
			button = stage['button']
			title = button['title'] if 'title' in button else self.bot.language.commands['register']['messages']['default-registration-button-title']
			color = discord.ButtonStyle(button['color']) if 'color' in button else discord.ButtonStyle.green
		else:
			title = self.bot.language.commands['register']['messages']['default-registration-button-title']
			color = discord.ButtonStyle.green

		component = discord.ui.View(timeout=None)
		if 'questions' in stage: 
			component.add_item(discord.ui.Button(disabled=False,custom_id="registration_stage_open",label=title,style=color))
		else:
			component.add_item(discord.ui.Button(disabled=False,custom_id="registration_skip_stage",label=title,style=color))

		return content,embeds,component
	def isFormStage(self, stage: str):
		if 'choose' in (self.stages['stages'][stage]):
			return False
		return True
	def getNextStage(self, stage:str, question: str = None):
		stage = self.stages['stages'][stage]
		if question:
			if 'choose' in stage:
				question = stage['choose'][question]
				if 'next_stage' in question:
					return question['next_stage']
		return stage['next_stage'] if 'next_stage' in stage else None
	def parseAnswers(self,id: int):
		with self.bot.cursor() as cursor:
			cursor.execute(f'SELECT DISTINCT a.stage,a.question,a.answer FROM mc_registrations_answers AS a JOIN mc_registrations AS s ON s.id=a.id WHERE a.id={id}')
			answers = cursor.fetchall()
		final = []
		stages = self.stages['stages']
		for stage,question,answer in answers:
			stage = stages[stage]
			if answer:
				final.append([stage['questions'][question]['title'],answer])
			else:
				final.append([stage['title'],stage['choose'][question]['title']])
		return final
	
	async def create_register(self,interaction,nick, id, referal):
		with self.bot.cursor() as cursor:
			cursor.execute("SELECT ((SUM(closed)-SUM(sended))/COUNT(*)) FROM mc_registrations WHERE closed IS NOT NULL AND sended IS NOT NULL")
			values = cursor.fetchone()
			if values[0]:
				time = relativeTimeParser(seconds=values[0],greater=True)
				time = Template(self.bot.language.commands['register']['messages']['average-time-format']).safe_substitute(time=time)
			else:
				time = ""

			content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['register']['messages']['channel-create-message']).safe_substitute(time=time))
			await interaction.response.edit_message(embeds=embeds,content=content,view=None)	
			try:
				content, reference, embeds, view = DiscordManager.json_to_message(Template(self.bot.language.commands['register']['messages']['dm-create-message']).safe_substitute(time=time))
				await interaction.user.send(embeds=embeds,content=content)
			except:
				pass

			raw_user = interaction.user.mention
			user = Template(self.bot.language.commands['register']['messages']['user-format']).safe_substitute(user=raw_user)
			raw_nick = nick.replace('_','\\_')
			nick = Template(self.bot.language.commands['register']['messages']['nick-format']).safe_substitute(nick=raw_nick)
			inviter = Template(self.bot.language.commands['register']['messages']['inviter-format']).safe_substitute(user=referal.mention) if referal else ''
			embed = discord.Embed(
				title = Template(self.bot.language.commands['register']['messages']['embed-title']).safe_substitute(raw_nick=raw_nick,nick=nick,raw_user=raw_user,user=user,inviter=inviter,id=id),
				description = Template(self.bot.language.commands['register']['messages']['embed-description']).safe_substitute(raw_nick=raw_nick,nick=nick,raw_user=raw_user,user=user,inviter=inviter,id=id).replace('\\n','\n'),
				colour = discord.Colour.from_rgb(100, 100, 100)
			)
			
			content = Template(self.bot.language.commands['register']['messages']['content']).safe_substitute(raw_nick=raw_nick,nick=nick,raw_user=raw_user,user=user, inviter=inviter,id=id)
			for answer in self.parseAnswers(id):
				embed.add_field(name=answer[0],value=answer[1],inline=False)
			view = discord.ui.View(timeout=None)
			label = self.bot.language.commands['register']['messages']['accept-button-label']
			color = discord.ButtonStyle(self.bot.language.commands['register']['messages']['accept-button-color'])
			view.add_item(discord.ui.Button(disabled=False,custom_id="registration_approve",label=label,style=color))
			label = self.bot.language.commands['register']['messages']['decline-button-label']
			color = discord.ButtonStyle(self.bot.language.commands['register']['messages']['decline-button-color'])
			view.add_item(discord.ui.Button(disabled=False,custom_id="registration_disapprove",label=label,style=color))
			message = await self.bot.guild().get_channel(self.channel).send(content=content,embed=embed,view=view)
			cursor.execute(f'UPDATE mc_registrations SET sended=UNIX_TIMESTAMP(), messageid={message.id} WHERE id={id}')
	
	async def remove_inactive(self, member):
		with self.bot.cursor() as cursor:
			cursor.execute(f'UPDATE mc_accounts SET inactive=FALSE, last_join=UNIX_TIMESTAMP() WHERE discordid=\'{member.id}\'')
			cursor.execute(f'UPDATE mc_inactive_recovery SET approved=TRUE,closed=UNIX_TIMESTAMP(),close_reason=\'Ваша заявка о восстановлении была одобрена\' WHERE discordid=\'{member.id}\' AND closed IS NULL AND approved IS FALSE')
			await member.remove_roles(interaction.guild.get_role(self.inactive_role))
			await member.add_roles(interaction.guild.get_role(self.registered_role))
			cursor.execute(f'SELECT id,nick FROM mc_accounts WHERE discordid={member.id}')
			id,nick = cursor.fetchone()
			if (server:=await self.webapi.fetch_player(nick)):
				await self.webapi.send_signal(server,'inactive_remove',str(id))

	async def create_inactive_recovery(self, member, answers: [str,...] = None):
		with self.bot.cursor() as cursor:
			cursor.execute(f'SELECT id, nick, time_played, first_join, last_join FROM mc_accounts WHERE discordid = {member.id}')
			data = cursor.fetchone()
			if not data:
				return False
			cursor.execute('SELECT AUTO_INCREMENT FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = \'mc_inactive_recovery\'')
			newid = cursor.fetchone()[0]
			id, nick, time_played, first_join, last_join = data
			cursor.execute(f'SELECT bedrockUsername FROM LinkedPlayers WHERE javaUniqueId=UNHEX(REPLACE(\'{id}\', \'-\', \'\'))')
			data = cursor.fetchone()
			subname = data[0] if data else None	
			raw_user = member.mention
			user = Template(self.bot.language.commands['recovery']['messages']['user-format']).safe_substitute(user=raw_user)
			raw_nick = nick.replace('_','\\_')
			if subname:
				subname = subname.replace('_','\\_')
				subname = Template(self.bot.language.commands['recovery']['messages']['subname-format']).safe_substitute(subname=subname)
			else:
				subname = ''
			nick = Template(self.bot.language.commands['recovery']['messages']['nick-format']).safe_substitute(nick=raw_nick,subname=subname)
			if first_join!=last_join:
				last_join = Template(self.bot.language.commands['recovery']['messages']['last-join-format']).safe_substitute(time=last_join)
			else:
				last_join = ''
			first_join = Template(self.bot.language.commands['recovery']['messages']['first-join-format']).safe_substitute(time=first_join)
			if time_played > 0:
				time_played = Template(self.bot.language.commands['recovery']['messages']['time-played-format']).safe_substitute(time=relativeTimeParser(seconds=time_played))
			else:
				time_played = ''
			embed = discord.Embed(
				title = Template(self.bot.language.commands['recovery']['messages']['embed-title']).safe_substitute(raw_nick=raw_nick,nick=nick,raw_user=raw_user,user=user,time_played=time_played,last_join=last_join,first_join=first_join,id=newid),
				description = Template(self.bot.language.commands['recovery']['messages']['embed-description']).safe_substitute(raw_nick=raw_nick,nick=nick,raw_user=raw_user,user=user,time_played=time_played,last_join=last_join,first_join=first_join,id=newid).replace('\\n','\n'),
				colour = discord.Colour.from_rgb(100, 100, 100)
				)
			content = Template(self.bot.language.commands['recovery']['messages']['content']).safe_substitute(raw_nick=raw_nick,nick=nick,raw_user=raw_user,user=user,time_played=time_played,last_join=last_join,first_join=first_join,id=newid)
			questions = self.recovery_questions()
			if answers:
				for i in range(len(questions)):
					embed.add_field(name=questions[i]['label'],value=answers[i],inline=False)
			view = discord.ui.View(timeout=None)
			label = self.bot.language.commands['recovery']['messages']['accept-button-label']
			color = discord.ButtonStyle(self.bot.language.commands['recovery']['messages']['accept-button-color'])
			view.add_item(discord.ui.Button(disabled=False,custom_id="inactive_recovery_approve",label=label,style=color))
			label = self.bot.language.commands['recovery']['messages']['decline-button-label']
			color = discord.ButtonStyle(self.bot.language.commands['recovery']['messages']['decline-button-color'])
			view.add_item(discord.ui.Button(disabled=False,custom_id="inactive_recovery_disapprove",label=label,style=color))
			message = await self.bot.guild().get_channel(self.channel).send(content=content,embed=embed,view=view)
			cursor.execute(f'INSERT INTO mc_inactive_recovery (discordid,messageid) VALUES ({member.id},{message.id})')

	def bedrock_registration_modal(self):
		modal_title = self.bot.language.commands['register']['messages']['registration-bedrock-modal-title']
		modal = discord.ui.Modal(title=modal_title, custom_id = "registration_start_bedrock")
		label = self.bot.language.commands['register']['messages']['registration-nick-input-label']
		placeholder = self.bot.language.commands['register']['messages']['registration-nick-input-placeholder']
		modal.add_item(discord.ui.TextInput(min_length=1,max_length=17,label=label,style=discord.TextStyle.short, placeholder=placeholder))
		label = self.bot.language.commands['register']['messages']['registration-referal-input-label']
		placeholder = self.bot.language.commands['register']['messages']['registration-referal-input-placeholder']
		modal.add_item(discord.ui.TextInput(min_length=1,max_length=17,label=label,style=discord.TextStyle.short,required=False, placeholder=placeholder))
		return modal
	def java_registration_modal(self):
		modal_title=self.bot.language.commands['register']['messages']['registration-java-modal-title']
		modal = discord.ui.Modal(title=modal_title, custom_id = "registration_start_java")
		label = self.bot.language.commands['register']['messages']['registration-nick-input-label']
		placeholder = self.bot.language.commands['register']['messages']['registration-nick-input-placeholder']
		modal.add_item(discord.ui.TextInput(min_length=3,max_length=16,label=label,style=discord.TextStyle.short, placeholder=placeholder))
		label = self.bot.language.commands['register']['messages']['registration-referal-input-label']
		placeholder = self.bot.language.commands['register']['messages']['registration-referal-input-placeholder']
		modal.add_item(discord.ui.TextInput(min_length=1,max_length=17,label=label,style=discord.TextStyle.short,required=False, placeholder=placeholder))
		return modal
	def registration_decline_modal(self):
		modal_title = self.bot.language.commands['register']['messages']['registration-decline-modal-title']
		modal = discord.ui.Modal(title=modal_title, custom_id = "registration_disapprove")
		label = self.bot.language.commands['register']['messages']['registration-decline-modal-label']
		placeholder = self.bot.language.commands['register']['messages']['registration-decline-modal-placeholder']
		modal.add_item(discord.ui.TextInput(max_length=512,label=label,style=discord.TextStyle.paragraph, placeholder=placeholder))
		return modal
	
	def recovery_questions(self):
		recovery = self.stages['recovery']
		size = len(recovery)
		size = size if size<5 else 5
		return [recovery[i] for i in range(size)]
	def recovery_modal(self):
		modal_title = self.bot.language.commands['recovery']['messages']['recovery-modal-title']
		modal = discord.ui.Modal(title=modal_title, custom_id = "inactive_recovery_submit")
		for question in self.recovery_questions():
			modal.add_item(discord.ui.TextInput(min_length=question['min'],max_length=question['max'],label=question['label'],style=discord.TextStyle.paragraph, placeholder=question['placeholder']))
		return modal
	def recovery_decline_modal(self):
		modal_title = self.bot.language.commands['recovery']['messages']['decline-modal-title']
		modal = discord.ui.Modal(title=modal_title, custom_id = "inactive_recovery_disapprove")
		label = self.bot.language.commands['recovery']['messages']['decline-modal-label']
		placeholder = self.bot.language.commands['recovery']['messages']['decline-modal-placeholder']
		modal.add_item(discord.ui.TextInput(max_length=512,label=label,style=discord.TextStyle.paragraph, placeholder=placeholder))
		return modal

	async def add_exception(self, nick: str, reason: str = None, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0, years: int = 0):
		time = seconds+(minutes*60)+(hours*3600)+(days*86400)+(years*31536000)
		id = self.getJavaUUID(nick) if not nick.startswith('.') else getBedrockUUID(nick)
		if not id:
			return False
		with self.bot.cursor() as cursor:
			cursor.execute(f'SELECT discordid FROM mc_accounts WHERE id=\'{id}\'')
			if not (data:=cursor.fetchone()):
				return False
			if reason:
				cursor.execute(f'INSERT INTO mc_exceptions (id,end,reason) VALUES (\'{id}\',UNIX_TIMESTAMP()+{time},?) ON DUPLICATE KEY UPDATE end=end+{time}, reason=?',(reason,reason,))
			else:
				cursor.execute(f'INSERT INTO mc_exceptions (id,end) VALUES (\'{id}\',UNIX_TIMESTAMP()+{time}) ON DUPLICATE KEY UPDATE end=end+{time}')
			if (server:=await self.webapi.fetch_player(nick)):
				await self.webapi.send_signal(server,'exceptioned',str(id))
			if(member:=self.bot.guild().get_member(data[0])):
				await member.add_roles(self.bot.guild().get_role(self.exception_role))
				return member
			return True
	async def remove_exception(self, nick: str):
		id = self.getJavaUUID(nick) if not nick.startswith('.') else getBedrockUUID(nick)
		if not id:
			return False
		with self.bot.cursor() as cursor:
			cursor.execute(f'SELECT a.discordid FROM mc_exceptions AS e JOIN mc_accounts AS a on a.id=e.id WHERE e.id=\'{id}\'')
			if (data:=cursor.fetchone()):
				cursor.execute(f'DELETE FROM mc_exceptions WHERE id=\'{id}\'')
				if (server:=await self.webapi.fetch_player(nick)):
					await self.webapi.send_signal(server,'unexceptioned',str(id))
				if(member:=self.bot.guild().get_member(data[0])):
					await member.remove_roles(self.bot.guild().get_role(self.exception_role))
					return member
				return True
		return False
