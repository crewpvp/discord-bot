from discord.ext import tasks, commands
import discord, yaml, logging, asyncio
from utils import Connector

from modules import Greetings, Farewells, AutoVoice, Manager, Votes, VkMemes, NickColors
from modules import Premium, Mutes, Tickets, Profiles, ChatGPT, SimpleChatGPT, Minecraft 

class Bot(commands.Bot):

	def __init__(self, config_path: str):
		super().__init__(command_prefix='!', help_command=None, intents=discord.Intents.all())

		self.synced = False
		self.config_path = config_path

		with open(config_path) as f:
			self.config = yaml.load(f, Loader=yaml.FullLoader)
		self.guild_id = self.config['discord']['guild-id']

		modules = self.config['modules']
		self.enabled_modules = [module for module in modules.keys() if 'enabled' in modules[module] and modules[module]['enabled']]
		
		self.connection_pool = Connector(**self.config['mariadb'])
		
		self.run(self.config['discord']['token'])

	def cursor(self):
		return self.connection_pool.get_cursor()
	
	def guild(self):
		return self.get_guild(self.guild_id)

	def guild_object(self):
		return discord.Object(id=self.guild_id)
	
	async def setup_hook(self):
		await self.connection_pool.new_connection_pool()
		if 'farewells' in self.enabled_modules:
			await self.add_cog(Farewells(self, **self.config['modules']['farewells']['settings']),guild=self.guild_object())
		if 'greetings' in self.enabled_modules:
			await self.add_cog(Greetings(self, **self.config['modules']['greetings']['settings']),guild=self.guild_object())
		if 'autovoice' in self.enabled_modules:
			await self.add_cog(AutoVoice(self, **self.config['modules']['autovoice']['settings']),guild=self.guild_object())
		if 'votes' in self.enabled_modules:
			await self.add_cog(Votes(self, **self.config['modules']['votes']['settings']),guild=self.guild_object())
		if 'vkmemes' in self.enabled_modules:
			await self.add_cog(VkMemes(self, **self.config['modules']['vkmemes']['settings']),guild=self.guild_object())
		if 'nickcolors' in self.enabled_modules:
			await self.add_cog(NickColors(self, **self.config['modules']['nickcolors']['settings']),guild=self.guild_object())
		if 'premium' in self.enabled_modules:
			await self.add_cog(Premium(self, **self.config['modules']['premium']['settings']),guild=self.guild_object())
		if 'mutes' in self.enabled_modules:
			await self.add_cog(Mutes(self, **self.config['modules']['mutes']['settings']),guild=self.guild_object())
		if 'tickets' in self.enabled_modules:
			await self.add_cog(Tickets(self, **self.config['modules']['tickets']['settings']),guild=self.guild_object())
		if 'profiles' in self.enabled_modules:
			await self.add_cog(Profiles(self, **self.config['modules']['profiles']['settings']),guild=self.guild_object())
		if 'chatgpt' in self.enabled_modules:
			await self.add_cog(ChatGPT(self,**self.config['modules']['chatgpt']['settings']),guild=self.guild_object())
		if 'simplechatgpt' in self.enabled_modules:
			await self.add_cog(SimpleChatGPT(self,**self.config['modules']['simplechatgpt']['settings']),guild=self.guild_object())
		if 'minecraft' in self.enabled_modules:
			await self.add_cog(Minecraft(self, **self.config['modules']['minecraft']['settings']),guild=self.guild_object())
		await self.add_cog(Manager(self),guild=self.guild_object())
		print('Загружены все расширения')

	async def on_ready(self):
		await self.wait_until_ready()
		if not self.synced:
			await self.tree.sync(guild = self.guild_object())
			self.synced = True
		print(f'Бот {self.user} был успешно подключен')
		
logging.getLogger('discord').setLevel(logging.ERROR)
logging.getLogger('discord.client').setLevel(logging.ERROR)
logging.getLogger('discord.gateway').setLevel(logging.ERROR)
logging.getLogger('discord.http').setLevel(logging.ERROR)
logging.getLogger('asyncmy').setLevel(logging.ERROR)
logging.getLogger('revChatGPT.V1').setLevel(logging.ERROR)
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)

bot = Bot("config.yml")