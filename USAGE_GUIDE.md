# Usage Guide - Enhanced Task & Note Features

## New Feature: Dynamic Model Selection

### Switching AI Models

Sometimes you want a different AI model for various reasons:
- **Speed**: Use `gpt-5-nano` for quick responses
- **Quality**: Use `gpt-4o` for complex reasoning
- **Cost**: Use `gpt-4o-mini` for balance

**How to switch:**

```
/model
→ Password prompt appears
→ Enter: platypus
→ See current model and available options
→ Click a button to instantly switch
→ ✅ Model changed! No restart needed.
```

**That's it!** The bot will use the new model for all future conversations.

**Available models:**
- `openai/gpt-5-nano` - Fast, efficient, great for most tasks
- `openai/gpt-4o` - Most capable, better for complex reasoning
- `openai/gpt-4o-mini` - Balanced speed and quality

---

## Quick Start Examples

### Example 1: Project Owner Setting Up Assignments

**Scenario:** You've created a project and need to assign work to your team.

```
/project info 1
→ Shows project with all tasks and note indicators

/project task assign 5 @Kyle
→ Assigns "Setup auth" to Kyle

/project task assign 6 @Alex
→ Assigns "Implement API" to Alex

/project info 1  (Check again)
→ Now shows:
   ⬜ Setup auth 📝(0) → @Kyle
   ⬜ Implement API 📝(0) → @Alex
```

### Example 2: Assigned User Adding Notes & Completing Work

**Scenario:** Kyle is working on the "Setup auth" task and wants to track progress.

```
/project task details 5
→ Shows:
   - Task: Setup auth
   - Assigned To: Kyle (you)
   - Status: Pending
   - Notes: None yet

📝 Click "View/Add Note" button
→ Modal appears for Kyle to add note

Type: "Got JWT working, now testing with Discord OAuth"
Submit

✅ Note added!

Later... Task is done:

/project task details 5
✅ Click "Mark Complete" button
→ Task marked complete
✅ Task marked complete: Setup auth
```

### Example 3: Team Reviewing Progress

**Scenario:** Quick status check on project.

```
/project info 1
→ Shows:
   ✅ Setup database → @Kyle (has 2 notes)
   ⬜ Implement API 📝(4) → @Alex
   ⬜ Create frontend → @Jordan
   ✅ Write tests 📝(1)
   ⬜ Deploy

→ Team immediately sees:
   - What's done (✅)
   - Who's working on what (→)
   - Which tasks have active discussion (📝)

/project task details 6
→ Click to see Alex's 4 notes on the API implementation
```

### Example 4: Dynamic Task Reassignment

**Scenario:** Someone gets blocked and needs to reassign a task.

```
/project task unassign 7
→ 🗑️ Removed task: Create frontend (now unassigned)

/project task assign 7 @Jordan
→ Reassigned to Jordan with confirmation

Jordan later completes:
/project task details 7
✅ Mark Complete button → Done!
```

## Command Reference

### View Project Status
```
/project info <project_id>
```
Shows all tasks with:
- Status (✅ or ⬜)
- Note count indicator (📝)
- Assigned user (→ @username)

### View Detailed Task
```
/project task details <task_id>
```
Shows:
- Full task details
- Assignment status
- All notes with authors and timestamps
- Interactive buttons for:
  - 📝 View/Add notes (assigned users can add)
  - ✅ Mark complete (owner/assignee)
  - ⬜ Mark incomplete (owner/assignee)

### Manage Task Assignment
```
/project task assign <task_id> <@user>
```
Assigns task to a team member (owner only)

```
/project task unassign <task_id>
```
Remove assignment (owner or assignee)

### Traditional Task Management
```
/project checklist list <project_id>
```
Shows all tasks with toggle buttons

```
/project checklist add <project_id> <description>
```
Add new task to project

```
/project checklist toggle <task_id>
```
Quick toggle without detail view

## Permission Model

| Action | Project Owner | Assigned User | Other Members |
|--------|---|---|---|
| View project info | ✅ | ✅ | ✅ |
| View task details | ✅ | ✅ | ✅ |
| Add notes | ✅ | ✅ | ❌ |
| Mark complete | ✅ | ✅ | ❌ |
| Mark incomplete | ✅ | ✅ | ❌ |
| Assign task | ✅ | ❌ | ❌ |
| Unassign task | ✅ | ✅ | ❌ |
| Delete task | ✅ | ❌ | ❌ |

## Best Practices

### 🎯 For Project Owners
1. **Use `/project info` regularly** - Quick visual overview of everything
2. **Assign tasks early** - Helps team know who's responsible
3. **Check note counts** - Tasks with many notes (📝) might need attention
4. **Reassign if blocked** - Use `/project task unassign` → `/project task assign`

### 👤 For Assigned Users
1. **Use `/project task details`** - Full context for your tasks
2. **Add notes early and often** - Help team understand progress
3. **Update status as you work** - Mark complete when done
4. **Check other notes** - Learn from team's progress on other tasks

### 👥 For Team Members
1. **Review `/project info`** - Daily standup reference
2. **Read task notes** - Context on decisions and blockers
3. **Use `/project status`** - Track multiple projects
4. **Offer help** - Notice others' tasks with many notes (may be blocked)

## Workflow Examples

### Daily Standby
```
1. /project info 1  (Check what's done, who's working on what)
2. Review any tasks with 📝 notes (check for blockers)
3. If blocked: /project task details <id> → read notes
4. If can help: offer assistance in project thread
```

### Weekly Review
```
1. /project status all  (See all active projects)
2. For each project: /project info <id>
3. Archive completed projects: /project archive <id>
4. Plan next week: /project task assign <id> <@next_person>
```

### Task Completion Flow
```
1. /project task details <id>  (See full context)
2. Work on task...
3. Add notes about solution: 📝 button
4. When done: ✅ Mark Complete button
5. Others see: ✅ in project info display
```

## Tips & Tricks

💡 **Quick Note Count Check:**
- Eye the 📝 icons in `/project info`
- High counts might indicate complexity or discussion
- Use as conversation starters

💡 **Unblocking Tasks:**
- If someone's task has many notes (discussing blockers)
- Use `/project task unassign` and `/project task assign` to fresh person
- Often faster than waiting for resolution

💡 **Permission Boundaries:**
- Assigned users can manage their own tasks
- But can't assign to others (owner-only feature)
- Prevents accidental reorganization

💡 **Note Trail:**
- All notes are timestamped
- Useful for tracking decision history
- Reference in retrospectives

## Troubleshooting

**Q: Can I add a note if not assigned?**
A: No, only assigned users can add notes. Project owners can assign you first.

**Q: Can I unassign someone else's task?**
A: Project owners can unassign anyone. Assigned users can only unassign themselves.

**Q: Where do notes appear?**
A: In `/project task details` view with author, date, and content.

**Q: Can I see tasks assigned to me?**
A: Use `/project task details` or `get_user_tasks` tool to see all your tasks.

**Q: What if a task needs notes but no one's assigned?**
A: Assign someone first, then they can add notes. Or project owner can add context in the thread.
