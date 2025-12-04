"""
BRRR Bot - Main Entry Point
A Discord bot that goes brrrrrrrr for weekly coding projects
"""

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import logging
from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Generate log filename with timestamp
log_filename = f"logs/brrr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Set up logging with both file and console handlers
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # File handler - stores all logs including DEBUG
        logging.FileHandler(log_filename, encoding='utf-8'),
        # Console handler - shows INFO and above
        logging.StreamHandler()
    ]
)

# Set console handler to INFO level (less noisy)
logging.getLogger().handlers[1].setLevel(logging.INFO)

# Reduce noise from third-party libraries
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('discord').setLevel(logging.INFO)

logger = logging.getLogger('brrr')
logger.info(f"Logging to file: {log_filename}")

# Load environment variables
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
REQUESTY_API_KEY = os.getenv('REQUESTY_API_KEY')
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/brrr.db')

# =============================================================================
# MODEL CONFIGURATION
# Hardcoded for testing. To make configurable later:
# - Add per-user model selection in database
# - Add /model command to switch models
# - Or use: LLM_MODEL = os.getenv('LLM_MODEL', 'openai/gpt-5-nano')
# =============================================================================
LLM_MODEL = os.getenv('LLM_MODEL', 'openai/gpt-5-nano')  # Default to gpt-5-nano

if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables!")

if not REQUESTY_API_KEY:
    logger.warning("REQUESTY_API_KEY not found - LLM features will be disabled")
else:
    logger.info(f"LLM configured: {LLM_MODEL} via Requesty")


class BrrrBot(commands.Bot):
    def __init__(self):
        # Set up intents - we need message content and members
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.db = None
        self.llm = None
        # Per-channel locks to prevent concurrent message processing
        self._channel_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Track when bot is ready to ignore old messages (set in on_ready)
        self._started_at = None
        
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Initialize database
        from src.database import Database
        self.db = Database(DATABASE_PATH)
        await self.db.init()
        logger.info("Database initialized")
        
        # Initialize LLM client
        if REQUESTY_API_KEY:
            from src.llm import LLMClient
            self.llm = LLMClient(REQUESTY_API_KEY, LLM_MODEL)
            logger.info(f"LLM client initialized with model: {LLM_MODEL}")
        
        # Load cogs
        await self.load_extension('src.cogs.projects')
        await self.load_extension('src.cogs.weekly')
        await self.load_extension('src.cogs.ideas')
        await self.load_extension('src.cogs.chat')
        logger.info("All cogs loaded")
        
        # Sync commands
        await self.tree.sync()
        logger.info("Commands synced")
    
    async def on_ready(self):
        """Called when the bot is fully ready"""
        # Set the ready timestamp - ignore any messages from before this moment
        self._started_at = datetime.now(timezone.utc)
        
        logger.info(f'BRRR Bot is online! Logged in as {self.user}')
        logger.info(f'Connected to {len(self.guilds)} guild(s)')
        
        # Debug: List all commands in tree
        all_commands = await self.tree.fetch_commands()
        logger.info(f"Local tree has {len(all_commands)} commands:")
        for cmd in all_commands:
            logger.info(f"  - /{cmd.name}")
        
        # For development: force sync to all guilds to bypass cache
        for guild in self.guilds:
            try:
                logger.info(f"Syncing commands to guild {guild.name}...")
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Successfully synced {len(synced)} commands to {guild.name}")
            except Exception as e:
                logger.error(f"Failed to sync to guild {guild.name}: {e}")
        
        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="projects go brrrrr 🚀"
            )
        )
    
    async def on_message(self, message: discord.Message):
        """
        Handle incoming messages - RESPONDS TO BOTS TOO!
        This is the key difference from default behavior.
        """
        # Don't respond to ourselves
        if message.author.id == self.user.id:
            return
        
        # Ignore messages if bot isn't ready yet or if sent before bot started
        if self._started_at is None or message.created_at < self._started_at:
            return
        
        # Process commands first (for prefix commands if any)
        await self.process_commands(message)
        
        # Check if bot was mentioned or message is a reply to bot
        bot_mentioned = self.user.mentioned_in(message)
        is_reply_to_bot = (
            message.reference and 
            message.reference.resolved and 
            message.reference.resolved.author.id == self.user.id
        )
        
        # Check if bot name is in content (simple "chat without @ed")
        name_in_content = "brrr" in message.content.lower()
        
        # If mentioned or replied to, engage in conversation
        if bot_mentioned or is_reply_to_bot or name_in_content:
            if self.llm is None:
                await message.reply("brrrr... LLM not configured! Set REQUESTY_API_KEY to enable chat.", mention_author=False)
                return
            
            # Get the chat cog to handle the conversation
            chat_cog = self.get_cog('Chat')
            if chat_cog:
                # Use per-channel lock to prevent concurrent API calls
                async with self._channel_locks[message.channel.id]:
                    await chat_cog.handle_mention(message)
    
    async def close(self):
        """Cleanup on shutdown"""
        if self.llm:
            await self.llm.close()
        await super().close()


