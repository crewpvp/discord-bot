from json import loads, dumps
from jsonschema import validate

class Signal:
	schema = {
	    "type": "object",
	    "properties": {
	        "key": {"type": "string"},
	        "data": {
	            "type": "array",
	            "items": {"type": ["number","string"]}
	        }
	    },
	    "required": ["key","data"]
	}

	@staticmethod
	def from_json(json: str|dict) -> 'Signal':
		json = loads(json) if isinstance(json,str) else json
		validate(instance=json, schema=Signal.schema)
		return Signal(**json)

	def __init__(self, key: str, data: [str|int|float]):
		self.key = key
		self.data = data
	
	def to_dict(self) -> dict:
		return {'key': self.key, 'data': self.data}
	
	def to_json(self) -> str:
		return dumps(self.to_dict(),indent=1,ensure_ascii=False)

	def __str__(self):
		return str(self.to_dict())

class Player:
	schema = {
	    "type": "object",
	    "properties": {
	        "name": {"type": "string"},
	        "uuid": {"type": "string"},
	        "join_date": {"type": "integer"},
	        "time_played": {"type": "integer"},
	        "server_name": {"type": "string"},
	        "server": {"$ref": "#/definitions/server"}
	    },
	    "required": ["name", "uuid", "join_date", "time_played", "server_name"],
	    "definitions": {
	        "server": {
	            "type": "object",
			    "properties": {
			        "name": {"type": "string"},
			        "address": {"type": "string"},
			        "port": {"type": "integer"},
			        "hostname": {"type": "string"},
			        "online": {"type": "boolean"},
			        "connection_date": {"type": "integer"},
			        "uptime": {"type": "integer"},
			        "players_count": {"type": "integer"},
			        "players": {
			            "type": "array",
			            "items": {"$ref": "#/definitions/player"}
			        }
			    },
			    "required": ["name", "address", "port", "hostname", "online", "connection_date", "uptime", "players_count", "players"]
	        },
	        "player": {
	            "type": "object",
			    "properties": {
			        "name": {"type": "string"},
			        "uuid": {"type": "string"},
			        "join_date": {"type": "integer"},
			        "time_played": {"type": "integer"},
			        "server_name": {"type": "string"}
			    },
			    "required": ["name", "uuid", "join_date", "time_played", "server_name"]
	        }
	    }
	}
	
	@staticmethod
	def from_json(json: str|dict) -> 'Player':
		json = loads(json) if isinstance(json,str) else json
		validate(instance=json, schema=Player.schema)
		json['server'] = Server.from_json(json['server']) if "server" in json else None 
		return Player(**json)

	def __init__(self, name: str, uuid: str, join_date: int, time_played: int, server_name: str, server = None):
		self.name = name
		self.uuid = uuid
		self.join_date = join_date
		self.time_played = time_played
		self.server_name = server_name
		self.server = server
	
	def to_dict(self) -> dict:
		if self.server:
			return {'name': self.name, 'uuid': self.uuid, 'join_date': self.join_date, 'time_played': self.time_played, 'server_name': self.server_name, 'server': self.server.to_dict()}
		else:
			return {'name': self.name, 'uuid': self.uuid, 'join_date': self.join_date, 'time_played': self.time_played, 'server_name': self.server_name}
	
	def to_json(self) -> str:
		return dumps(self.to_dict(),indent=1,ensure_ascii=False)

	def __str__(self):
		return str(self.to_dict())

class Server:
	schema = {
	    "type": "object",
	    "properties": {
	        "name": {"type": "string"},
	        "address": {"type": "string"},
	        "port": {"type": "integer"},
	        "hostname": {"type": "string"},
	        "online": {"type": "boolean"},
	        "connection_date": {"type": "integer"},
	        "uptime": {"type": "integer"},
	        "players_count": {"type": "integer"},
	        "players": {
	            "type": "array",
	            "items": {"$ref": "#/definitions/player"}
	        }
	    },
	    "required": ["name", "address", "port", "hostname", "online", "connection_date", "uptime", "players_count", "players"],
	    "definitions": {
	        "player": {
	            "type": "object",
			    "properties": {
			        "name": {"type": "string"},
			        "uuid": {"type": "string"},
			        "join_date": {"type": "integer"},
			        "time_played": {"type": "integer"},
			        "server_name": {"type": "string"}
			    },
			    "required": ["name", "uuid", "join_date", "time_played", "server_name"]
	        }
	    }
	}
	
	@staticmethod
	def from_json(json: str|dict) -> 'Server':
		json = loads(json) if isinstance(json,str) else json
		validate(instance=json, schema=Server.schema)
		json['players'] = [Player.from_json(player) for player in json['players']]
		return Server(**json)

	def __init__(self, name: str, address: str, port: int, hostname: str, online: bool, connection_date: int, uptime: int, players_count: int, players: []):
		self.name = name
		self.address = address
		self.port = port
		self.hostname = hostname
		self.online = online
		self.connection_date = connection_date
		self.uptime = uptime
		self.players_count = players_count
		self.players = players

	def to_dict(self) -> dict:
		players = [player.to_dict() for player in self.players]
		return {'name': self.name, 'address': self.address, 'port': self.port, 'hostname': self.hostname, 'online': self.online, 'connection_date': self.connection_date, 'uptime': self.uptime, 'players_count': self.players_count, 'players': players}
	
	def to_json(self) -> str:
		return dumps(self.to_dict(),indent=1,ensure_ascii=False)

	def __str__(self):
		return str(self.to_dict())