# 📦 Built-in modules
import json
import os
from urllib.parse import quote

# 👾 Discord modules
import discord
from discord.ext import commands, tasks

# 🌐 Web modules
import aiohttp

# 📥 Custom modules
from Config import (
	EMBED_COLOR,
	CodexBaseUrl,
	CodexBranch,
	CodexChannelID,
	CodexMentionIDs,
	CodexPollInterval,
	CodexRepo,
	CodexStateFile,
)
from Utils.Logger import Logger

# 📚 The wiki pushes to this private mirror after every save, so a new commit
# there means someone edited a page. We poll GitHub instead of listening for a
# webhook: the bot has no inbound route, and edits happen a few times a day.
API_BASE = 'https://api.github.com'


def LoadState():
	if not os.path.exists(CodexStateFile):
		return {}
	try:
		with open(CodexStateFile, 'r') as File:
			return json.load(File)
	except json.JSONDecodeError:
		return {}


def SaveState(Data):
	with open(CodexStateFile, 'w') as File:
		json.dump(Data, File, indent=2)


def PageLink(Path: str):
	"""📄 Repository path -> wiki URL. Attachments have no page of their own."""
	if not Path.endswith('.md'):
		return None
	return f'{CodexBaseUrl}/{quote(Path[:-3])}'


def Fit(Lines, Limit):
	"""✂️ Keep whole lines within a Discord limit and say how many were dropped.

	Not cosmetic: an oversized embed is rejected with a 400, and the state only
	advances after a successful send — so one long round would stall the loop
	for good and retry the same rejected message forever.
	"""
	Kept, Used = [], 0
	for Index, Line in enumerate(Lines):
		Tail = f'… and {len(Lines) - Index} more'
		if Used + len(Line) + 1 > Limit - len(Tail) - 1:
			Kept.append(Tail)
			break
		Kept.append(Line)
		Used += len(Line) + 1
	return '\n'.join(Kept)


def BuildEmbed(Commits, Files):
	"""📝 One embed per round, not one per commit: a burst of small saves is one event."""
	Lines = []
	for Commit in Commits:
		Message = Commit['commit']['message'].splitlines()[0][:150]
		Author = Commit['commit']['author']['name']
		Lines.append(f'• {Message} — *{Author}*')

	Embed = discord.Embed(
		title='📚 Codex updated',
		description=Fit(Lines, 4096),
		color=EMBED_COLOR,
	)

	# 🔗 Renamed files carry their old name; show where the page lives now.
	Pages = []
	for File in Files:
		Link = PageLink(File['filename'])
		Name = File['filename'][:-3] if File['filename'].endswith('.md') else File['filename']
		Marker = {'added': '🆕 ', 'removed': '🗑️ '}.get(File['status'], '')
		Pages.append(f'{Marker}[{Name}]({Link})' if Link else f'{Marker}{Name}')
	if Pages:
		Embed.add_field(name='Pages', value=Fit(Pages, 1024), inline=False)

	Embed.set_footer(text=CodexBaseUrl.replace('https://', ''))
	return Embed


class Codex(commands.Cog):
	def __init__(self, Bot: commands.Bot) -> None:
		self.Bot = Bot
		self.Token = os.getenv('CODEX_GITHUB_TOKEN')
		self.Channel = None

	@commands.Cog.listener()
	async def on_ready(self):
		# 🔇 Missing token or channel disables the cog instead of erroring every
		# poll. The rest of the bot must not care whether the wiki is wired up.
		if not self.Token or not CodexChannelID or not CodexRepo:
			Logger.info('Codex: not configured, change notifications are off.')
			return
		self.Channel = self.Bot.get_channel(CodexChannelID)
		if not isinstance(self.Channel, discord.TextChannel):
			Logger.error(f'Codex: channel {CodexChannelID} not found, change notifications are off.')
			return
		if not self.PollLoop.is_running():
			self.PollLoop.start()

	async def cog_unload(self):
		self.PollLoop.cancel()

	async def Request(self, Session, Path):
		Headers = {
			'Authorization': f'Bearer {self.Token}',
			'Accept': 'application/vnd.github+json',
			'X-GitHub-Api-Version': '2022-11-28',
		}
		async with Session.get(f'{API_BASE}{Path}', headers=Headers) as Response:
			if Response.status != 200:
				return Response.status, None
			return Response.status, await Response.json()

	@tasks.loop(seconds=CodexPollInterval)
	async def PollLoop(self):
		try:
			State = LoadState()
			Last = State.get('last_sha')

			async with aiohttp.ClientSession() as Session:
				# 🥇 First run: remember where we are, do not replay the history.
				if not Last:
					Status, Data = await self.Request(
						Session, f'/repos/{CodexRepo}/commits?sha={CodexBranch}&per_page=1'
					)
					if Status != 200 or not Data:
						Logger.error(f'Codex: GitHub returned {Status} on the first poll.')
						return
					SaveState({'last_sha': Data[0]['sha']})
					Logger.info(f'Codex: starting from {Data[0]["sha"][:7]}.')
					return

				# 🔍 One request gives both the commits and the files they touched.
				Status, Data = await self.Request(
					Session, f'/repos/{CodexRepo}/compare/{Last}...{CodexBranch}'
				)

				# 🧭 404 means our sha is gone from the branch (force push, reset).
				# Re-anchor rather than retry the same broken compare forever.
				if Status == 404:
					Logger.error('Codex: last known commit is gone from the branch, re-anchoring.')
					SaveState({})
					return
				if Status != 200 or Data is None:
					Logger.error(f'Codex: GitHub returned {Status} while comparing.')
					return

			Commits = Data.get('commits', [])
			if not Commits:
				return

			# 🔔 The mention has to sit in the message text: a mention inside an
			# embed renders as a link and notifies nobody. allowed_mentions keeps
			# it to these two even if a commit message carries an @everyone.
			Mentions = ' '.join(f'<@{Id}>' for Id in CodexMentionIDs)
			await self.Channel.send(
				content=Mentions or None,
				embed=BuildEmbed(Commits, Data.get('files', [])),
				allowed_mentions=discord.AllowedMentions(
					users=True, roles=False, everyone=False
				),
			)
			SaveState({'last_sha': Commits[-1]['sha']})
		except Exception as Error:
			# 🛟 A poll that raises would stop the loop for good.
			Logger.error(f'Codex: poll failed: {Error}')

	@PollLoop.before_loop
	async def BeforePoll(self):
		await self.Bot.wait_until_ready()


async def setup(Bot: commands.Bot) -> None:
	await Bot.add_cog(Codex(Bot))


if __name__ == '__main__':
	# 🧪 `python -m Cogs.Codex` from the repo root — covers the two spots where
	# a mistake stays silent in production: the Discord length limits and the URLs.
	assert Fit(['a', 'b'], 1024) == 'a\nb'
	Long = [f'line {Index} ' + 'x' * 90 for Index in range(60)]
	assert len(Fit(Long, 1024)) <= 1024
	assert Fit(Long, 1024).splitlines()[-1].startswith('… and')
	assert PageLink('attachments/screenshot.png') is None
	assert PageLink('Do This/Add an Item.md').endswith('/Do%20This/Add%20an%20Item')
	print('Codex self-check ok')
