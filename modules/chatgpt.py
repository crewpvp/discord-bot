import discord, re, os, json, random
from discord import app_commands
from discord.ext import commands
from revChatGPT.V1 import Chatbot
import asyncio, functools, typing
from datetime import datetime

def to_thread(func: typing.Callable) -> typing.Coroutine:
	@functools.wraps(func)
	async def wrapper(*args, **kwargs):
		loop = asyncio.get_event_loop()
		wrapped = functools.partial(func, *args, **kwargs)
		return await loop.run_in_executor(None, wrapped)
	return wrapper

class ChatGPT(commands.Cog):
	def __init__(self, bot, allowed_roles: [int,...], error_messages: [str,...], conversation_intro: str, reference_chance: float, delayed_answers: {}, random_answers: {}, answer_after_message: {} ):
		self.bot = bot
		
		self.allowed_roles = allowed_roles
		self.error_messages = error_messages
		self.conversation_intro = conversation_intro
		self.reference_chance = reference_chance

		self.conversation_id = None
		self.access_token = None
		self.chatgpt = None

		self.blocked = False
		
		self.delayed_messages = []
		
		self.last_answer_time = datetime.now().timestamp()
		self.last_answer_id = None

		self.delayed_answers = delayed_answers
		self.random_answers = random_answers
		self.answer_after_message = answer_after_message
		
	@commands.Cog.listener()
	async def on_message(self, message: discord.Message):
		if not self.chatgpt and not self.load_data():
			return
		if self.bot.user == message.author:
			return
		if message.guild.id != self.bot.guild_id:
			return
		if not message.content:
			return
		if not (self.bot.user.mention in message.content):
			if self.blocked:
				return
			if (await self.reaction_answer_condition(message)):
				self.blocked = True
				await self.reaction_answer(message)
				if self.delayed_answers['enabled']:
					await self.process_delayed_questions()
				self.blocked = False
				return
			if (await self.random_answer_condition(message)):
				self.blocked = True
				await self.random_answer(message)
				if self.delayed_answers['enabled']:
					await self.process_delayed_questions()
				self.blocked = False
			return
		if self.blocked:
			if self.delayed_answers['enabled']:
				self.add_delayed_question(message)
		else:
			self.blocked = True
			await self.target_question(message)
			if self.delayed_answers['enabled']:
				await self.process_delayed_questions()
			self.blocked = False
	
	chatgpt_group = app_commands.Group(name='chatgpt', description='Менеджер настроек ChatGPT бота')
	chatgpt_update_group = app_commands.Group(name='update', parent=chatgpt_group, description='Обновление некоторых параметров ChatGPT')
	
	@chatgpt_update_group.command(name='conversation', description='создать новый чат, может решить проблему долгих ответов/не работы бота')
	async def chatgpt_update_conversation(self, interaction: discord.Interaction):
		await interaction.response.defer(ephemeral=True)
		self.blocked = True
		if not await self.create_conversation():
			embed = discord.Embed(description='Чат не был создан, возможно какие-то проблемы на стороне OpenAI, попробуйте позже',color=discord.Colour.red())
		else:
			embed = discord.Embed(description='Новый чат создан',color=discord.Colour.green())
		self.blocked = False
		await interaction.followup.send(embed=embed,ephemeral=True)
	
	@chatgpt_update_group.command(name='token', description='обновить токен бота')
	async def chatgpt_update_token(self, interaction: discord.Interaction, token: str):
		await interaction.response.defer(ephemeral=True)
		self.access_token = token
		self.chatgpt = Chatbot(config={ "access_token": self.access_token })
		if not self.conversation_id and not await self.create_conversation():
			embed = discord.Embed(description='Токен не был обновлен, проверьте что вы получили его [тут](https://chat.openai.com/api/auth/session)',color=discord.Colour.red())
		else:
			embed = discord.Embed(description='Токен успешно обновлен',color=discord.Colour.green())
			self.save_data()
		await interaction.followup.send(embed=embed,ephemeral=True)

	@to_thread
	def ask(self,question):
		for data in self.chatgpt.ask(question,conversation_id = self.conversation_id):
			text = data["message"]
		return text
	async def create_conversation(self):
		try:
			self.conversation_id = None
			await self.ask(self.conversation_intro)
			self.conversation_id = self.chatgpt.conversation_id
			self.save_data()
			return True
		except:
			return None

	def length_split(self,message: str):
		if len(message) < 1992:
			return [message]
		messages = []
		block = []
		l = 0
		code = False
		for part in message.split(' '):
			if '```' in part:
				code = False if code else True
			if l+len(part) < 1992:
				l+= len(part)+1
				block.append(part)
			else:
				if code:
					messages.append(' '.join(block)+'\n```')
				else:
					messages.append(' '.join(block))

				block = ['```\n'+part] if code else [part]  
				l = len(part)+1
		if code:
			messages.append(' '.join(block)+'\n```')
		else:
			messages.append(' '.join(block))
		return messages
	
	async def target_question(self, message):
		async with message.channel.typing():
			question = message.author.name + ': '+ message.content.replace(self.bot.user.mention,"ChatGPT")
			try:
				answer = await self.ask(question)
				answer = re.sub(f'@?{message.author.name}',f'<@{message.author.id}>', answer, flags=re.IGNORECASE)
				answer = re.sub(f'^chatgpt:',f'', answer, flags=re.IGNORECASE)
				answer_parts = self.length_split(answer)
			except:
				answer_parts = [random.choice(self.error_messages)]
			
			first = True
			for answer in answer_parts:
				if first and random.random() < self.reference_chance:
					first = False
					reference = discord.MessageReference(message_id=message.id, channel_id=message.channel.id)	
					answer_message = await message.channel.send(content=answer, reference=reference)
				else:
					answer_message = await message.channel.send(content=answer)
			
			self.last_answer_time = answer_message.created_at.timestamp()
			self.last_answer_id = answer_message.id
	
	async def reaction_answer(self,message):
		async with message.channel.typing():
			reaction = message.author.name + ': '+ message.content.replace(self.bot.user.mention,"ChatGPT")
			reaction = self.answer_after_message['intro'].format(reaction=reaction)
			try:
				answer = await self.ask(reaction)
			except:
				return
			answer = re.sub(f'@?{message.author.name}',f'<@{message.author.id}>', answer, flags=re.IGNORECASE)
			answer = re.sub(f'^chatgpt:',f'', answer, flags=re.IGNORECASE)
			answer_parts = self.length_split(answer)
			
			first = True
			for answer in answer_parts:
				if first and random.random() < self.reference_chance:
					first = False
					reference = discord.MessageReference(message_id=message.id, channel_id=message.channel.id)	
					answer_message = await message.channel.send(content=answer, reference=reference)
				else:
					answer_message = await message.channel.send(content=answer)
			
			self.last_answer_time = answer_message.created_at.timestamp()
			self.last_answer_id = answer_message.id
	async def reaction_answer_condition(self,message):
		if not self.answer_after_message['enabled']:
			return False
		if message.channel.id not in self.answer_after_message['allowed_channels']:
			return False
		first = True
		async for msg in message.channel.history(limit=2):
			if first:
				first = False
				continue
			if msg.author != self.bot.user:
				return False
			if random.random() > self.answer_after_message['chance']:
				return False
			time_delta = message.created_at.timestamp() - msg.created_at.timestamp()
			if self.answer_after_message['time_priority']:
				chance = 1 - (time_delta/self.answer_after_message['time_to_answer'])
			else:
				chance = self.answer_after_message['time_to_answer'] - time_delta
			if random.random() > chance:
				return False
		else:
			return False
		return True

	async def process_delayed_questions(self):
		messages = self.delayed_messages
		self.delayed_messages = []
		messages_content = []
		messages_indexes = []

		for i in range(len(messages)):
			try:
				message = await messages[i].fetch()
				question = message.content.replace(self.bot.user.mention,"ChatGPT")
				question = message.author.name + ': '+ question.replace('<question>','')
				messages_content.append(question)
				messages_indexes.append(i)
			except:
				pass
		questions = '\n<question>'.join(messages_content)
		questions = self.delayed_answers['intro'].format(questions=questions)

		if not messages_content:
			return

		async with message.channel.typing():
			try:
				answers = await self.ask(questions)
			except:
				return
			answers = answers.split(self.delayed_answers['delimiter'])
			amount_questions = len(messages_indexes)
			for i in range(len(answers)):
				if i < amount_questions:
					message = messages[messages_indexes[i]]
					answer = answers[i]
					answer = re.sub(f'@?{message.author.name}',f'<@{message.author.id}>', answer, flags=re.IGNORECASE)
					answer = re.sub(f'^chatgpt:',f'', answer, flags=re.IGNORECASE)
					answer_parts = self.length_split(answer)
					
					first = True
					for answer in answer_parts:
						if first and random.random() < self.reference_chance:
							first = False
							reference = discord.MessageReference(message_id=message.id, channel_id=message.channel.id)	
							answer_message = await message.channel.send(content=answer, reference=reference)
						else:
							answer_message = await message.channel.send(content=answer)

		self.last_answer_time = answer_message.created_at.timestamp()
		self.last_answer_id = answer_message.id
	def add_delayed_question(self,message):
		self.delayed_messages.append(message)

	async def random_answer(self,message):
		if datetime.now().timestamp()-self.last_answer_time < self.random_answers['cooldown']:
			return
		if random.random() > self.random_answers['chance']:
			return
		authors = []
		first = None
		dialog = []
		async for msg in message.channel.history(limit=self.random_answers['max_messages']):
			if msg.author == self.bot.user:
				break
			if not first:
				first = msg.created_at.timestamp()
			if first - msg.created_at.timestamp() > self.random_answers['threshold']:
				break
			if msg.author not in authors:
				authors.append(msg.author)
			dialog.append(msg.author.name + ': '+ msg.content.replace(self.bot.user.mention,"ChatGPT"))
		if len(authors) < self.random_answers['min_users']:
			return
		if len(dialog) < self.random_answers['min_messages']:
			return
		dialog = '\n'.join(dialog)
		dialog = self.random_answers['intro'].format(dialog=dialog)
		async with message.channel.typing():
			try:
				answer = await self.ask(dialog)
			except:
				return
		for author in authors:
			answer = re.sub(f'@?{author.name}',f'<@{author.id}>', answer, flags=re.IGNORECASE)
		answer = re.sub(f'^chatgpt:',f'', answer, flags=re.IGNORECASE)
		answer_parts = self.length_split(answer)

		for answer in answer_parts:
			answer_message = await message.channel.send(content=answer)
			
		self.last_answer_time = answer_message.created_at.timestamp()
		self.last_answer_id = answer_message.id
	async def random_answer_condition(self,message):
		if not self.random_answers['enabled']:
			return False
		if message.channel.id not in self.random_answers['allowed_channels']:
			return False
		return True
	
	def save_data(self):
		with open('chatgpt.json', 'w') as outfile:
			json.dump({'last-conversation':self.conversation_id,'access-token':self.access_token}, outfile)
	def load_data(self):
		if os.path.isfile("chatgpt.json"):
			with open('chatgpt.json') as json_file:
				data = json.load(json_file)
				self.access_token = data['access-token']
				self.conversation_id = data['last-conversation']
				self.chatgpt = Chatbot(config={ "access_token": self.access_token })
				return True
		return None
