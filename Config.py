# 📦 Built-in modules
import logging
import os

# Load .env file manually for BOT_TYPE detection
try:
	with open('.env', 'r') as f:
		for line in f:
			if '=' in line and not line.strip().startswith('#'):
				key, value = line.strip().split('=', 1)
				os.environ[key] = value
except FileNotFoundError:
	pass

# 👾 Discord modules
import discord

# <-- Logging Settings -->

# Global Log Level
LogLevel = logging.INFO

# Blacklisted Channels (by ID) - Messages from these channels won't be logged
BlacklistedChannels = [
	1340307785312632915,  # Console
	1340314725770330185,  # Chat Link
]

# <-- Discord Settings -->

# Discord Intents
Intents = discord.Intents.default()
Intents.message_content = True

# Command Prefix
CommandPrefix = '!'

# Bot Name
BotName = 'Void Bot'

# Message Cooldown (in seconds) - Prevents spamming commands/messages
MessageCooldown = 2

# <-- Minecraft Settings -->

ProtocolVersion = 766  # 1.20.5
DefaultServer = 'play.voidtales.win'
DefaultServerPort = 25565
PresenceUpdateInterval = 30

# <-- Player Stats Settings -->

FuzzyMatchingThreshold = 0.6

# <-- Live Status Settings -->

# Channel ID for live status updates
# Use different channel for test mode vs production
LiveStatusChannelID = (
	1308757047596154951  # Test channel
	if os.getenv('BOT_TYPE') == 'test'
	else 1342510703386296483  # Production channel
)

# Update interval for live status (in seconds)
LiveStatusUpdateInterval = 60

# File path for live status persistence
LiveStatusFile = 'live_status.json'

# <-- Suggestions Settings -->

# Channel ID for suggestion embeds
SuggestionChannelID = 1411614420089438238

# <-- Role Settings -->

# Admin role IDs - Users with these roles have full admin permissions
ADMIN_ROLE_IDS = [1290261005955235840, 1308763721316958261]

# Moderator role ID - Users with this role have moderator permissions
MODERATOR_ROLE_ID = 1264629488130723872

# <-- Ticket System Settings -->

# Category ID for ticket channels
TICKETS_CATEGORY_ID = 1308780597988036628

# Channel ID for ticket transcripts
TRANSCRIPT_CHANNEL_ID = 1308793574329946162

# <-- Codex Wiki Settings -->

# The team wiki sits behind a login and is deliberately not linked anywhere
# public, so its address and its mirror come from the environment rather than
# from this repository. Without them the cog stays off, which is also what any
# other deployment of this bot wants.
_CodexChannel = os.getenv('CODEX_CHANNEL_ID', '').strip()
CodexChannelID = int(_CodexChannel) if _CodexChannel.isdigit() else 0
CodexRepo = os.getenv('CODEX_REPO', '')
CodexBaseUrl = os.getenv('CODEX_BASE_URL', '').rstrip('/')
CodexBranch = os.getenv('CODEX_BRANCH', 'main')

# Who gets pinged when a page changes. Discord only notifies from the message
# text, never from inside an embed, so these end up above the embed.
CodexMentionIDs = [
	Id for Id in os.getenv('CODEX_MENTION_IDS', '').replace(' ', '').split(',') if Id.isdigit()
]

# Poll interval (in seconds). Wiki edits happen a few times a day, no rush.
CodexPollInterval = 300

# File path for the last seen commit
CodexStateFile = 'codex_state.json'

# <-- Bot Color Settings -->

# Primary color for embeds (pastel green, used across all cogs)
EMBED_COLOR = discord.Color(0xA0D6B4)  # Pastel Green
