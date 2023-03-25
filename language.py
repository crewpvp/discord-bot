from discord import app_commands

class DiscordLanguage():
	instance = None
    

	def __init__(self,bot,language):
		self.bot = bot
		self.language = language
		self.messages = language['messages'] if 'messages' in language else {}
		self.create_groups()
		self.create_commands()
		DiscordLanguage.instance = self

	def create_groups(self):
		self.groups = {}
		if 'command_groups' in self.language:
			command_groups = self.language['command_groups']
			for group_name in command_groups.keys():
				group_description = command_groups[group_name]
				self.groups[group_name] = app_commands.Group(name=group_name, description=group_description) 

	def register_groups(self):
		guild = self.bot.guild_object()
		for group in self.groups.values():
			self.bot.tree.add_command(group, guild = guild)

	def create_commands(self):
		self.commands = {}
		if 'commands' in self.language:
			commands = self.language['commands']
			for command_name in commands.keys():
				command = commands[command_name]
				self.commands[command_name] = {}
				if 'group' in command and command['group'] in self.groups:
					self.commands[command_name]['init'] = self.groups[command['group']]
					self.commands[command_name]['initargs'] = {'name':command['name'],'description':command['description']}
				else:
					self.commands[command_name]['init'] = self.bot.tree
					self.commands[command_name]['initargs'] = {'name':command['name'],'description':command['description'],'guild':self.bot.guild_object()}	
				
				self.commands[command_name]['describe'] = {}
				self.commands[command_name]['rename'] = {}
				self.commands[command_name]['choices'] = {}
				self.commands[command_name]['autocomplete'] = {}
				if 'arguments' in command:
					for argument_name in command['arguments'].keys():
						argument = command['arguments'][argument_name]
						if 'describe' in argument:
							self.commands[command_name]['describe'][argument_name] = argument['describe']
						if 'rename' in argument:
							self.commands[command_name]['rename'][argument_name] = argument['rename']
						if 'choices' in argument:
							choices = []
							for choice_name in argument['choices']:
								choice = argument['choices'][choice_name]
								choices.append(app_commands.Choice(name=choice_name, value=choice))
							self.commands[command_name]['choices'][argument_name] = choices
						if 'autocomplete' in argument:
							autocompletes = []
							for value in argument['autocomplete']:
								autocompletes.append(app_commands.Choice(name=value, value=value))
							self.commands[command_name]['autocomplete'][argument_name] = lambda interaction,current: [autocomplete for autocomplete in autocompletes if current.lower() in autocomplete.name.lower()]
				self.commands[command_name]['messages'] = command['messages'] if 'messages' in command else {}

	@staticmethod
	def command(func):
		command = DiscordLanguage.instance.commands[func.__name__]
		return command['init'].command(**command['initargs'])(
			app_commands.describe(**command['describe'])(
				app_commands.rename(**command['rename'])(
					app_commands.choices(**command['choices'])(
						func)
					)
				)
			)