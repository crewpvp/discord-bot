import asyncmy

class cursor_context_manager:
	def __init__(self,pool_generator):
		self.pool_generator = pool_generator

	async def __aenter__(self):
		try:
			self.connection = await self.pool_generator.connection_pool.acquire()
			self.cursor = self.connection.cursor()
		except:
			await self.pool_generator.new_connection_pool()
			self.connection = await self.pool_generator.connection_pool.acquire()
			self.cursor = self.connection.cursor()
		return self.cursor

	async def __aexit__(self, exc_type, exc, tb):
		await self.cursor.close()
		self.pool_generator.connection_pool.release(self.connection)

class Connector:
	def __init__(self,database: str, password: str, user: str, host: str, port: int):
		self.database = database
		self.password = password
		self.user = user
		self.host = host
		self.port = port
		self.connection_pool = None
	
	def get_cursor(self):
		return cursor_context_manager(self)

	async def new_connection_pool(self):
		while not self.connection_pool:
			try:
				self.connection_pool = await asyncmy.create_pool(database=self.database,password=self.password,user=self.user,host=self.host,port=self.port, autocommit=True)
			except:
				print("Невозможно подключиться в БД, повтор через 5 секунд")
				asyncio.sleep(5)

