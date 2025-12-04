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
                # Validate all commands before syncing
                for cmd in self.tree._get_all_commands():
                    logger.debug(f"  - Validating /{cmd.name}...")
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Successfully synced {len(synced)} commands to {guild.name}")
                for cmd in synced:
                    logger.info(f"  ✓ /{cmd.name}")
            except Exception as e:
                logger.error(f"Failed to sync to guild {guild.name}: {e}", exc_info=True)
        
        # Also do a global sync
        try:
            logger.info("Performing global sync...")
            global_synced = await self.tree.sync()
            logger.info(f"Global sync: {len(global_synced)} commands")
        except Exception as e:
            logger.error(f"Global sync failed: {e}", exc_info=True)
        
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
        
        # Check for "brrrmenu" trigger first (before other handlers)
        if "brrrmenu" in message.content.lower():
            # Create a fake interaction-like response
            embed = discord.Embed(
                title="🚀 BRRR Bot - Main Menu",
                description="Choose a category to get started!\n\nClick the buttons below to explore features:",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="📋 Projects", value="Start, manage, and track projects", inline=True)
            embed.add_field(name="💡 Ideas", value="Capture and browse ideas", inline=True)
            embed.add_field(name="📅 Weekly", value="Weekly stats and summaries", inline=True)
            embed.add_field(name="💬 Chat & Memory", value="Manage memories and chat", inline=True)
            embed.add_field(name="🎭 Persona", value="Customize bot personality", inline=True)
            embed.add_field(name="❓ Help", value="View full command list", inline=True)
            embed.set_footer(text="Tip: Use /menu anytime for quick access!")
            
            from src.bot import MainMenuView
            view = MainMenuView()
            await message.reply(embed=embed, view=view, mention_author=False)
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


# =============================================================================
# INTERACTIVE MENU SYSTEM
# =============================================================================

