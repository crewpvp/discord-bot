from json import loads
from jsonschema import validate
import sys, inspect

class wrongMethodExceptions(Exception):
	type = 'WRONG_METHOD'
	def __init__(self,message: str =  "Web server supports only GET or POST methods of request"):
		super().__init__(message)

class wrongPathException(Exception):
	type = 'WRONG_PATH'
	def __init__(self,message: str = "Path, what you specified doesn't exists"):
		super().__init__(message)

class wrongParamsException(Exception):
	type = 'WRONG_PARAMS'
	def __init__(self,message: str = "Some required params are missed"):
		super().__init__(message)

class playerNotFoundException(Exception):
	type = 'PLAYER_NOT_FOUND'
	def __init__(self,message: str = "Player, what you specified isn't online"):
		super().__init__(self,message)

class serverNotFoundException(Exception):
	type = 'SERVER_NOT_FOUND'
	def __init__(self,message: str = "Server, what you specified isn't exists"):
		self.message = message

class playerNotSpecified(Exception):
	type = 'PLAYER_NOT_SPECIFIED'
	def __init__(self,message: str = "Specify name of player for fetch in your request"):
		super().__init__(message)

class serverNotSpecified(Exception):
	type = 'SERVER_NOT_SPECIFIED'
	def __init__(self,message: str = "Specify name of server for fetch in your request"):
		super().__init__(message)

class serverIsOfflineException(Exception):
	type = 'SERVER_IS_OFFLINE'
	def __init__(self,message: str = "Server what you specified is offline"):
		super().__init__(message)

class connectionClosedException(Exception):
	type = 'CONNECTION_CLOSED'
	def __init__(self,message: str = "Can't read request body"):
		super().__init__(message)

class invalidJsonException(Exception):
	type = 'INVALID_JSON'
	def __init__(self,message: str = "Can't parse JSON"):
		super().__init__(message)

class invalidSignalJsonException(Exception):
	type = 'INVALID_SIGNAL_JSON'
	def __init__(self,message: str = "Can't parse JSON to SIGNALS, check docs and fix request body"):
		super().__init__(message)

class errorNotParsedException(Exception):
	type = 'ERROR_NOT_PARSED'
	def __init__(self,message: str = "Can't parse Error, try check updates for python api"):
		super().__init__(message)

def parseError(error: str|dict) -> Exception:
	schema = {
		"type": "object",
		"properties": {
			"error": {
				"type": "object",
				"properties": {
					"type": { "type": "string" },
					"message": { "type": "string" }
				},
				"required": ["type", "message"]
			}
		},
		"required": ["error"]
	}
	error = loads(error) if isinstance(error,str) else error
	validate(instance=error, schema=schema)
	error = error['error']
	for ex in [ex for name, ex in inspect.getmembers(sys.modules[__name__], inspect.isclass)]:
		if ex.type.lower() == error['type'].lower():
			return ex(error['message']) 
	return errorNotParsedException()

