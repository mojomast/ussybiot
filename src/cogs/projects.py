"""
BRRR Bot - Project Commands Cog
Handles /project start, status, info, archive, checklist with note management
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
import logging
import aiosqlite

logger = logging.getLogger('brrr.projects')


class TaskNoteModal(discord.ui.Modal, title="Add Note to Task"):
    """Modal for adding a note to a task"""
    
    note_content = discord.ui.TextInput(
        label="Note",
        style=discord.TextStyle.paragraph,
        placeholder="Add your note here...",
        max_length=1000,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        self.result = self.note_content.value
        await interaction.response.defer()


class ProjectModal(discord.ui.Modal, title="Start New Project"):
    """Modal for creating a new project"""
    
    project_title = discord.ui.TextInput(
        label="Project Title",
        placeholder="What are you building?",
        max_length=100,
        required=True
    )
    
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="Brief description of the project...",
        max_length=500,
        required=False
    )
    
    tags = discord.ui.TextInput(
        label="Tags (comma separated)",
        placeholder="python, discord, bot",
        max_length=100,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse tags
        tag_list = []
        if self.tags.value:
            tag_list = [t.strip() for t in self.tags.value.split(',') if t.strip()]
        
        # Store data for the cog to use
        self.result = {
            'title': self.project_title.value,
            'description': self.description.value or None,
            'tags': tag_list
        }
        await interaction.response.defer()


class TaskModal(discord.ui.Modal, title="Add Task"):
    """Modal for adding a task"""
    
    task_label = discord.ui.TextInput(
        label="Task Description",
        placeholder="What needs to be done?",
        max_length=200,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        self.result = self.task_label.value
        await interaction.response.defer()


class ProjectSelectMenu(discord.ui.Select):
    """Dropdown to select a project"""
    
    def __init__(self, projects: list, callback_func):
        options = []
        for p in projects[:25]:  # Discord limit
            status_emoji = "🟢" if p['status'] == 'active' else "📦"
            options.append(
                discord.SelectOption(
                    label=p['title'][:100],
                    value=str(p['id']),
                    description=f"{status_emoji} {p['status'].capitalize()}",
                    emoji=status_emoji
                )
            )
        
        super().__init__(
            placeholder="Select a project...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.callback_func = callback_func
    
    async def callback(self, interaction: discord.Interaction):
        await self.callback_func(interaction, int(self.values[0]))


class ProjectInfoView(discord.ui.View):
    """View for project info with quick task access buttons"""
    
    def __init__(self, tasks: list, project_id: int, db, bot):
        super().__init__(timeout=600)
        self.tasks = tasks
        self.project_id = project_id
        self.db = db
        self.bot = bot
        self._build_buttons()
    
    def _build_buttons(self):
        """Build buttons for tasks with notes (first 15 tasks)"""
        self.clear_items()
        
        # Only show buttons for tasks that have notes
        tasks_with_notes = []
        for t in self.tasks[:15]:
            # This will be populated when buttons are clicked
            tasks_with_notes.append(t)
        
        if not tasks_with_notes:
            return
        
        # Create button for each task (limit to 5 per row, 25 total)
        for i, task in enumerate(tasks_with_notes[:25]):
            emoji = "✅" if task['is_done'] else "⬜"
            label = f"📋 {task['label'][:30]}"
            
            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary if task['is_done'] else discord.ButtonStyle.primary,
                custom_id=f"proj_info_task_{task['id']}",
                row=i // 5
            )
            button.callback = self._make_task_callback(task['id'])
            self.add_item(button)
    
    def _make_task_callback(self, task_id: int):
        async def callback(interaction: discord.Interaction):
            task = await self.db.get_task(task_id)
            if not task:
                await interaction.response.send_message("Task not found!", ephemeral=True)
                return
            
            # Show task detail
            status_emoji = "✅" if task['is_done'] else "⬜"
            embed = discord.Embed(
                title=f"{status_emoji} {task['label']}",
                color=discord.Color.green() if task['is_done'] else discord.Color.blue()
            )
            
            embed.add_field(name="Task ID", value=str(task['id']), inline=True)
            embed.add_field(name="Status", value="Completed" if task['is_done'] else "Pending", inline=True)
            
            if task.get('assigned_to'):
                embed.add_field(name="Assigned To", value=f"<@{task['assigned_to']}>", inline=True)
            else:
                embed.add_field(name="Assigned To", value="Unassigned", inline=True)
            
            # Show notes
            notes = await self.db.get_task_notes(task_id)
            if notes:
                note_text = ""
                for note in notes[:3]:
                    author_id = note.get('author_id', 'Unknown')
                    content = note.get('content', '')[:150]
                    created = note.get('created_at', '')[:10]
                    note_text += f"• <@{author_id}> ({created}): {content}\n"
                if len(notes) > 3:
                    note_text += f"... and {len(notes) - 3} more notes"
                embed.add_field(name=f"📝 Notes ({len(notes)})", value=note_text, inline=False)
            else:
                embed.add_field(name="📝 Notes", value="No notes yet", inline=False)
            
            # Show buttons for this task
            view = TaskDetailView(task, self.project_id, self.db, self.bot)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        return callback


class TaskToggleView(discord.ui.View):
    """View with task toggle buttons"""
    
    def __init__(self, tasks: list, project_id: int, db):
        super().__init__(timeout=300)
        self.tasks = tasks
        self.project_id = project_id
        self.db = db
        self._build_buttons()
    
    def _build_buttons(self):
        self.clear_items()
        for i, task in enumerate(self.tasks[:20]):  # Limit to 20 tasks
            emoji = "✅" if task['is_done'] else "⬜"
            label = task['label'][:80]
            button = discord.ui.Button(
                label=f"{emoji} {label}",
                style=discord.ButtonStyle.secondary if task['is_done'] else discord.ButtonStyle.primary,
                custom_id=f"task_{task['id']}",
                row=i // 5
            )
            button.callback = self._make_callback(task['id'], i)
            self.add_item(button)
    
    def _make_callback(self, task_id: int, index: int):
        async def callback(interaction: discord.Interaction):
            await self.db.toggle_task(task_id)
            self.tasks[index]['is_done'] = not self.tasks[index]['is_done']
            self._build_buttons()
            await interaction.response.edit_message(view=self)
        return callback


class ChecklistFilterView(discord.ui.View):
    """View with filter options for tasks"""
    
    def __init__(self, project_id: int, db, bot):
        super().__init__(timeout=600)
        self.project_id = project_id
        self.db = db
        self.bot = bot
        self.filter_status = "all"  # all, pending, complete
    
    @discord.ui.button(label="⬜ Pending", style=discord.ButtonStyle.primary)
    async def pending_filter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show only pending tasks"""
        self.filter_status = "pending"
        await self._show_filtered(interaction)
    
    @discord.ui.button(label="✅ Complete", style=discord.ButtonStyle.success)
    async def complete_filter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show only completed tasks"""
        self.filter_status = "complete"
        await self._show_filtered(interaction)
    
    @discord.ui.button(label="📋 All Tasks", style=discord.ButtonStyle.secondary)
    async def all_filter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show all tasks"""
        self.filter_status = "all"
        await self._show_filtered(interaction)
    
    async def _show_filtered(self, interaction: discord.Interaction):
        """Update the display with filtered tasks"""
        project = await self.db.get_project(self.project_id)
        all_tasks = await self.db.get_project_tasks(self.project_id)
        
        if self.filter_status == "pending":
            tasks = [t for t in all_tasks if not t['is_done']]
            filter_text = "⬜ Pending Tasks"
        elif self.filter_status == "complete":
            tasks = [t for t in all_tasks if t['is_done']]
            filter_text = "✅ Completed Tasks"
        else:
            tasks = all_tasks
            filter_text = "📋 All Tasks"
        
        done = sum(1 for t in all_tasks if t['is_done'])
        
        embed = discord.Embed(
            title=f"{filter_text}",
            description=f"{project['title']} - Progress: {done}/{len(all_tasks)} complete",
            color=discord.Color.green() if done == len(all_tasks) else discord.Color.blue()
        )
        
        task_list = []
        for t in tasks:
            emoji = "✅" if t['is_done'] else "⬜"
            assigned = f" → <@{t['assigned_to']}>" if t.get('assigned_to') else ""
            task_list.append(f"{emoji} {t['label']}{assigned}")
        
        if tasks:
            embed.add_field(name="Tasks", value="\n".join(task_list[:20]), inline=False)
        else:
            embed.add_field(name="Tasks", value=f"No {self.filter_status} tasks", inline=False)
        
        view = TaskToggleView(tasks, self.project_id, self.db)
        await interaction.response.edit_message(embed=embed, view=view)


