import discord, re, os, json, random
from discord import app_commands
from revChatGPT.V1 import Chatbot
import asyncio, functools, typing
from datetime import datetime
from manager import DiscordManager

def to_thread(func: typing.Callable) -> typing.Coroutine:
	@functools.wraps(func)
	async def wrapper(*args, **kwargs):
		loop = asyncio.get_event_loop()
		wrapped = functools.partial(func, *args, **kwargs)
		return await loop.run_in_executor(None, wrapped)
	return wrapper

class DiscordChatGPT:
	def __init__(self, bot, session_token: str, allowed_roles: [int,...], error_messages: [str,...]):
		self.bot = bot
		self.allowed_roles = allowed_roles
		self.error_messages = error_messages
		self.conversation_id = None
		self.chatgpt = Chatbot(config={ "session_token":session_token })

		self.blocked = False
		self.delayed_questions = {}
		self.last_answer_time = datetime.now().timestamp()
		self.last_answer_id = None
		async def message(message):
			if not self.conversation_id:
				try:
					await self.load_conversation()
				except:
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
				
				bot_id = self.bot.guild().get_member(self.bot.user.id).id
				async for msg in message.channel.history(limit=2):
					if msg.author.id != bot_id:
						continue
					if msg.id != self.last_answer_id:
						break
					if ((datetime.now().timestamp()-msg.created_at.timestamp())/150 > random.random() or random.random() > 0.5):
						break
					self.blocked = True
					async with message.channel.typing():
						try:
							for answer in self.single_answer(message,await self.get_answer(self.answer_after_message(message))):
								msg = await message.channel.send(content=answer)
							self.last_answer_time = msg.created_at.timestamp()
							self.last_answer_id = msg.id
						except:
							pass
					await self.process_delayed_questions(message.channel)
					self.blocked = False
					return

				if not ((datetime.now().timestamp()-self.last_answer_time)/3600 >= (0.2+(random.random()*0.8))):
					return 
				
				question = await self.random_trigger(message)
				if question:
					self.blocked = True
					async with message.channel.typing():
						try:
							for answer in self.process_random_trigger(await self.get_answer(question)):
								msg = await message.channel.send(content=answer)
							self.last_answer_time = msg.created_at.timestamp()
							self.last_answer_id = msg.id
						except:
							pass
					await self.process_delayed_questions(message.channel)
					self.blocked = False
				return
			if not bool(set(self.allowed_roles) & set([role.id for role in message.author.roles])):
				return
			
			if not self.blocked:
				self.blocked = True
				await self.process_single_question(message)
				await self.process_delayed_questions(message.channel)
				self.blocked = False
			else:
				self.add_delayed_question(message)

		self.message = message

		command_init = self.bot.language.commands['chatgpt_updateconversation']['init']
		@command_init.command(**self.bot.language.commands['chatgpt_updateconversation']['initargs'])
		async def command_chatgpt_updateconversation(interaction: discord.Interaction):
			await interaction.response.defer(ephemeral=True)
			try:
				await self.create_conversation()
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['chatgpt_updateconversation']['messages']['conversation-updated'])
			except:
				content, reference, embeds, view = DiscordManager.json_to_message(self.bot.language.commands['chatgpt_updateconversation']['messages']['error-on-conversation-update'])
			await interaction.followup.send(content=content,embeds=embeds,ephemeral=True)

	async def create_conversation(self):
		self.conversation_id = None
		await self.get_answer('Привет, сразу поясняю как будет работать наше общение. Тебя добавили в чат и будут присылать тебе сообщения пользователей  в формате:\nникнейм: сообщение\nИногда в начале запроса будут встречаться пояснения как тебе следует отвечать')
		self.conversation_id = self.chatgpt.conversation_id
		with open('chatgpt.json', 'w') as outfile:
			json.dump({'last_conversation':self.conversation_id}, outfile)
	async def load_conversation(self):
		if os.path.isfile("chatgpt.json"):
			with open('chatgpt.json') as json_file:
				data = json.load(json_file)
				if 'last_conversation' in data:
					self.conversation_id = data['last_conversation']
					return
		await self.create_conversation()

	@to_thread
	def get_answer(self,question):
		for data in self.chatgpt.ask(question,conversation_id = self.conversation_id):
			text = data["message"]
		return text

	def add_delayed_question(self,message):
		channel = message.channel.id
		user = message.author.name
		question = message.content.replace(self.bot.user.mention,"ChatGPT").replace('\n',' ')
		for member in message.mentions:
			question.replace(f'<@{member.id}>','@'+member.name)
		if channel in self.delayed_questions:
			if user in self.delayed_questions[channel]:
				self.delayed_questions[channel][user].append(question)
			else:
				self.delayed_questions[channel][user] = [question]
		else:
			self.delayed_questions[channel] = {user:[question]}
	def get_delayed_questions(self,channel: int):
		base = "Тебе будут предоставлены вопросы от нескольких пользователей, ответь на каждый из них, раздели свои ответы на них при помощи фразы '<split>'\n"
		questions = []
		for user in self.delayed_questions[channel].keys():
			questions.append(user+': '+' '.join(self.delayed_questions[channel][user]))
		del self.delayed_questions[channel]
		return base+'\n'.join(questions)	
	def delayed_answer(self, answer):
		answer = answer.replace("ChatGPT: ", "")
		return [self.process_length(part) for part in answer.split('<split>') if part != ""]
	async def process_delayed_questions(self, channel):
		if channel.id in self.delayed_questions:
			question = self.get_delayed_questions(channel.id)
			async with channel.typing():
				try:
					for answer in self.delayed_answer(await self.get_answer(question)):
						for part in answer:
							msg = await channel.send(content=part)
						await asyncio.sleep(random.random()*2.5)
					self.last_answer_time = msg.created_at.timestamp()
					self.last_answer_id = msg.id
				except:
					pass


	def single_question(self, message):
		return message.author.name + ': '+ message.content.replace(self.bot.user.mention,"ChatGPT")
	def single_answer(self, message, answer):
		answer = re.sub(f'@?{message.author.name}',f'<@{message.author.id}>', answer, flags=re.IGNORECASE)
		answer = answer.replace("ChatGPT: ", "")
		answer = ''.join([ans for ans in answer.split('<split>') if ans!=''])
		return self.process_length(answer)
	async def process_single_question(self, message):
		async with message.channel.typing():
			try:
				answers = self.single_answer(message,await self.get_answer(self.single_question(message)))
			except:
				await asyncio.sleep(random.random()*2.5)
				answers = [random.choice(self.error_messages)]
			i = 0
			for answer in answers:
				if i==0 and random.random() < 0.33:
					reference = discord.MessageReference(message_id=message.id, channel_id=message.channel.id)	
					msg = await message.channel.send(content=answer, reference=reference)
				else:
					msg = await message.channel.send(content=answer)
				i+=1
			self.last_answer_time = msg.created_at.timestamp()
			self.last_answer_id = msg.id
	async def random_trigger(self, message):
		base = "Сейчас тебе пришел запрос в котором диалог неескольких пользователей. Выдай какое-нибудь небольшое сообщение чтобы поддержать их диалог, сразу начни писать сообщение, не нужно писать 'да я могу это сделать' и тому подобные фразы и не используй кавычки в ответе. Вот сам диалог:\n"
		prev_author = None
		prev_author_nick = None
		questions = []
		question = []
		bot_id = self.bot.guild().get_member(self.bot.user.id).id
		
		users = []
		amount_messages = 0
		dead_time = datetime.now().timestamp() - 10*60
		async for msg in message.channel.history(limit=30):
			if msg.created_at.timestamp() < dead_time:
				break
			if msg.content == None:
				continue
			if not (msg.author in users):
				users.append(msg.author)
			amount_messages+=1

			content = msg.content.replace('\n',' ')
			for member in message.mentions:
				content.replace(f'<@{member.id}>','@'+member.name)
			
			if prev_author == None:
				prev_author = msg.author.id
				prev_author_nick = msg.author.name

			if prev_author == msg.author.id:
				question.append(content)
			else:
				if prev_author == bot_id:
					questions.append('ChatGPT: '+' '.join(reversed(question)))
				else:
					questions.append(prev_author_nick+': '+' '.join(reversed(question)))
				question = []
				prev_author = msg.author.id
				prev_author_nick = msg.author.name
				question.append(content)
		if prev_author == self.bot.user.id:
			questions.append('ChatGPT: '+' '.join(reversed(question)))
		else:
			questions.append(prev_author_nick+': '+' '.join(reversed(question)))
		
		if len(users)>=2 and amount_messages>=6:
			return base + ('\n'.join(reversed(questions))).replace(self.bot.user.mention,"ChatGPT")
		return None
	def process_random_trigger(self, answer):
		answer = answer.replace("ChatGPT: ", "")
		answer = ''.join(answer.split('<split>'))
		return self.process_length(answer)
	
	def answer_after_message(self,message):
		base = 'Это реакция пользователя на твой предыдущий ответ:\n'
		return base+self.single_question(message)

	def process_length(self,message: str):
		if len(message) > 1992:
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
		else:
			return [message]