# Create bot instance
bot = BrrrBot()


# Admin user IDs (Discord user IDs)
ADMIN_USERS = {
    1000449836886020159,  # @ussy
}

# Model command password
MODEL_PASSWORD = "platypus"


class PasswordModal(discord.ui.Modal, title="Enter Password"):
    """Modal for password authentication"""
    
    password_input = discord.ui.TextInput(
        label="Password",
        placeholder="Enter the password to manage models",
        max_length=100,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Verify password
        if self.password_input.value == MODEL_PASSWORD:
            self.result = True
        else:
            self.result = False
        await interaction.response.defer()


class ModelSelectView(discord.ui.View):
    """View for selecting LLM model from dynamically fetched list"""
    
    def __init__(self, bot, models: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.models = models
        
        # Create buttons for each model (limit to 25 due to Discord limits)
        for i, model in enumerate(models[:25]):
            model_id = model.get('id', '')
            model_name = model.get('name', model_id)
            
            # Determine button style based on current model
            try:
                is_current = bot.llm and bot.llm.model == model_id
            except Exception as e:
                logger.warning(f"Error checking current model: {e}")
                is_current = False
            
            button = discord.ui.Button(
                label=model_name[:80],
                style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.primary,
                custom_id=f"model_{i}"
            )
            button.callback = self._make_model_callback(model_id, model_name, i)
            self.add_item(button)
    
    def _make_model_callback(self, model_id: str, model_name: str, index: int):
        async def callback(interaction: discord.Interaction):
            # Prompt for password
            modal = PasswordModal()
            await interaction.response.send_modal(modal)
            
            # Wait for modal submission
            try:
                await modal.wait()
            except:
                return
            
            # Check password
            if not hasattr(modal, 'result') or not modal.result:
                await interaction.followup.send(
                    "❌ Incorrect password!",
                    ephemeral=True
                )
                return
            
            # Change the model
            self.bot.llm.model = model_id
            logger.info(f"Model changed to {model_id} by {interaction.user}")
            
            # Update button styles
            for i, item in enumerate(self.children):
                if isinstance(item, discord.ui.Button):
                    if i == index:
                        item.style = discord.ButtonStyle.success
                    else:
                        item.style = discord.ButtonStyle.primary
            
            embed = discord.Embed(
                title="✅ Model Changed",
                description=f"LLM model is now: **{model_name}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Model ID",
                value=f"`{model_id}`",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Announce in the channel
            await interaction.followup.send(
                f"🔄 Bot's LLM model changed to: **{model_name}**"
            )
        
        return callback


@bot.tree.command(name="model", description="Change the LLM model")
async def model_command(interaction: discord.Interaction):
    """Let users choose which LLM model to use (password protected)"""
    
    # Prompt for password
    modal = PasswordModal()
    await interaction.response.send_modal(modal)
    
    # Wait for modal submission
    try:
        await modal.wait()
    except:
        return
    
    # Check password
    if not hasattr(modal, 'result') or not modal.result:
        await interaction.followup.send(
            "❌ Incorrect password!",
            ephemeral=True
        )
        return
    
    # Check if LLM is initialized
    if not bot.llm:
        await interaction.followup.send(
            "❌ LLM not initialized! Check REQUESTY_API_KEY in .env",
            ephemeral=True
        )
        return
    
    try:
        # Fetch available models from API
        models = await bot.llm.get_available_models()
        
        if not models:
            await interaction.followup.send(
                "❌ Failed to fetch available models from the API. Please try again later."
            )
            return
        
        embed = discord.Embed(
            title="🤖 LLM Model Selection",
            description=f"Choose from {len(models)} available model(s):",
            color=discord.Color.blue()
        )
        
        # Show current model
        current_model = bot.llm.model if bot.llm else "None"
        embed.add_field(
            name="📍 Current Model",
            value=f"`{current_model}`",
            inline=False
        )
        
        # Show available models (first 10 in embed, all in buttons)
        model_list = "\n".join([
            f"• `{m.get('id', m.get('name'))}`"
            for m in models[:10]
        ])
        if len(models) > 10:
            model_list += f"\n... and {len(models) - 10} more"
        
        embed.add_field(
            name="📚 Available Models",
            value=model_list,
            inline=False
        )
        
        embed.set_footer(text="Click a button to select a model")
        
        view = ModelSelectView(bot, models)
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        logger.error(f"Error in model command: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ Error: {str(e)}"
        )



# Simple ping command for testing
@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏎️ BRRRRR! Pong! ({latency}ms)")


@bot.tree.command(name="brrr", description="Get bot status and info")
async def brrr_status(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 BRRR Bot Status",
        description="Weekly project planner that goes brrrrrrrr!",
        color=discord.Color.green()
    )
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Guilds", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="LLM", value="✅ Active" if bot.llm else "❌ Disabled", inline=True)
    
    if interaction.guild:
        projects = await bot.db.get_guild_projects(interaction.guild.id, status='active')
        embed.add_field(name="Active Projects", value=str(len(projects)), inline=True)
    
    embed.set_footer(text="Use /help for commands")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 BRRR Bot Commands",
        description="Your weekly project planning assistant! Click buttons for interactive features.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📋 Project Commands",
        value="""
`/project start` - Start a new project with auto-tasks
`/project status` - List all projects
`/project info` - Get project details with quick action buttons
`/project archive` - Archive a completed project
`/project checklist add` - Add a task to a project
`/project checklist list` - View tasks with filter buttons
`/project checklist toggle` - Mark task complete/incomplete
`/project checklist remove` - Delete a task
        """,
        inline=False
    )
    
    embed.add_field(
        name="📅 Weekly Commands",
        value="""
`/week start` - Start a new week with project overview
`/week stats` - Interactive stats dashboard with filtering 🎯 NEW
`/week summary` - Quick progress summary
`/week retro` - Run project retrospective
        """,
        inline=False
    )
    
    embed.add_field(
        name="💡 Idea Commands",
        value="""
`/idea add` - Add a new idea with description
`/idea quick` - Quick add with just a title
`/idea list` - Browse ideas with voting buttons 👍👎🔥
`/idea pick` - Pick an idea to turn into a project
`/idea random` - Get a random idea
`/idea delete` - Delete an idea from the pool
        """,
        inline=False
    )
    
    embed.add_field(
        name="🎭 Persona Commands",
        value="""
`/persona set` - Customize how I respond to you
`/persona preset` - Quick style presets (concise, detailed, etc)
`/persona show` - View your current settings
`/persona clear` - Reset to default behavior
        """,
        inline=False
    )
    
    embed.add_field(
        name="🧠 Memory Commands",
        value="""
`/memory show` - See what I remember about you
`/memory forget` - Make me forget something
`/memory clear` - Clear all your memories
        """,
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Admin Commands",
        value="""
`/model` - Change the LLM model (admin only)
        """,
        inline=False
    )
    
    embed.add_field(
        name="💬 Chat & Interaction",
        value="""
**@mention me** to chat! I can help with:
• Project planning & brainstorming
• Code questions & debugging
• Task ideas & suggestions
• Team coordination

**Interactive Features:**
• Vote on ideas with 👍👎🔥
• Assign tasks with dropdown buttons
• Change project status instantly
• Set task priorities on the fly
• View team stats with buttons
        """,
        inline=False
    )
    
    embed.set_footer(text="Let's make your projects go brrrrrr! 🏎️ | Powered by gpt-5-nano")
    await interaction.response.send_message(embed=embed)


def main():
    """Run the bot"""
    bot.run(TOKEN)


if __name__ == '__main__':
    main()
