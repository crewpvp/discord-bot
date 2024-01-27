from .datatypes import Server, Player, Signal
from .exceptions import parseError
import aiohttp
from json import dumps

class api:
	def __init__(self, host: str, login: str, password: str):
		self.host = host
		self.auth = aiohttp.BasicAuth(login, password)

	async def servers(self, online: bool = True) -> [Server]:
		async with aiohttp.ClientSession() as session:
			params = {'online':str(online).lower()}
			async with session.get(url=self.host+'/servers',auth=self.auth,params=params) as response:
				if response.status == 200:
					return [Server.from_json(server) for server in (await response.json())['data']]
				else:
					raise parseError(await response.json())

	async def server(self, server: str|Server) -> Server:
		async with aiohttp.ClientSession() as session:
			server = server.name if isinstance(server,Server) else server
			async with session.get(url=self.host+'/server/'+server,auth=self.auth) as response:
				if response.status == 200:
					return Server.from_json((await response.json())['data'])
				else:
					raise parseError(await response.json())

	async def players(self, servers: [str|Server] = []) -> [Player]:
		async with aiohttp.ClientSession() as session:
			params = []
			for server in servers:
				params.append(server.name if isinstance(server,Server) else server)
			async with session.get(url=self.host+f'/players',auth=self.auth, params=params) as response:
				if response.status == 200:
					return [Player.from_json(player) for player in (await response.json())['data']]
				else:
					raise parseError(await response.json()) 
	
	async def player(self, player: str|Player) -> Player:
		async with aiohttp.ClientSession() as session:
			player = player.uuid if isinstance(player,Player) else player
			async with session.get(url=self.host+'/players/'+player,auth=self.auth) as response:
				if response.status == 200:
					return Player.from_json((await response.json())['data'])
				else:
					raise parseError(await response.json())
	
	async def kick(self, player: str|Player, reason: str|dict = ""):
		async with aiohttp.ClientSession() as session:
			player = player.uuid if isinstance(player,Player) else player
			async with session.post(url=self.host+'/players/'+player+'/kick',auth=self.auth, data=dumps(reason,ensure_ascii=False)) as response:
				if response.status != 200:
					raise parseError(await response.json())

	async def connect(self, player: str|Player, server: str|Server):
		async with aiohttp.ClientSession() as session:
			player = player.uuid if isinstance(player,Player) else player
			server = server.name if isinstance(server,Server) else server
			async with session.get(url=self.host+'/players/'+player+'/connect/'+server,auth=self.auth) as response:
				if response.status != 200:
					raise parseError(await response.json())

	async def signals(self, signals: [dict|str|Signal], servers: [str|Server]):
		async with aiohttp.ClientSession() as session:
			servers = [server.name if isinstance(server,Server) else server for server in servers]
			signals = [signal.to_dict() if isinstance(signal,Signal) else Signal.from_json(signal).to_dict() for signal in signals]
			data = {'servers': servers, 'signals': signals}
			async with session.post(url=self.host+'/signal',auth=self.auth, data=dumps(data,ensure_ascii=False)) as response:
				if response.status != 200:
					raise parseError(await response.json())