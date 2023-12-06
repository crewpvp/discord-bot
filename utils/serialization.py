import discord, json

def message_to_json(message):
	msg = {}
	if message.content:
		msg['content'] = message.content
	if message.reference:
		msg['reference'] = {'message_id':message.reference.message_id}
	if message.embeds:
		msg['embeds'] = [embed.to_dict() for embed in message.embeds]
	if message.components:
		components = []
		for component in message.components:
			if isinstance(component , discord.Button):
				components.append({
						'custom_id':component.custom_id,
						'url': component.url,
						'label': component.label,
						'type': int(component.type),
						'style': int(component.style)
					})
			elif isinstance(component, discord.SelectMenu):
				options = [{'label': option.label,'value': option.value,'description': option.description} for option in component.options]
				components.append({
						'custom_id':component.custom_id,
						'placeholder': component.placeholder,
						'min_values': component.min_values,
						'max_values': component.max_values,
						'type': int(component.type),
						'options': options
					})
			elif isinstance(component, discord.ActionRow):
				childrens = []
				for children in component.children:
					if isinstance(children , discord.Button):
						childrens.append({
								'custom_id':children.custom_id,
								'url': children.url,
								'label': children.label,
								'type': int(children.type),
								'style': int(children.style)
							})
					elif isinstance(children, discord.SelectMenu):
						options = [{'label': option.label,'value': option.value,'description': option.description} for option in children.options]
						childrens.append({
								'custom_id':children.custom_id,
								'placeholder': children.placeholder,
								'min_values': children.min_values,
								'max_values': children.max_values,
								'type': int(children.type),
								'options': options
							})
				components.append({'type': int(component.type),'children': childrens})
		msg['components'] = components
	return json.dumps(msg,indent=1,ensure_ascii=False)	

def json_to_message(message: str):
	content, reference, embeds, view = None, None, [], None
	try:
		msg = json.loads(message)
		if 'content' in msg:
			content = msg['content']
		if 'reference' in msg:
			reference = msg['reference']
		if 'embeds' in msg:
			embeds = [discord.Embed.from_dict(embed) for embed in msg['embeds']]
		if 'components' in msg:
			view = discord.ui.View(timeout=None)
			for component in msg['components']:
				if component['type'] == 2:
					view.add_item(discord.ui.Button(disabled=False,url=component['url'],custom_id=component['custom_id'],label=component['label'],style=discord.ButtonStyle(component['style'])))
				elif component['type'] == 4:
					options = [discord.SelectOption(label=option['title'],value=option['value'],description=option['description']) for option in component['options']]
					view.add_item(discord.ui.Select(custom_id=component['custom_id'],placeholder=component['placeholder'],min_values=component['min_values'],max_values=component['max_values'],options=options))
				elif component['type'] == 1:
					for children in component['children']:
						if children['type'] == 2:
							view.add_item(discord.ui.Button(disabled=False,url=children['url'],custom_id=children['custom_id'],label=children['label'],style=discord.ButtonStyle(children['style'])))
						elif children['type'] == 4:
							options = [discord.SelectOption(label=option['title'],value=option['value'],description=option['description']) for option in children['options']]
							view.add_item(discord.ui.Select(custom_id=children['custom_id'],placeholder=children['placeholder'],min_values=children['min_values'],max_values=children['max_values'],options=options))


	except:
		pass
	return content, reference, embeds, view

def overwrites_to_json(overwrites):
	json_list = []
	for key in overwrites:
		if isinstance(key, discord.Role):
			pair = overwrites[key].pair()
			json_list.append({'type':0,'id':key.id,'allow':pair[0].value,'deny':pair[1].value})
		elif isinstance(key, discord.Member):
			pair = overwrites[key].pair()
			json_list.append({'type':1,'id':key.id,'allow':pair[0].value,'deny':pair[1].value})
	return json.dumps(json_list,indent=0,ensure_ascii=False)
	
def overwrites_from_json(guild: discord.Guild ,stored_overwrites: str):
	overwrites = {}
	for overwrite in json.loads(stored_overwrites):
		if overwrite['type']==0:
			subject = guild.get_role(overwrite['id'])
		else:
			subject = guild.get_member(overwrite['id'])
		if not subject:
			continue
		overwrites[subject] = discord.PermissionOverwrite.from_pair(discord.Permissions(permissions=overwrite['allow']),discord.Permissions(permissions=overwrite['deny']))
	return overwrites