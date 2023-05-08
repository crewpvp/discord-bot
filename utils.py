#функции для вывода времени в нормальном формате
def numberWordFormat(number: int, titles: list):
	cases = [ 2, 0, 1, 1, 1, 2 ]
	if 4 < number % 100 < 20:
		idx = 2
	elif number % 10 < 5:
		idx = cases[number % 10]
	else:
		idx = cases[5]

	return titles[idx]

def relativeTimeParser(seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0, years: int = 0, greater: bool = False):
	result = []
	time = seconds+(minutes*60)+(hours*3600)+(days*86400)+(years*31536000)
	if time >= 31536000:
		ttime = round(time/31536000)
		time = time%31536000
		result.append(str(ttime)+' '+numberWordFormat(ttime,['год','года','лет']))
		if greater:
			return result[0]
	if time >= 86400:
		ttime = round(time/86400)
		time = time%86400
		result.append(str(ttime)+' '+numberWordFormat(ttime,['день','дня','дней']))
		if greater:
			return result[0]
	if time >= 3600:
		ttime = round(time/3600)
		time = time%3600
		result.append(str(ttime)+' '+numberWordFormat(ttime,['час','часа','часов']))
		if greater:
			return result[0]
	if time >= 60:
		ttime = round(time/60)
		time = time%60
		result.append(str(ttime)+' '+numberWordFormat(ttime,['минута','минуты','минут']))
		if greater:
			return result[0]
	if time>0 or (time==0 and len(result)==0):
		time = round(time)
		result.append(str(time)+' '+numberWordFormat(time,['секунда','секунды','секунд']))
	return ' '.join(result)

