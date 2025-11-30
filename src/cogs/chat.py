"""
BRRR Bot - Chat Cog
Handles conversational AI with memory
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

logger = logging.getLogger('brrr.chat')


class Chat(commands.Cog):
    """Conversational AI with persistent memory"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @property
    def db(self):
        return self.bot.db
    
    @property
    def llm(self):
        return self.bot.llm
    
    async def handle_mention(self, message: discord.Message):
        """Handle when the bot is mentioned in a message"""
        
        if not self.llm:
            return
        
        # Show typing indicator
        async with message.channel.typing():
            try:
                # Get user info (works for both users and bots!)
                user_id = message.author.id
                guild_id = message.guild.id if message.guild else 0
                channel_id = message.channel.id
                
                # Get display name
                user_name = message.author.display_name
                
                # Check if it's a bot
                is_bot = message.author.bot
                
                # Get user memories
                memories = await self.db.get_all_memories(user_id, guild_id)
                
                # Get conversation history for context
                history = await self.db.get_recent_messages(user_id, guild_id, channel_id, limit=10)
                
                # Clean the message content (remove bot mention)
                content = message.content
                for mention in message.mentions:
                    content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
                content = content.strip()
                
                if not content:
                    content = "Hello!"
                
                # Add context about whether this is a bot
                if is_bot:
                    content = f"[This message is from another bot named {user_name}] {content}"
                
                # Build messages for LLM
                messages = history + [{"role": "user", "content": content}]
                
                # Get response from LLM
                response = await self.llm.chat(
                    messages=messages,
                    user_memories=memories,
                    user_name=user_name
                )
                
                # Save the conversation to history
                await self.db.add_message(user_id, guild_id, channel_id, "user", content)
                await self.db.add_message(user_id, guild_id, channel_id, "assistant", response.content)
                
                # Save any new memories
                for mem in response.memories_to_save:
                    await self.db.set_memory(
                        user_id=user_id,
                        guild_id=guild_id,
                        key=mem.get('key', 'misc'),
                        value=mem.get('value', ''),
                        context=mem.get('context')
                    )
                    logger.info(f"Saved memory for {user_name}: {mem['key']} = {mem['value']}")
                
                # Send response
                # Split if too long
                if len(response.content) > 2000:
                    chunks = [response.content[i:i+2000] for i in range(0, len(response.content), 2000)]
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await message.reply(chunk, mention_author=False)
                        else:
                            await message.channel.send(chunk)
                else:
                    await message.reply(response.content, mention_author=False)
                    
            except Exception as e:
                logger.error(f"Error in chat handler: {e}", exc_info=True)
                await message.reply(
                    "brrr... something went wrong! Try again? 🔧",
                    mention_author=False
                )
    
    # Memory management commands
    memory_group = app_commands.Group(name="memory", description="Manage what the bot remembers about you")
    
    @memory_group.command(name="show", description="See what the bot remembers about you")
    async def memory_show(self, interaction: discord.Interaction):
        """Show all memories for the user"""
        
        memories = await self.db.get_all_memories(
            interaction.user.id,
            interaction.guild.id
        )
        
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
        
        for key, data in list(memories.items())[:25]:  # Discord field limit
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
        
        embed.set_footer(text="Use /memory forget <key> to remove a memory")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @memory_group.command(name="forget", description="Make the bot forget something specific")
    @app_commands.describe(key="The memory key to forget (e.g., 'skill_python')")
    async def memory_forget(self, interaction: discord.Interaction, key: str):
        """Delete a specific memory"""
        
        memory = await self.db.get_memory(
            interaction.user.id,
            interaction.guild.id,
            key
        )
        
        if not memory:
            await interaction.response.send_message(
                f"I don't have a memory with key `{key}`!",
                ephemeral=True
            )
            return
        
        await self.db.delete_memory(
            interaction.user.id,
            interaction.guild.id,
            key
        )
        
        await interaction.response.send_message(
            f"✅ Forgot: `{key}`",
            ephemeral=True
        )
    
    @memory_group.command(name="clear", description="Clear all memories about you")
    async def memory_clear(self, interaction: discord.Interaction):
        """Clear all memories for the user"""
        
        # Confirmation view
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False
            
            @discord.ui.button(label="Yes, forget everything", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                self.stop()
                await button_interaction.response.defer()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                await button_interaction.response.defer()
        
        view = ConfirmView()
        await interaction.response.send_message(
            "⚠️ This will clear ALL my memories about you. Are you sure?",
            view=view,
            ephemeral=True
        )
        
        await view.wait()
        
        if view.confirmed:
            await self.db.clear_user_memories(
                interaction.user.id,
                interaction.guild.id
            )
            await interaction.edit_original_response(
                content="🧹 All memories cleared! Fresh start. 🧠",
                view=None
            )
        else:
            await interaction.edit_original_response(
                content="Cancelled - your memories are safe!",
                view=None
            )
    
    @memory_group.command(name="add", description="Manually add a memory")
    @app_commands.describe(
        key="Memory key (e.g., 'favorite_language')",
        value="Memory value (e.g., 'Python')"
    )
    async def memory_add(self, interaction: discord.Interaction, key: str, value: str):
        """Manually add a memory"""
        
        # Sanitize key
        key = key.lower().replace(' ', '_')
        
        await self.db.set_memory(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            key=key,
            value=value,
            context=f"Manually added by user"
        )
        
        await interaction.response.send_message(
            f"✅ I'll remember: `{key}` = `{value}`",
            ephemeral=True
        )
    
    # Direct chat command for when you don't want to @ the bot
    @app_commands.command(name="chat", description="Chat with the bot")
    @app_commands.describe(message="What do you want to say?")
    async def chat_command(self, interaction: discord.Interaction, message: str):
        """Direct chat command"""
        
        if not self.llm:
            await interaction.response.send_message(
                "Chat is disabled - LLM not configured!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else 0
            channel_id = interaction.channel.id
            user_name = interaction.user.display_name
            
            memories = await self.db.get_all_memories(user_id, guild_id)
            history = await self.db.get_recent_messages(user_id, guild_id, channel_id, limit=10)
            
            messages = history + [{"role": "user", "content": message}]
            
            response = await self.llm.chat(
                messages=messages,
                user_memories=memories,
                user_name=user_name
            )
            
            # Save conversation
            await self.db.add_message(user_id, guild_id, channel_id, "user", message)
            await self.db.add_message(user_id, guild_id, channel_id, "assistant", response.content)
            
            # Save memories
            for mem in response.memories_to_save:
                await self.db.set_memory(
                    user_id=user_id,
                    guild_id=guild_id,
                    key=mem.get('key', 'misc'),
                    value=mem.get('value', ''),
                    context=mem.get('context')
                )
            
            # Build response embed
            embed = discord.Embed(
                description=response.content,
                color=discord.Color.blue()
            )
            embed.set_author(
                name="BRRR Bot",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in chat command: {e}", exc_info=True)
            await interaction.followup.send(
                "brrr... something went wrong! 🔧",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Chat(bot))