class ProjectStatusView(discord.ui.View):
    """View for changing project status"""
    
    def __init__(self, project: dict, db, bot):
        super().__init__(timeout=600)
        self.project = project
        self.db = db
        self.bot = bot
    
    @discord.ui.button(label="🟢 Active", style=discord.ButtonStyle.success)
    async def set_active(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set project to active"""
        await self._change_status(interaction, "active", "🟢 Project set to active")
    
    @discord.ui.button(label="⏸️ Paused", style=discord.ButtonStyle.primary)
    async def set_paused(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Pause the project"""
        await self._change_status(interaction, "paused", "⏸️ Project paused")
    
    @discord.ui.button(label="✅ Completed", style=discord.ButtonStyle.green)
    async def set_completed(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark project as completed"""
        await self._change_status(interaction, "completed", "✅ Project marked complete!")
    
    @discord.ui.button(label="📦 Archive", style=discord.ButtonStyle.danger)
    async def set_archived(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Archive the project"""
        await self._change_status(interaction, "archived", "📦 Project archived")
    
    async def _change_status(self, interaction: discord.Interaction, status: str, message: str):
        """Helper to change project status"""
        # Check permission
        if interaction.user.id not in self.project.get('owners', []):
            await interaction.response.send_message(
                "⚠️ Only project owners can change the status!",
                ephemeral=True
            )
            return
        
        # Update project status in database
        await self.db.execute(
            "UPDATE projects SET status = ? WHERE id = ?",
            (status, self.project['id'])
        )
        
        await interaction.response.send_message(message, ephemeral=True)


class ProjectQuickActionView(discord.ui.View):
    """Quick action buttons for project operations"""
    
    def __init__(self, project: dict, db, bot):
        super().__init__(timeout=600)
        self.project = project
        self.db = db
        self.bot = bot
    
    @discord.ui.button(label="📋 View Tasks", style=discord.ButtonStyle.primary, emoji="📋")
    async def view_tasks(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View all tasks"""
        tasks = await self.db.get_project_tasks(self.project['id'])
        if not tasks:
            await interaction.response.send_message(
                "No tasks yet! Use `/project checklist add` to create some.",
                ephemeral=True
            )
            return
        
        view = ChecklistFilterView(self.project['id'], self.db, self.bot)
        embed = discord.Embed(
            title=f"📋 {self.project['title']} - Tasks",
            description="Click filters to view different task categories",
            color=discord.Color.blue()
        )
        done = sum(1 for t in tasks if t['is_done'])
        embed.add_field(name="Progress", value=f"{done}/{len(tasks)} complete", inline=False)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="➕ Add Task", style=discord.ButtonStyle.success, emoji="➕")
    async def add_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a new task"""
        from src.cogs.projects import TaskModal
        modal = TaskModal()
        await interaction.response.send_modal(modal)
        try:
            await modal.wait()
        except:
            return
        
        if hasattr(modal, 'result'):
            await self.db.create_task(self.project['id'], modal.result, interaction.user.id)
            await interaction.followup.send(
                f"✅ Task added to **{self.project['title']}**",
                ephemeral=True
            )
    
    @discord.ui.button(label="🏁 Complete All", style=discord.ButtonStyle.green, emoji="🏁")
    async def complete_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark all tasks as complete"""
        # Check permission
        if interaction.user.id not in self.project.get('owners', []):
            await interaction.response.send_message(
                "⚠️ Only project owners can mark all tasks complete!",
                ephemeral=True
            )
            return
        
        tasks = await self.db.get_project_tasks(self.project['id'])
        for task in tasks:
            if not task['is_done']:
                await self.db.toggle_task(task['id'])
        
        await interaction.response.send_message(
            f"✅ All tasks marked complete!",
            ephemeral=True
        )
    
    @discord.ui.button(label="⚙️ Status", style=discord.ButtonStyle.blurple, emoji="⚙️")
    async def change_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Change project status"""
        # Check permission
        if interaction.user.id not in self.project.get('owners', []):
            await interaction.response.send_message(
                "⚠️ Only project owners can change status!",
                ephemeral=True
            )
            return
        
        view = ProjectStatusView(self.project, self.db, self.bot)
        embed = discord.Embed(
            title="⚙️ Change Project Status",
            description=f"Current: **{self.project['status'].capitalize()}**",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TaskDetailView(discord.ui.View):
    """View for task details with note management and completion"""
    
    def __init__(self, task: dict, project_id: int, db, bot):
        super().__init__(timeout=600)
        self.task = task
        self.project_id = project_id
        self.db = db
        self.bot = bot
    
    @discord.ui.button(label="📝 View/Add Note", style=discord.ButtonStyle.blurple)
    async def note_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View or add a note to the task"""
        notes = await self.db.get_task_notes(self.task['id'])
        
        if not notes and interaction.user.id != self.task.get('assigned_to'):
            await interaction.response.send_message(
                "⚠️ You must be assigned to this task to add notes!",
                ephemeral=True
            )
            return
        
        # Show existing notes
        if notes:
            embed = discord.Embed(
                title=f"📋 Notes for: {self.task['label'][:100]}",
                color=discord.Color.blue()
            )
            for note in notes[:5]:
                author_id = note.get('author_id', 'Unknown')
                content = note.get('content', '')[:200]
                created = note.get('created_at', '')[:10]
                embed.add_field(
                    name=f"<@{author_id}> - {created}",
                    value=content,
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Allow assigned user to add notes
        if interaction.user.id == self.task.get('assigned_to'):
            modal = TaskNoteModal()
            await interaction.response.send_modal(modal)
            try:
                await modal.wait()
            except:
                return
            
            if hasattr(modal, 'result'):
                await self.db.add_task_note(
                    self.task['id'],
                    interaction.user.id,
                    modal.result
                )
                await interaction.followup.send(
                    "✅ Note added!",
                    ephemeral=True
                )
    
    @discord.ui.button(label="👤 Assign", style=discord.ButtonStyle.secondary, emoji="👤")
    async def assign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Quickly assign task to a team member"""
        project = await self.db.get_project(self.project_id)
        is_owner = interaction.user.id in project.get('owners', [])
        
        if not is_owner:
            await interaction.response.send_message(
                "⚠️ Only project owners can assign tasks!",
                ephemeral=True
            )
            return
        
        view = TaskAssignmentView(self.task, self.project_id, interaction.guild, self.db, self.bot)
        embed = discord.Embed(
            title="👤 Assign Task",
            description=f"Assign **{self.task['label']}** to someone",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="⚡ Priority", style=discord.ButtonStyle.primary, emoji="⚡")
    async def priority_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set task priority level"""
        project = await self.db.get_project(self.project_id)
        is_owner = interaction.user.id in project.get('owners', [])
        is_assigned = interaction.user.id == self.task.get('assigned_to')
        
        if not (is_owner or is_assigned):
            await interaction.response.send_message(
                "⚠️ Only project owners or assigned users can set priority!",
                ephemeral=True
            )
            return
        
        view = TaskPriorityView(self.task, self.db, self.bot)
        embed = discord.Embed(
            title="⚡ Set Priority",
            description=f"Choose priority level for **{self.task['label']}**",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="✅ Mark Complete", style=discord.ButtonStyle.green)
    async def complete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark task as complete (assigned user or owner only)"""
        project = await self.db.get_project(self.project_id)
        is_owner = interaction.user.id in project.get('owners', [])
        is_assigned = interaction.user.id == self.task.get('assigned_to')
        
        if not (is_owner or is_assigned):
            await interaction.response.send_message(
                "⚠️ Only the task owner or assigned user can mark this complete!",
                ephemeral=True
            )
            return
        
        await self.db.toggle_task(self.task['id'])
        self.task['is_done'] = True
        button.disabled = True
        button.label = "✅ Completed"
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("✅ Task marked complete!", ephemeral=True)
    
    @discord.ui.button(label="⬜ Mark Incomplete", style=discord.ButtonStyle.red)
    async def incomplete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark task as incomplete (assigned user or owner only)"""
        project = await self.db.get_project(self.project_id)
        is_owner = interaction.user.id in project.get('owners', [])
        is_assigned = interaction.user.id == self.task.get('assigned_to')
        
        if not (is_owner or is_assigned):
            await interaction.response.send_message(
                "⚠️ Only the task owner or assigned user can modify this!",
                ephemeral=True
            )
            return
        
        if self.task['is_done']:
            await self.db.toggle_task(self.task['id'])
            self.task['is_done'] = False
            button.disabled = True
            button.label = "⬜ Incomplete"
            
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⬜ Task marked incomplete!", ephemeral=True)


class TaskAssignmentView(discord.ui.View):
    """View for quickly assigning tasks to team members"""
    
    def __init__(self, task: dict, project_id: int, guild: discord.Guild, db, bot):
        super().__init__(timeout=600)
        self.task = task
        self.project_id = project_id
        self.guild = guild
        self.db = db
        self.bot = bot
        
        # Create dropdown with guild members
        self._build_member_select()
    
    def _build_member_select(self):
        """Build member dropdown"""
        members = []
        if self.guild and self.guild.members:
            # Get first 25 non-bot members
            for member in list(self.guild.members)[:25]:
                if not member.bot:
                    members.append(member)
        
        options = []
        for member in members:
            options.append(
                discord.SelectOption(
                    label=member.display_name[:100],
                    value=str(member.id),
                    emoji="👤"
                )
            )
        
        if not options:
            return
        
        # Add "Unassigned" option
        options.insert(0, discord.SelectOption(label="Unassigned", value="0", emoji="⭕"))
        
        select = discord.ui.Select(
            placeholder="Assign to...",
            options=options
        )
        select.callback = self._assign_callback
        self.add_item(select)
    
    async def _assign_callback(self, interaction: discord.Interaction):
        """Handle assignment selection"""
        user_id_str = self.values[0] if hasattr(self, 'values') else interaction.data['values'][0]
        user_id = int(user_id_str) if user_id_str != "0" else None
        
        # Update task assignment
        task_sql = "UPDATE tasks SET assigned_to = ? WHERE id = ?"
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute(task_sql, (user_id, self.task['id']))
            await db.commit()
        
        if user_id:
            await interaction.response.send_message(
                f"✅ Task assigned to <@{user_id}>!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "✅ Task unassigned!",
                ephemeral=True
            )


class TaskPriorityView(discord.ui.View):
    """View for setting task priority levels"""
    
    def __init__(self, task: dict, db, bot):
        super().__init__(timeout=600)
        self.task = task
        self.db = db
        self.bot = bot
    
    @discord.ui.button(label="🟢 Low", style=discord.ButtonStyle.success)
    async def priority_low(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set task priority to low"""
        await self._set_priority(interaction, "low", "🟢 Low priority set")
    
    @discord.ui.button(label="🟡 Medium", style=discord.ButtonStyle.primary)
    async def priority_medium(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set task priority to medium"""
        await self._set_priority(interaction, "medium", "🟡 Medium priority set")
    
    @discord.ui.button(label="🔴 High", style=discord.ButtonStyle.danger)
    async def priority_high(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set task priority to high"""
        await self._set_priority(interaction, "high", "🔴 High priority set")
    
    @discord.ui.button(label="🔥 Critical", style=discord.ButtonStyle.red)
    async def priority_critical(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Set task priority to critical"""
        await self._set_priority(interaction, "critical", "🔥 Critical priority set")
    
    async def _set_priority(self, interaction: discord.Interaction, priority: str, message: str):
        """Helper to set priority"""
        # Store priority in database (would need to update schema)
        # For now, just show confirmation
        await interaction.response.send_message(message, ephemeral=True)


class Projects(commands.Cog):
    """Project management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @property
    def db(self):
        return self.bot.db
    
    project_group = app_commands.Group(
        name="project",
        description="Project management commands",
        guild_only=True
    )
    
    @project_group.command(name="start", description="Start a new project")
    async def project_start(self, interaction: discord.Interaction):
        """Start a new project with a modal form"""
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
        project_id = await self.db.create_project(
            guild_id=interaction.guild.id,
            title=data['title'],
            description=data['description'],
            owners=[interaction.user.id],
            tags=data['tags']
        )
        
        # Create thread for the project
        thread = None
        if interaction.channel.type == discord.ChannelType.text:
            try:
                thread = await interaction.channel.create_thread(
                    name=f"🚀 {data['title']}",
                    type=discord.ChannelType.public_thread
                )
                await self.db.update_project(project_id, thread_id=thread.id)
            except discord.Forbidden:
                logger.warning(f"No permission to create thread for project {project_id}")
            except discord.HTTPException as e:
                logger.error(f"Failed to create thread for project {project_id}: {e}")
        
        # Build the project embed
        embed = discord.Embed(
            title=f"🚀 Project Started: {data['title']}",
            description=data['description'] or "No description provided",
            color=discord.Color.green()
        )
        embed.add_field(name="ID", value=str(project_id), inline=True)
        embed.add_field(name="Owner", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value="🟢 Active", inline=True)
        
        if data['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in data['tags']), inline=False)
        
        if thread:
            embed.add_field(name="Thread", value=thread.mention, inline=False)
        
        embed.set_footer(text="Use /project checklist to add tasks!")
        
        # Send the announcement
        await interaction.followup.send(embed=embed)
        
        # If thread was created, send a welcome message there too
        if thread:
            thread_embed = discord.Embed(
                title=f"🏎️ {data['title']} - Let's go BRRRRR!",
                description="This is your project thread. Use it to discuss, share updates, and track progress!",
                color=discord.Color.blue()
            )
            thread_embed.add_field(
                name="Quick Commands",
                value="""
• `/project checklist add` - Add tasks
• `/project checklist list` - View tasks
• `/project info` - Project details
• `/project archive` - When you're done!
                """,
                inline=False
            )
            await thread.send(embed=thread_embed)
        
        # Auto-generate tasks if LLM is available
        if self.bot.llm and data['description']:
            try:
                tasks_text = await self.bot.llm.generate_project_plan(
                    data['title'],
                    data['description']
                )
                tasks = [t.strip() for t in tasks_text.strip().split('\n') if t.strip()]
                
                for task in tasks[:10]:  # Limit to 10 auto-tasks
                    await self.db.create_task(project_id, task, interaction.user.id)
                
                if thread and tasks:
                    tasks_embed = discord.Embed(
                        title="📋 Auto-generated Checklist",
                        description="\n".join(f"⬜ {t}" for t in tasks[:10]),
                        color=discord.Color.blue()
                    )
                    tasks_embed.set_footer(text="Use /project checklist to manage these tasks")
                    await thread.send(embed=tasks_embed)
            except Exception as e:
                logger.error(f"Failed to auto-generate tasks: {e}")
    
    @project_group.command(name="status", description="List all projects")
    @app_commands.describe(filter="Filter by project status")
    async def project_status(
        self,
        interaction: discord.Interaction,
        filter: Optional[Literal["active", "archived", "all"]] = "active"
    ):
        """Show all projects in the guild"""
        if filter == "all":
            projects = await self.db.get_guild_projects(interaction.guild.id)
        else:
            projects = await self.db.get_guild_projects(interaction.guild.id, status=filter)
        
        if not projects:
            await interaction.response.send_message(
                f"No {filter} projects found! Use `/project start` to create one. 🚀",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"📊 Projects ({filter.capitalize()})",
            color=discord.Color.blue()
        )
        
        for p in projects[:10]:  # Show first 10
            status_emoji = "🟢" if p['status'] == 'active' else "📦"
            tasks = await self.db.get_project_tasks(p['id'])
            done = sum(1 for t in tasks if t['is_done'])
            
            value = p['description'][:100] if p['description'] else "No description"
            if tasks:
                value += f"\n📋 Tasks: {done}/{len(tasks)} complete"
            if p['thread_id']:
                value += f"\n💬 <#{p['thread_id']}>"
            
            embed.add_field(
                name=f"{status_emoji} [{p['id']}] {p['title']}",
                value=value,
                inline=False
            )
        
        if len(projects) > 10:
            embed.set_footer(text=f"Showing 10 of {len(projects)} projects")
        
        await interaction.response.send_message(embed=embed)
    
    @project_group.command(name="info", description="Get detailed project info")
    @app_commands.describe(project_id="Project ID to view")
    async def project_info(self, interaction: discord.Interaction, project_id: int):
        """Show detailed project information with tasks and notes"""
        project = await self.db.get_project(project_id)
        
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Project not found!", ephemeral=True)
            return
        
        status_emoji = "🟢" if project['status'] == 'active' else "📦"
        
        embed = discord.Embed(
            title=f"{status_emoji} {project['title']}",
            description=project['description'] or "No description",
            color=discord.Color.green() if project['status'] == 'active' else discord.Color.greyple()
        )
        
        embed.add_field(name="ID", value=str(project['id']), inline=True)
        embed.add_field(name="Status", value=project['status'].capitalize(), inline=True)
        embed.add_field(name="Created", value=project['created_at'][:10], inline=True)
        
        if project['owners']:
            owners = [f"<@{o}>" for o in project['owners']]
            embed.add_field(name="Owners", value=", ".join(owners), inline=False)
        
        if project['tags']:
            embed.add_field(name="Tags", value=", ".join(f"`{t}`" for t in project['tags']), inline=False)
        
        if project['thread_id']:
            embed.add_field(name="Thread", value=f"<#{project['thread_id']}>", inline=False)
        
        # Show tasks with enhanced display
        tasks = await self.db.get_project_tasks(project['id'])
        if tasks:
            done = sum(1 for t in tasks if t['is_done'])
            task_list = []
            for t in tasks[:15]:
                emoji = "✅" if t['is_done'] else "⬜"
                # Get note count for this task
                notes = await self.db.get_task_notes(t['id'])
                note_indicator = f" 📝({len(notes)})" if notes else ""
                # Get assigned user
                assigned = f" → <@{t['assigned_to']}>" if t.get('assigned_to') else ""
                task_list.append(f"{emoji} {t['label'][:60]}{note_indicator}{assigned}")
            
            embed.add_field(
                name=f"📋 Tasks ({done}/{len(tasks)} done)",
                value="\n".join(task_list) if task_list else "No tasks",
                inline=False
            )
            if len(tasks) > 15:
                embed.set_footer(text=f"Showing 15 of {len(tasks)} tasks - use /project task details to view individual tasks")
        
        # Create an interactive view with task detail buttons
        view = ProjectInfoView(tasks, project['id'], self.db, self.bot)
        quick_view = ProjectQuickActionView(project, self.db, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        await interaction.followup.send(
            "**Project Quick Actions** - Click below to manage:",
            view=quick_view,
            ephemeral=False
        )
    
    @project_group.command(name="archive", description="Archive a project")
    @app_commands.describe(project_id="Project ID to archive")
    async def project_archive(self, interaction: discord.Interaction, project_id: int):
        """Archive a completed project"""
        project = await self.db.get_project(project_id)
        
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Project not found!", ephemeral=True)
            return
        
        if project['status'] == 'archived':
            await interaction.response.send_message("Project is already archived!", ephemeral=True)
            return
        
        await self.db.archive_project(project_id)
        
        embed = discord.Embed(
            title=f"📦 Project Archived: {project['title']}",
            description="Great work! This project has been archived.",
            color=discord.Color.greyple()
        )
        
        tasks = await self.db.get_project_tasks(project_id)
        done = sum(1 for t in tasks if t['is_done'])
        embed.add_field(name="Tasks Completed", value=f"{done}/{len(tasks)}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    # Checklist subcommand group
    checklist_group = app_commands.Group(
        name="checklist",
        description="Manage project tasks",
        parent=project_group
    )
    
    @checklist_group.command(name="add", description="Add a task to a project")
    @app_commands.describe(project_id="Project to add task to", task="Task description")
    async def checklist_add(
        self,
        interaction: discord.Interaction,
        project_id: int,
        task: str
    ):
        """Add a task to a project's checklist"""
        project = await self.db.get_project(project_id)
        
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Project not found!", ephemeral=True)
            return
        
        task_id = await self.db.create_task(project_id, task, interaction.user.id)
        
        await interaction.response.send_message(
            f"✅ Added task to **{project['title']}**: {task}",
            ephemeral=True
        )
    
    @checklist_group.command(name="list", description="View and toggle project tasks")
    @app_commands.describe(project_id="Project to view tasks for")
    async def checklist_list(self, interaction: discord.Interaction, project_id: int):
        """Show tasks with toggle buttons"""
        project = await self.db.get_project(project_id)
        
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Project not found!", ephemeral=True)
            return
        
        tasks = await self.db.get_project_tasks(project_id)
        
        if not tasks:
            await interaction.response.send_message(
                f"No tasks for **{project['title']}**. Use `/project checklist add` to add some!",
                ephemeral=True
            )
            return
        
        done = sum(1 for t in tasks if t['is_done'])
        
        embed = discord.Embed(
            title=f"📋 {project['title']} - Tasks",
            description=f"Progress: {done}/{len(tasks)} complete",
            color=discord.Color.green() if done == len(tasks) else discord.Color.blue()
        )
        
        task_list = []
        for t in tasks:
            emoji = "✅" if t['is_done'] else "⬜"
            task_list.append(f"{emoji} {t['label']}")
        
        embed.add_field(name="Tasks", value="\n".join(task_list[:20]), inline=False)
        
        view = TaskToggleView(tasks, project_id, self.db)
        await interaction.response.send_message(embed=embed, view=view)
    
    @checklist_group.command(name="toggle", description="Toggle a task's completion status")
    @app_commands.describe(task_id="Task ID to toggle")
    async def checklist_toggle(self, interaction: discord.Interaction, task_id: int):
        """Toggle a specific task"""
        task = await self.db.get_task(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        # Verify task belongs to a project in this guild
        project = await self.db.get_project(task['project_id'])
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        await self.db.toggle_task(task_id)
        status = "completed" if not task['is_done'] else "incomplete"
        await interaction.response.send_message(
            f"✅ Marked task as {status}: **{task['label']}**",
            ephemeral=True
        )
    
    @checklist_group.command(name="remove", description="Remove a task from a project")
    @app_commands.describe(task_id="Task ID to remove")
    async def checklist_remove(self, interaction: discord.Interaction, task_id: int):
        """Remove a task from a project"""
        task = await self.db.get_task(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        # Verify task belongs to a project in this guild
        project = await self.db.get_project(task['project_id'])
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        await self.db.delete_task(task_id)
        await interaction.response.send_message(
            f"🗑️ Removed task: **{task['label']}**",
            ephemeral=True
        )
    
    # Task detail subcommand group
    task_group = app_commands.Group(
        name="task",
        description="Manage individual tasks",
        parent=project_group
    )
    
    @task_group.command(name="details", description="View task details with notes and options")
    @app_commands.describe(task_id="Task ID to view")
    async def task_details(self, interaction: discord.Interaction, task_id: int):
        """Show detailed task information with note display and management"""
        task = await self.db.get_task(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        project = await self.db.get_project(task['project_id'])
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        status_emoji = "✅" if task['is_done'] else "⬜"
        embed = discord.Embed(
            title=f"{status_emoji} {task['label']}",
            color=discord.Color.green() if task['is_done'] else discord.Color.blue()
        )
        
        embed.add_field(name="Task ID", value=str(task['id']), inline=True)
        embed.add_field(name="Status", value="Completed" if task['is_done'] else "Pending", inline=True)
        embed.add_field(name="Project", value=f"{project['title']} (ID: {project['id']})", inline=False)
        
        if task.get('assigned_to'):
            embed.add_field(name="Assigned To", value=f"<@{task['assigned_to']}>", inline=True)
        else:
            embed.add_field(name="Assigned To", value="Unassigned", inline=True)
        
        if task.get('created_by'):
            embed.add_field(name="Created By", value=f"<@{task['created_by']}>", inline=True)
        
        # Show notes
        notes = await self.db.get_task_notes(task_id)
        if notes:
            note_text = ""
            for note in notes[:3]:
                author_id = note.get('author_id', 'Unknown')
                content = note.get('content', '')[:150]
                created = note.get('created_at', '')[:10]
                note_text += f"• <@{author_id}> ({created}): {content}\n"
            if len(notes) > 3:
                note_text += f"... and {len(notes) - 3} more notes"
            embed.add_field(name=f"📝 Notes ({len(notes)})", value=note_text, inline=False)
        
        embed.set_footer(text="Click buttons below to manage this task")
        
        view = TaskDetailView(task, project['id'], self.db, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
    
    @task_group.command(name="assign", description="Assign a task to a user")
    @app_commands.describe(task_id="Task ID", user="User to assign to")
    async def task_assign(self, interaction: discord.Interaction, task_id: int, user: discord.User):
        """Assign a task to a specific user"""
        task = await self.db.get_task(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        project = await self.db.get_project(task['project_id'])
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        # Check if user can assign (must be project owner)
        if interaction.user.id not in project.get('owners', []):
            await interaction.response.send_message(
                "⚠️ Only project owners can assign tasks!",
                ephemeral=True
            )
            return
        
        await self.db.assign_task(task_id, user.id)
        
        embed = discord.Embed(
            title="✅ Task Assigned",
            description=f"**{task['label']}** assigned to {user.mention}",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @task_group.command(name="unassign", description="Remove assignment from a task")
    @app_commands.describe(task_id="Task ID")
    async def task_unassign(self, interaction: discord.Interaction, task_id: int):
        """Unassign a task from its current user"""
        task = await self.db.get_task(task_id)
        
        if not task:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        project = await self.db.get_project(task['project_id'])
        if not project or project['guild_id'] != interaction.guild.id:
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        # Check if user can unassign (must be project owner or currently assigned)
        is_owner = interaction.user.id in project.get('owners', [])
        is_assigned = interaction.user.id == task.get('assigned_to')
        
        if not (is_owner or is_assigned):
            await interaction.response.send_message(
                "⚠️ Only the project owner or assigned user can unassign this task!",
                ephemeral=True
            )
            return
        
        await self.db.unassign_task(task_id)
        
        await interaction.response.send_message(
            f"✅ Unassigned: **{task['label']}**",
            ephemeral=True
        )
    
    # My tasks subcommand
    my_tasks_group = app_commands.Group(
        name="my-tasks",
        description="View and manage your assigned tasks",
        parent=project_group
    )
    
    @my_tasks_group.command(name="pending", description="See your pending tasks")
    async def my_pending_tasks(self, interaction: discord.Interaction):
        """Show all tasks assigned to you that are pending"""
        user_tasks = await self.db.get_user_tasks(
            interaction.guild.id,
            interaction.user.id,
            include_done=False
        )
        
        if not user_tasks:
            await interaction.response.send_message(
                "You have no pending tasks! 🎉",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"📌 Your Pending Tasks ({len(user_tasks)})",
            description="Tasks assigned to you that need work",
            color=discord.Color.gold()
        )
        
        for task in user_tasks[:10]:
            project = await self.db.get_project(task['project_id'])
            notes = await self.db.get_task_notes(task['id'])
            note_count = f" (📝 {len(notes)})" if notes else ""
            
            embed.add_field(
                name=f"⬜ {task['label'][:60]}",
                value=f"**{project['title']}** (ID: {task['id']}){note_count}",
                inline=False
            )
        
        if len(user_tasks) > 10:
            embed.set_footer(text=f"Showing 10 of {len(user_tasks)} tasks")
        
        # Create quick action buttons
        class TaskQuickView(discord.ui.View):
            def __init__(self, bot_ref, db_ref):
                super().__init__(timeout=600)
                self.bot_ref = bot_ref
                self.db_ref = db_ref
            
            @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
            async def refresh(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                await button_interaction.response.defer()
                # Will refresh when clicked
            
            @discord.ui.button(label="✅ Mark Next Complete", style=discord.ButtonStyle.success)
            async def mark_next(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if user_tasks:
                    first_task = user_tasks[0]
                    await self.db_ref.toggle_task(first_task['id'])
                    await button_interaction.response.send_message(
                        f"✅ Marked **{first_task['label']}** complete!",
                        ephemeral=True
                    )
        
        view = TaskQuickView(self.bot, self.db)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @my_tasks_group.command(name="all", description="See all your tasks")
    async def my_all_tasks(self, interaction: discord.Interaction):
        """Show all tasks assigned to you (pending and completed)"""
        user_tasks = await self.db.get_user_tasks(
            interaction.guild.id,
            interaction.user.id,
            include_done=True
        )
        
        if not user_tasks:
            await interaction.response.send_message(
                "No tasks assigned to you yet!",
                ephemeral=True
            )
            return
        
        pending = [t for t in user_tasks if not t['is_done']]
        completed = [t for t in user_tasks if t['is_done']]
        
        embed = discord.Embed(
            title=f"📊 Your Task Dashboard",
            description=f"Total: {len(user_tasks)} | Pending: {len(pending)} | Done: {len(completed)}",
            color=discord.Color.blue()
        )
        
        if pending:
            task_text = ""
            for task in pending[:5]:
                project = await self.db.get_project(task['project_id'])
                task_text += f"• **{task['label'][:50]}** - {project['title']}\n"
            if len(pending) > 5:
                task_text += f"... and {len(pending) - 5} more"
            embed.add_field(name=f"⬜ Pending ({len(pending)})", value=task_text, inline=False)
        
        if completed:
            task_text = ""
            for task in completed[:5]:
                project = await self.db.get_project(task['project_id'])
                task_text += f"• **{task['label'][:50]}** - {project['title']}\n"
            if len(completed) > 5:
                task_text += f"... and {len(completed) - 5} more"
            embed.add_field(name=f"✅ Completed ({len(completed)})", value=task_text, inline=False)
        
        embed.set_footer(text="Use /project my-tasks pending for detailed view")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Projects(bot))
