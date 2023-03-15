import aiohttp

class MinecraftWebAPI:
  def __init__(self, host: str, login: str, password: str):
    self.host = host
    self.auth = aiohttp.BasicAuth(login, password)

  async def get_servers(self, online: bool = True) -> tuple[str,...] | None:
    async with aiohttp.ClientSession() as session:
      params = {'online':str(online).lower()}
      try:
        async with session.get(url=self.host+'/servers',auth=self.auth,params=params) as response:
          return await response.json()
      except:
        return None
  
  async def fetch_player(self, nick: str) -> str | None:
    async with aiohttp.ClientSession() as session:
      try:
        async with session.get(url=self.host+f'/player/{nick}',auth=self.auth) as response:
          return await response.json() if response.status == 200 else None
      except:
        return None

  async def get_players(self, *servers: str) ->  tuple[str,...] | None:
    async with aiohttp.ClientSession() as session:
      try:
        params = {'server':servers} if servers else None
        async with session.get(url=self.host+f'/players',auth=self.auth, params=params) as response:
          return await response.json() if response.status == 200 else None
      except:
        return None

  async def send_command(self, server:str, command: str) -> bool:
    async with aiohttp.ClientSession() as session:
      try:
        async with session.get(url=self.host+f'/server/{server}/command?{command}',auth=self.auth) as response:
          return True if response.status==200 else False 
      except:
        return False
  
  async def send_signal(self, server: str,key: str, value: str = None) -> bool:
    async with aiohttp.ClientSession() as session:
      try: 
        if value:
          resp = await session.get(url=self.host+f'/server/{server}/signal?key={key}&value={value}',auth=self.auth)
        else:
          resp = await session.get(url=self.host+f'/server/{server}/signal?key={key}',auth=self.auth)
        return True if resp.status==200 else False 
      except:
        return False