class MainMenuView(discord.ui.View):
    """Main menu with category buttons"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="Projects", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def projects_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📋 Project Management",
            description="Manage your projects and tasks!",
            color=discord.Color.blue()
        )
        view = ProjectMenuView()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Ideas", style=discord.ButtonStyle.primary, emoji="💡", row=0)
    async def ideas_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💡 Idea Pool",
            description="Capture and manage your project ideas!",
            color=discord.Color.yellow()
        )
        view = IdeaMenuView()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Weekly", style=discord.ButtonStyle.primary, emoji="📅", row=0)
    async def weekly_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📅 Weekly Dashboard",
            description="Track your weekly progress and stats!",
            color=discord.Color.gold()
        )
        view = WeeklyMenuView()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Chat & Memory", style=discord.ButtonStyle.primary, emoji="💬", row=1)
    async def chat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💬 Chat & Memory",
            description="Manage chat features and what the bot remembers!",
            color=discord.Color.purple()
        )
        view = ChatMenuView()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Persona", style=discord.ButtonStyle.primary, emoji="🎭", row=1)
    async def persona_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎭 Persona Settings",
            description="Customize how the bot responds to you!",
            color=discord.Color.purple()
        )
        view = PersonaMenuView()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Help", style=discord.ButtonStyle.secondary, emoji="❓", row=2)
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show help embed
        embed = discord.Embed(
            title="🚀 BRRR Bot Help",
            description="Full command reference and tips!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Project Commands",
            value="`/project start` • `/project status` • `/project info`\n`/project archive` • `/project checklist add/list/toggle`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Idea Commands",
            value="`/idea add` • `/idea quick` • `/idea list`\n`/idea pick` • `/idea random` • `/idea delete`",
            inline=False
        )
        
        embed.add_field(
            name="📅 Weekly Commands",
            value="`/week start` • `/week stats` • `/week summary` • `/week retro`",
            inline=False
        )
        
        embed.add_field(
            name="💬 Chat Commands",
            value="`/chat` • `/memory show/forget/clear/add`\n`/persona set/preset/show/clear`",
            inline=False
        )
        
        embed.add_field(
            name="💡 Pro Tips",
            value="• Use `/menu` anytime for quick access\n• @mention me to chat naturally\n• All menus have a back button",
            inline=False
        )
        
        view = MainMenuView()
        await interaction.response.edit_message(embed=embed, view=view)


class ProjectMenuView(discord.ui.View):
    """Project management submenu"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="Start New Project", style=discord.ButtonStyle.success, emoji="🚀")
    async def start_project(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.cogs.projects import ProjectModal
        modal = ProjectModal()
        await interaction.response.send_modal(modal)
        
        # Wait for modal submission
        try:
            await modal.wait()
        except:
            return
        
        if not hasattr(modal, 'result'):
            return
        
        data = modal.result
        
        # Create the project
        project_id = await bot.db.create_project(
            guild_id=interaction.guild.id,
            title=data['title'],
            description=data['description'],
            owners=[interaction.user.id],
            tags=data['tags']
        )
        
        # Create thread if possible
        thread = None
        if interaction.channel.type == discord.ChannelType.text:
            try:
                thread = await interaction.channel.create_thread(
                    name=f"🚀 {data['title']}",
                    type=discord.ChannelType.public_thread
                )
                await bot.db.update_project(project_id, thread_id=thread.id)
            except discord.Forbidden:
                pass
        
        embed = discord.Embed(
            title=f"🚀 Project Started: {data['title']}",
            description=data['description'] or "No description provided",
            color=discord.Color.green()
        )
        embed.add_field(name="ID", value=str(project_id), inline=True)
        embed.add_field(name="Owner", value=interaction.user.mention, inline=True)
        
        if data['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in data['tags']), inline=False)
        
        if thread:
            embed.add_field(name="Thread", value=thread.mention, inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @discord.ui.button(label="View All Projects", style=discord.ButtonStyle.primary, emoji="📊")
    async def view_projects(self, interaction: discord.Interaction, button: discord.ui.Button):
        projects = await bot.db.get_guild_projects(interaction.guild.id, status='active')
        
        if not projects:
            await interaction.response.send_message(
                "No active projects! Use the button above to start one. 🚀",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📊 Active Projects",
            color=discord.Color.blue()
        )
        
        for p in projects[:10]:
            tasks = await bot.db.get_project_tasks(p['id'])
            done = sum(1 for t in tasks if t['is_done'])
            
            value = p['description'][:100] if p['description'] else "No description"
            if tasks:
                value += f"\n📋 Tasks: {done}/{len(tasks)}"
            
            embed.add_field(
                name=f"🟢 [{p['id']}] {p['title']}",
                value=value,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Archived Projects", style=discord.ButtonStyle.secondary, emoji="📦")
    async def archived_projects(self, interaction: discord.Interaction, button: discord.ui.Button):
        projects = await bot.db.get_guild_projects(interaction.guild.id, status='archived')
        
        if not projects:
            await interaction.response.send_message(
                "No archived projects yet!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📦 Archived Projects",
            color=discord.Color.greyple()
        )
        
        for p in projects[:10]:
            embed.add_field(
                name=f"[{p['id']}] {p['title']}",
                value=p['description'][:100] if p['description'] else "No description",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🚀 BRRR Bot - Main Menu",
            description="Choose a category to get started!",
            color=discord.Color.blue()
        )
        view = MainMenuView()
        await interaction.response.edit_message(embed=embed, view=view)


class IdeaMenuView(discord.ui.View):
    """Idea pool submenu"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="Add New Idea", style=discord.ButtonStyle.success, emoji="💡")
    async def add_idea(self, interaction: discord.Interaction, button: discord.ui.Button):
        from src.cogs.ideas import IdeaModal
        modal = IdeaModal()
        await interaction.response.send_modal(modal)
        
        try:
            await modal.wait()
        except:
            return
        
        if not hasattr(modal, 'result'):
            return
        
        data = modal.result
        
        idea_id = await bot.db.add_idea(
            guild_id=interaction.guild.id,
            title=data['title'],
            description=data['description'],
            submitted_by=interaction.user.id,
            tags=data['tags']
        )
        
        embed = discord.Embed(
            title="💡 Idea Added!",
            description=data['title'],
            color=discord.Color.yellow()
        )
        embed.add_field(name="ID", value=str(idea_id), inline=True)
        
        if data['description']:
            embed.add_field(name="Description", value=data['description'], inline=False)
        
        if data['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in data['tags']), inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @discord.ui.button(label="Browse Ideas", style=discord.ButtonStyle.primary, emoji="📖")
    async def browse_ideas(self, interaction: discord.Interaction, button: discord.ui.Button):
        ideas = await bot.db.get_guild_ideas(interaction.guild.id, unused_only=True)
        
        if not ideas:
            await interaction.response.send_message(
                "No ideas yet! Add one with the button above. 💡",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="💡 Idea Pool",
            description=f"{len(ideas)} idea(s) available!",
            color=discord.Color.yellow()
        )
        
        for idea in ideas[:10]:
            value = idea['description'][:100] if idea['description'] else "No description"
            if idea['tags']:
                value += f"\n🏷️ {', '.join(idea['tags'][:3])}"
            
            embed.add_field(
                name=f"[{idea['id']}] {idea['title']}",
                value=value,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Random Idea", style=discord.ButtonStyle.primary, emoji="🎲")
    async def random_idea(self, interaction: discord.Interaction, button: discord.ui.Button):
        import random
        ideas = await bot.db.get_guild_ideas(interaction.guild.id, unused_only=True)
        
        if not ideas:
            await interaction.response.send_message(
                "No ideas to pick from!",
                ephemeral=True
            )
            return
        
        idea = random.choice(ideas)
        
        embed = discord.Embed(
            title="🎲 Random Idea!",
            description=idea['title'],
            color=discord.Color.yellow()
        )
        
        if idea['description']:
            embed.add_field(name="Description", value=idea['description'], inline=False)
        
        if idea['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in idea['tags']), inline=False)
        
        embed.set_footer(text=f"Idea #{idea['id']}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🚀 BRRR Bot - Main Menu",
            description="Choose a category to get started!",
            color=discord.Color.blue()
        )
        view = MainMenuView()
        await interaction.response.edit_message(embed=embed, view=view)


class WeeklyMenuView(discord.ui.View):
    """Weekly dashboard submenu"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="Start New Week", style=discord.ButtonStyle.success, emoji="📅")
    async def start_week(self, interaction: discord.Interaction, button: discord.ui.Button):
        from datetime import datetime
        
        active_projects = await bot.db.get_guild_projects(interaction.guild.id, status='active')
        ideas = await bot.db.get_guild_ideas(interaction.guild.id, unused_only=True)
        
        today = datetime.utcnow()
        week_num = today.isocalendar()[1]
        
        embed = discord.Embed(
            title=f"🗓️ Week {week_num} - Let's Go BRRRRRR!",
            description="New week, new opportunities to ship!",
            color=discord.Color.gold()
        )
        
        if active_projects:
            project_lines = [f"🟢 **{p['title']}** (ID: {p['id']})" for p in active_projects[:5]]
            embed.add_field(
                name=f"📊 Active Projects ({len(active_projects)})",
                value="\n".join(project_lines) or "None",
                inline=False
            )
        
        if ideas:
            embed.add_field(
                name=f"💡 Ideas Ready ({len(ideas)})",
                value=f"{len(ideas)} ideas waiting to become projects!",
                inline=False
            )
        
        embed.add_field(
            name="🎯 This Week's Focus",
            value="What will you ship this week?",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @discord.ui.button(label="View Stats", style=discord.ButtonStyle.primary, emoji="📊")
    async def view_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        projects = await bot.db.get_guild_projects(interaction.guild.id)
        active = [p for p in projects if p['status'] == 'active']
        archived = [p for p in projects if p['status'] == 'archived']
        
        all_tasks = []
        for p in projects:
            tasks = await bot.db.get_project_tasks(p['id'])
            all_tasks.extend(tasks)
        
        completed_tasks = sum(1 for t in all_tasks if t['is_done'])
        
        embed = discord.Embed(
            title="📊 Server Stats",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Total Projects", value=str(len(projects)), inline=True)
        embed.add_field(name="Active", value=str(len(active)), inline=True)
        embed.add_field(name="Archived", value=str(len(archived)), inline=True)
        
        embed.add_field(name="Total Tasks", value=str(len(all_tasks)), inline=True)
        embed.add_field(name="Completed", value=str(completed_tasks), inline=True)
        
        if all_tasks:
            completion = int((completed_tasks / len(all_tasks)) * 100)
            embed.add_field(name="Completion", value=f"{completion}%", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Weekly Summary", style=discord.ButtonStyle.primary, emoji="📝")
    async def weekly_summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        projects = await bot.db.get_guild_projects(interaction.guild.id, status='active')
        
        if not projects:
            await interaction.response.send_message(
                "No active projects to summarize!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📝 Weekly Summary",
            description="Progress on active projects",
            color=discord.Color.blue()
        )
        
        for p in projects[:5]:
            tasks = await bot.db.get_project_tasks(p['id'])
            done = sum(1 for t in tasks if t['is_done'])
            
            progress = f"{done}/{len(tasks)} tasks complete" if tasks else "No tasks yet"
            embed.add_field(
                name=f"🟢 {p['title']}",
                value=progress,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🚀 BRRR Bot - Main Menu",
            description="Choose a category to get started!",
            color=discord.Color.blue()
        )
        view = MainMenuView()
        await interaction.response.edit_message(embed=embed, view=view)


class ChatMenuView(discord.ui.View):
    """Chat and memory management submenu"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="View Memories", style=discord.ButtonStyle.primary, emoji="🧠")
    async def view_memories(self, interaction: discord.Interaction, button: discord.ui.Button):
        memories = await bot.db.get_all_memories(interaction.user.id, interaction.guild.id)
        
        if not memories:
            await interaction.response.send_message(
                "I don't have any memories about you yet! Chat with me and I'll remember things. 🧠",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"🧠 What I Remember About {interaction.user.display_name}",
            color=discord.Color.purple()
        )
        
        for key, data in list(memories.items())[:10]:
            value = data['value'] if isinstance(data, dict) else data
            context = data.get('context', '') if isinstance(data, dict) else ''
            
            field_value = value
            if context:
                field_value += f"\n*{context}*"
            
            embed.add_field(
                name=key.replace('_', ' ').title(),
                value=field_value[:1024],
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Chat Tips", style=discord.ButtonStyle.secondary, emoji="💬")
    async def chat_tips(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💬 Chat Tips",
            description="How to interact with the bot effectively!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="How to Chat",
            value="• @mention me in any channel\n• Reply to my messages\n• Use `/chat <message>` command\n• Just say 'brrr' in your message",
            inline=False
        )
        
        embed.add_field(
            name="What I Can Help With",
            value="• Project planning & ideas\n• Code questions\n• Task suggestions\n• Team coordination\n• General conversation",
            inline=False
        )
        
        embed.add_field(
            name="Memory Features",
            value="I remember things you tell me:\n• Skills & preferences\n• Project details\n• Team information\n• Use `/memory` commands to manage",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🚀 BRRR Bot - Main Menu",
            description="Choose a category to get started!",
            color=discord.Color.blue()
        )
        view = MainMenuView()
        await interaction.response.edit_message(embed=embed, view=view)


class PersonaMenuView(discord.ui.View):
    """Persona customization submenu"""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="View Current Persona", style=discord.ButtonStyle.primary, emoji="🎭")
    async def view_persona(self, interaction: discord.Interaction, button: discord.ui.Button):
        memories = await bot.db.get_all_memories(interaction.user.id, interaction.guild.id)
        
        if 'persona_instructions' not in memories:
            await interaction.response.send_message(
                "You haven't set a custom persona yet! I'm using my default friendly style. 🎭",
                ephemeral=True
            )
            return
        
        persona_data = memories['persona_instructions']
        instructions = persona_data.get('value') if isinstance(persona_data, dict) else persona_data
        
        embed = discord.Embed(
            title="🎭 Your Current Persona",
            description=instructions,
            color=discord.Color.purple()
        )
        
        embed.set_footer(text="Use buttons below to change or clear")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Concise", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def preset_concise(self, interaction: discord.Interaction, button: discord.ui.Button):
        instructions = "Be concise and to-the-point. Keep responses brief and direct."
        
        await bot.db.set_memory(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            key='persona_instructions',
            value=instructions,
            context='preset: concise'
        )
        
        await interaction.response.send_message(
            "✅ Persona set to **Concise**! I'll keep it brief.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Detailed", style=discord.ButtonStyle.secondary, emoji="📚")
    async def preset_detailed(self, interaction: discord.Interaction, button: discord.ui.Button):
        instructions = "Be detailed and thorough. Provide comprehensive explanations and examples."
        
        await bot.db.set_memory(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            key='persona_instructions',
            value=instructions,
            context='preset: detailed'
        )
        
        await interaction.response.send_message(
            "✅ Persona set to **Detailed**! I'll be thorough.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Friendly", style=discord.ButtonStyle.secondary, emoji="😊")
    async def preset_friendly(self, interaction: discord.Interaction, button: discord.ui.Button):
        instructions = "Be warm, friendly, and encouraging. Use casual language and show enthusiasm."
        
        await bot.db.set_memory(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            key='persona_instructions',
            value=instructions,
            context='preset: friendly'
        )
        
        await interaction.response.send_message(
            "✅ Persona set to **Friendly**! Let's chat! 😊",
            ephemeral=True
        )
    
    @discord.ui.button(label="Professional", style=discord.ButtonStyle.secondary, emoji="💼")
    async def preset_professional(self, interaction: discord.Interaction, button: discord.ui.Button):
        instructions = "Be professional and formal. Use proper terminology and maintain a business-like tone."
        
        await bot.db.set_memory(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            key='persona_instructions',
            value=instructions,
            context='preset: professional'
        )
        
        await interaction.response.send_message(
            "✅ Persona set to **Professional**! Ready to assist.",
            ephemeral=True
        )
    
    @discord.ui.button(label="← Back to Menu", style=discord.ButtonStyle.secondary, row=2)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🚀 BRRR Bot - Main Menu",
            description="Choose a category to get started!",
            color=discord.Color.blue()
        )
        view = MainMenuView()
        await interaction.response.edit_message(embed=embed, view=view)


@bot.tree.command(name="menu", description="Interactive menu to access all bot features")
async def menu_command(interaction: discord.Interaction):
    """Show the main interactive menu"""
    embed = discord.Embed(
        title="🚀 BRRR Bot - Main Menu",
        description="Choose a category to get started!\n\nClick the buttons below to explore features:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📋 Projects",
        value="Start, manage, and track projects",
        inline=True
    )
    
    embed.add_field(
        name="💡 Ideas",
        value="Capture and browse ideas",
        inline=True
    )
    
    embed.add_field(
        name="📅 Weekly",
        value="Weekly stats and summaries",
        inline=True
    )
    
    embed.add_field(
        name="💬 Chat & Memory",
        value="Manage memories and chat",
        inline=True
    )
    
    embed.add_field(
        name="🎭 Persona",
        value="Customize bot personality",
        inline=True
    )
    
    embed.add_field(
        name="❓ Help",
        value="View full command list",
        inline=True
    )
    
    embed.set_footer(text="Tip: Use /menu anytime for quick access!")
    
    view = MainMenuView()
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 BRRR Bot Commands",
        description="Your weekly project planning assistant! Click buttons for interactive features.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎯 Quick Start",
        value="Use `/menu` for an interactive guide to all features!",
        inline=False
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
