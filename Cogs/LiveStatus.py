# 📦 Built-in modules
import discord
import json
import os

# 📥 Custom modules
from Cogs.ServerStats import CreateStatusEmbed
from Config import (
	BotName,
	DefaultServer,
	DefaultServerPort,
	LiveStatusChannelID,
	LiveStatusUpdateInterval,
	LiveStatusFile,
)
from Utils.Socket import GetStatus

# 👾 Discord modules
from discord.ext import commands, tasks
from discord.ui import View, Button


# === Path to JSON file ===
LIVE_STATUS_FILE = LiveStatusFile


# === Helper functions for JSON persistence ===
async def load_live_status():
	if not os.path.exists(LIVE_STATUS_FILE):
		return {}
	try:
		with open(LIVE_STATUS_FILE, 'r') as f:
			return json.load(f)
	except json.JSONDecodeError:
		return {}


async def save_live_status(data):
	with open(LIVE_STATUS_FILE, 'w') as f:
		json.dump(data, f, indent=2)


class LiveStatusView(View):
	def __init__(self, CogInstance):
		super().__init__(timeout=None)
		self.CogInstance = CogInstance

	@discord.ui.button(
		label='Refresh',
		style=discord.ButtonStyle.grey,
		emoji='<:Refresh:1422932521049657457>',
	)
	async def RefreshButton(self, Interaction: discord.Interaction, Button: Button):
		await self.CogInstance.UpdateStatusMessage(Interaction)


class LiveStatus(commands.Cog):
	def __init__(self, Bot: commands.Bot) -> None:
		self.Bot = Bot
		self.StatusMessage = None
		self.Channel = None
		self.OriginalChannelName = None

	@commands.Cog.listener()
	async def on_ready(self):
		# Load persistent data
		status_data = await load_live_status()
		message_id = status_data.get('message_id')

		self.Channel = self.Bot.get_channel(LiveStatusChannelID)
		if self.Channel and isinstance(self.Channel, discord.TextChannel):
			# Save original channel name
			self.OriginalChannelName = self.Channel.name
			if message_id:
				try:
					# Try to fetch existing message
					self.StatusMessage = await self.Channel.fetch_message(message_id)
					# Update it
					await self.UpdateStatusMessage()
				except discord.NotFound:
					# Message not found, send new one
					await self.UpdateStatusMessage()
			else:
				# No saved message, send new one
				await self.UpdateStatusMessage()
		# 🔄 Start the update loop
		self.UpdateStatusLoop.start()

	@tasks.loop(seconds=LiveStatusUpdateInterval)
	async def UpdateStatusLoop(self):
		if self.Channel and self.StatusMessage:
			await self.UpdateStatusMessage()

	async def UpdateStatusMessage(self, Interaction=None):
		try:
			# 🌐 Fetch server status
			Status = GetStatus(DefaultServer, DefaultServerPort)
			Embed, File = CreateStatusEmbed(
				Status, DefaultServer, DefaultServerPort, BotName
			)

			# Update channel name based on status
			if self.Channel and isinstance(self.Channel, discord.TextChannel):
				new_name = '🟢-server-online' if Status else '🔴-server-offline'
				if self.Channel.name != new_name:
					try:
						await self.Channel.edit(name=new_name)
					except discord.Forbidden:
						pass  # No permission to edit channel name

			ViewInstance = LiveStatusView(self)

			if self.StatusMessage:
				# ✏️ Edit existing message
				if File:
					await self.StatusMessage.edit(
						embed=Embed, attachments=[File], view=ViewInstance
					)
				else:
					await self.StatusMessage.edit(embed=Embed, view=ViewInstance)
			else:
				# 📤 Send new message
				if isinstance(self.Channel, discord.TextChannel):
					if File:
						self.StatusMessage = await self.Channel.send(
							embed=Embed, file=File, view=ViewInstance, silent=True
						)
					else:
						self.StatusMessage = await self.Channel.send(
							embed=Embed, view=ViewInstance, silent=True
						)
					# Save message ID for persistence
					await save_live_status({'message_id': self.StatusMessage.id})
				else:
					# 🚫 Channel type does not support sending messages
					self.StatusMessage = None

			if Interaction:
				await Interaction.response.defer()
		except Exception:
			if Interaction:
				await Interaction.response.send_message('Failed to refresh status.', ephemeral=True)


async def setup(Bot: commands.Bot) -> None:
	await Bot.add_cog(LiveStatus(Bot))
