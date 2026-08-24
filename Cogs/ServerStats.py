# 📦 Built-in modules
import base64
import io
import socket
import time

# 📥 Custom modules
from Config import DefaultServer, DefaultServerPort
from Utils.Socket import GetStatus
from Utils.Plan import PlanAPI

# ⚙️ Settings
from Config import (
	BotName,
)

# 👾 Discord modules
from discord.ui import View, Button
from discord.ext import commands
import discord


# 💡 Strip Minecraft color codes (e.g., §a, §l)
def StripColorCodes(Text: str) -> str:
	Out = []
	_ = 0
	while _ < len(Text):
		if Text[_] == '§' and _ + 1 < len(Text):
			_ += 2
			continue
		Out.append(Text[_])
		_ += 1
	return ''.join(Out)


# 💡 Format the "description" field from status JSON
def FormatDescription(Desc) -> str:
	if isinstance(Desc, str):
		return StripColorCodes(Desc)
	if isinstance(Desc, dict):
		Text = Desc.get('text', '')
		Extra = Desc.get('extra', [])
		Parts = [Text]
		for E in Extra:
			Parts.append(FormatDescription(E))
		return StripColorCodes(''.join(Parts)).strip()
	return ''


# 💡 Measure latency (ping) to the server
def MeasureLatency(Host: str, Port: int) -> float | None:
	try:
		StartTime = time.time()
		Sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		Sock.settimeout(5)  # Timeout after 5 seconds
		Sock.connect((Host, Port))
		Sock.close()
		EndTime = time.time()
		return (EndTime - StartTime) * 1000  # Convert to milliseconds
	except Exception:
		return None


# 💡 Get emoji based on latency
def GetPingEmoji(Latency: float | None) -> str:
	if Latency is None:
		return '<:Ping0:1422932936445005876>'  # No connection
	elif Latency > 500:
		return '<:Ping1:1422932999401639937>'  # Extremely high
	elif Latency > 400:
		return '<:Ping2:1422933063759036578>'
	elif Latency > 300:
		return '<:Ping3:1422933085212770324>'
	elif Latency > 200:
		return '<:Ping4:1422933101138546688>'
	elif Latency > 100:
		return '<:Ping5:1422933118930780291>'
	else:
		return '<:Ping6:1422933134407897119>'  # Low ping


# 💡 Get emoji based on change from 30d to 24h (increase/decrease)
def GetChangeEmoji(Current: str, Previous: str, IsIncreaseGood: bool = True) -> str:
	# 📊 Parse values to floats
	def ParseVal(Val: str) -> float | None:
		Val = Val.strip()
		if '%' in Val:
			return float(Val.replace('%', ''))
		if 'GB' in Val:
			return float(Val.replace('GB', ''))
		if 'd' in Val or 'h' in Val or 'm' in Val or 's' in Val:
			# Parse downtime: e.g., "6d 20h 43m 34s" -> seconds
			Parts = (
				Val.replace('d', ' ').replace('h', ' ').replace('m', ' ').replace('s', '').split()
			)
			Seconds = 0.0
			if len(Parts) >= 1:
				Seconds += float(Parts[0]) * 86400  # days
			if len(Parts) >= 2:
				Seconds += float(Parts[1]) * 3600  # hours
			if len(Parts) >= 3:
				Seconds += float(Parts[2]) * 60  # minutes
			if len(Parts) >= 4:
				Seconds += float(Parts[3])  # seconds
			return Seconds
		try:
			return float(Val)
		except ValueError:
			return None

	CurrentVal = ParseVal(Current)
	PrevVal = ParseVal(Previous)
	if CurrentVal is None or PrevVal is None:
		return ''

	IsIncrease = CurrentVal > PrevVal
	if IsIncreaseGood:
		# For good metrics (e.g., TPS, players), increase is good, decrease is bad
		return (
			'<:GreenIncrease:1422935980817645648>'
			if IsIncrease
			else '<:RedDecrease:1422932924474331266>'
		)
	else:
		# For bad metrics (e.g., CPU, RAM, downtime), increase is bad, decrease is good
		return (
			'<:RedIncrease:1422932680168837151>'
			if IsIncrease
			else '<:GreenDecrease:1422932666734612481>'
		)


# 💡 Create status embed and file from server data
def CreateStatusEmbed(
	Status, Host: str, Port: int, BotName: str
) -> tuple[discord.Embed, discord.File | None]:
	# 📊 Format the response as an embed
	Version = Status.get('version', {}).get('name', 'Unknown')
	PlayersOnline = Status.get('players', {}).get('online', 0)
	PlayersMax = Status.get('players', {}).get('max', 0)
	Description = FormatDescription(Status.get('description', '')) or 'No description'
	FaviconUrl = Status.get('favicon')

	# 📡 Measure latency
	Latency = MeasureLatency(Host, Port)
	PingEmoji = GetPingEmoji(Latency)
	LatencyText = f'{Latency:.0f}ms' if Latency is not None else 'Offline'

	Embed = discord.Embed(
		title=f'Minecraft Server Status for {Host}:{Port}',
		timestamp=discord.utils.utcnow(),
		color=0xA0D6B4,
	)
	Embed.description = f"""
	Version: `{Version}` <:Version:1422932471770644580>
	Players: `{PlayersOnline}/{PlayersMax}` <:Player:1422932487868383322>
	Latency: `{LatencyText}` {PingEmoji}
	Description: ```{Description}```
	"""

	# 🖼️ Add server logo if available
	File = None
	if FaviconUrl and ',' in FaviconUrl:
		# Decode base64 and create file attachment
		Base64Data = FaviconUrl.split(',', 1)[1]
		ImageData = base64.b64decode(Base64Data)
		ImageBuffer = io.BytesIO(ImageData)
		ImageBuffer.seek(0)
		File = discord.File(ImageBuffer, 'favicon.png')
		Embed.set_thumbnail(url='attachment://favicon.png')
	Embed.set_footer(text=BotName)
	return Embed, File


