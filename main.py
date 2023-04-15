from modules.votes import DiscordVotes
from modules.greetings import DiscordGreeting
from modules.farewells import DiscordFarewell
from modules.mutes import DiscordMutes
from modules.nickcolors import DiscordNickColor
from modules.tickets import DiscordTickets
from modules.profiles import DiscordProfiles
from modules.premium import DiscordPremium
from modules.minecraft import DiscordMinecraft
from modules.vkmemes import DiscordVkMemes
from modules.chatgpt import DiscordChatGPT
from modules.autovoice import DiscordAutoVoice
from manager import DiscordManager
from language import DiscordLanguage

from discord import app_commands
from discord.ext import tasks
import mariadb, discord, yaml, asyncio

class Bot(discord.Client):

	def __init__(self, config_path: str):
		super().__init__(intents=discord.Intents.all())
		self.config_path = config_path
		

		self.synced = False
		self.tree = app_commands.CommandTree(self)

		with open(config_path) as f:
			self.config = yaml.load(f, Loader=yaml.FullLoader)
		self.guild_id = self.config['discord']['guild-id']

		with open('language.yml') as f:
			self.language = yaml.load(f, Loader=yaml.FullLoader)
		self.language = DiscordLanguage(self,self.language)
		
		self.connection = mariadb.connect(**self.config['mariadb'], autocommit=True)

		self.buttons = {}
		
		modules = self.config['modules']
		self.enabled_modules = [module for module in modules.keys() if 'enabled' in modules[module] and modules[module]['enabled']]
		self.modules = {}
		
		if 'premium' in self.enabled_modules:
			self.modules['premium'] = DiscordPremium(self, **modules['premium']['settings'])
		if 'votes' in self.enabled_modules:
			self.modules['votes'] = DiscordVotes(self, **modules['votes']['settings'])
		if 'farewells' in self.enabled_modules:
			self.modules['farewells'] = DiscordFarewell(self, **modules['farewells']['settings'])
		if 'greetings' in self.enabled_modules:
			self.modules['greetings'] = DiscordGreeting(self, **modules['greetings']['settings'])
		if 'mutes' in self.enabled_modules:
			self.modules['mutes'] = DiscordMutes(self, **modules['mutes']['settings'])
		if 'nick-colors' in self.enabled_modules:
			self.modules['nick-colors'] = DiscordNickColor(self, **modules['nick-colors']['settings'])
		if 'tickets' in self.enabled_modules:
			self.modules['tickets'] = DiscordTickets(self, **modules['tickets']['settings'])
		if 'profiles' in self.enabled_modules:
			self.modules['profiles'] = DiscordProfiles(self, **modules['profiles']['settings'])
		if 'minecraft' in self.enabled_modules:
			self.modules['minecraft'] = DiscordMinecraft(self, **modules['minecraft']['settings'])
		if 'vkmemes' in self.enabled_modules:
			self.modules['vkmemes'] = DiscordVkMemes(self, **modules['vkmemes']['settings'])
		if 'auto-voice' in self.enabled_modules:
			self.modules['autovoice'] = DiscordAutoVoice(self, **modules['auto-voice']['settings'])
		if 'chat-gpt' in self.enabled_modules:
			self.modules['chatgpt'] = DiscordChatGPT(self,**modules['chat-gpt']['settings'])
		
		self.timer = 0
		self.discord_manager = DiscordManager(self)
		self.language.register_groups()

		@self.event
		async def on_interaction(interaction: discord.Interaction):
			for module in self.modules.values():
				if hasattr(module, 'interaction'):
					await module.interaction(interaction) 
		
		@self.event
		async def on_member_remove(member: discord.Member):
			for module in self.modules.values():
				if hasattr(module, 'member_remove'):
					await module.member_remove(member) 

		@self.event
		async def on_member_join(member: discord.Member):
			for module in self.modules.values():
				if hasattr(module, 'member_join'):
					await module.member_join(member)

		@self.event
		async def on_voice_state_update(member: discord.Member, before, after):
			for module in self.modules.values():
				if hasattr(module, 'voice_state_update'):
					await module.voice_state_update(member,before,after)

		@self.event
		async def on_member_update(before, after):
			for module in self.modules.values():
				if hasattr(module, 'member_update'):
					await module.member_update(before,after) 

		@self.event
		async def on_message(message):
			for module in self.modules.values():
				if hasattr(module, 'message'):
					await module.message(message) 

		self.run(self.config['discord']['token'])
		
	def cursor(self):
		try:
			return self.connection.cursor()
		except:
			self.connection = mariadb.connect(**self.config['mariadb'], autocommit=True)
			return self.connection.cursor()

	def guild(self):
		return self.get_guild(self.guild_id)

	def guild_object(self):
		return discord.Object(id=self.guild_id)

	async def on_ready(self):
		await self.wait_until_ready()
		if not self.synced:
			await self.tree.sync(guild = self.guild_object())
			self.synced = True
		
		#self.tree.clear_commands(guild = None)
		#await self.tree.sync(guild = None)

		print(f'Бот {self.user} был успешно подключен')
		
		self.check.start()


	@tasks.loop(seconds=1)
	async def check(self):
		for module in self.modules.values():
			if hasattr(module, 'check'):
				await module.check(self.timer) 
		self.timer += 1

bot = Bot("config.yml")