class Minecraft(commands.Cog):
	def __init__(self, Bot: commands.Bot) -> None:
		self.Bot = Bot
		self.PlanAPI = PlanAPI()

	@commands.hybrid_command(
		name='mcstatus',
		description='Get Minecraft server status',
		aliases=['status', 'online', 'server'],
	)
	async def MCStatus(
		self, ctx: commands.Context, host: str | None = None, port: int = 25565
	) -> None:
		if host is None:
			host = DefaultServer
		if port == 25565 and host == DefaultServer:
			port = DefaultServerPort
		try:
			# 🌐 Fetch server status
			Status = GetStatus(host, port)
			Embed, File = CreateStatusEmbed(Status, host, port, BotName)

			# 🔄 Create and attach the refresh view
			ViewInstance = RefreshView(host, port, BotName)

			if File:
				await ctx.send(embed=Embed, file=File, view=ViewInstance)
			else:
				await ctx.send(embed=Embed, view=ViewInstance)
		except Exception:
			Embed = discord.Embed(
				title='Error',
				timestamp=discord.utils.utcnow(),
				description='Failed to fetch server status',
				color=0xF5A3A3,
			)
			Embed.set_footer(text=BotName)
			await ctx.send(embed=Embed)

	@commands.hybrid_command(
		name='mcperf',
		description='Get Minecraft server performance overview',
		aliases=['perf', 'performance'],
	)
	async def MCPerf(self, ctx: commands.Context) -> None:
		ServerUUID = self.PlanAPI.Env.get('PLAN_SERVER_UUID')
		if not ServerUUID:
			Embed = discord.Embed(
				title='Error',
				timestamp=discord.utils.utcnow(),
				description='Environment variables are missing',
				color=0xF5A3A3,
			)
			Embed.set_footer(text=BotName)
			await ctx.send(embed=Embed)
			return
		PerfData = self.PlanAPI.GetPerformanceOverview(ServerUUID)
		if not PerfData or 'numbers' not in PerfData:
			Embed = discord.Embed(
				title='Error',
				timestamp=discord.utils.utcnow(),
				description='Failed to fetch performance data',
				color=0xF5A3A3,
			)
			Embed.set_footer(text=BotName)
			await ctx.send(embed=Embed)
			return
		Numbers = PerfData['numbers']
		Embed = discord.Embed(
			title='Server Performance Overview',
			timestamp=discord.utils.utcnow(),
			color=0xA0D6B4,
		)
		Embed.description = f"""
		TPS: `{Numbers.get('tps_24h', 'N/A')}` {GetChangeEmoji(Numbers.get('tps_24h', ''), Numbers.get('tps_30d', ''), True)}
		Downtime: `{Numbers.get('server_downtime_24h', 'N/A')}` {GetChangeEmoji(Numbers.get('server_downtime_24h', ''), Numbers.get('server_downtime_30d', ''), False)}
		CPU: `{Numbers.get('cpu_24h', 'N/A')}` {GetChangeEmoji(Numbers.get('cpu_24h', ''), Numbers.get('cpu_30d', ''), False)}
		RAM: `{Numbers.get('ram_24h', 'N/A')}` {GetChangeEmoji(Numbers.get('ram_24h', ''), Numbers.get('ram_30d', ''), False)}
		Entities: `{Numbers.get('entities_24h', 'N/A')}` {GetChangeEmoji(Numbers.get('entities_24h', ''), Numbers.get('entities_30d', ''), False)}
		Chunks: `{Numbers.get('chunks_24h', 'N/A')}` {GetChangeEmoji(Numbers.get('chunks_24h', ''), Numbers.get('chunks_30d', ''), False)}
		Players: `{Numbers.get('players_24h', 'N/A')}` {GetChangeEmoji(Numbers.get('players_24h', ''), Numbers.get('players_30d', ''), True)}
		"""
		Embed.set_footer(text=BotName)
		await ctx.send(embed=Embed)


class RefreshView(View):
	def __init__(self, Host: str, Port: int, BotName: str):
		super().__init__(timeout=None)
		self.Host = Host
		self.Port = Port
		self.BotName = BotName

	@discord.ui.button(
		label='Refresh', style=discord.ButtonStyle.grey, emoji='<:Refresh:1422932521049657457>'
	)
	async def RefreshButton(self, interaction: discord.Interaction, button: Button):
		try:
			# 🌐 Re-fetch server status
			Status = GetStatus(self.Host, self.Port)
			Embed, File = CreateStatusEmbed(Status, self.Host, self.Port, self.BotName)
			await interaction.response.edit_message(embed=Embed, view=self)
		except Exception:
			ErrorEmbed = discord.Embed(
				title='Error',
				timestamp=discord.utils.utcnow(),
				description='Failed to fetch server status',
				color=0xF5A3A3,
			)
			ErrorEmbed.set_footer(text=self.BotName)
			await interaction.response.edit_message(embed=ErrorEmbed, view=self)


async def setup(Bot: commands.Bot) -> None:
	await Bot.add_cog(Minecraft(Bot))
