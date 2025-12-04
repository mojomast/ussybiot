# Enhanced Project Management System - Technical Documentation

## System Architecture

### Core Components

#### 1. **TaskNoteModal** (New)
- **Purpose:** Structured UI for adding notes to tasks
- **Input:** Text area (max 1000 chars)
- **Output:** Deferred response with note content in `result` attribute
- **Location:** `src/cogs/projects.py` lines 15-25

#### 2. **TaskDetailView** (Enhanced)
- **Purpose:** Interactive task detail display with note management
- **Components:**
  - 📝 View/Add Note button
  - ✅ Mark Complete button  
  - ⬜ Mark Incomplete button
- **Permissions:**
  - Note viewing: All users
  - Note adding: Assigned users only
  - Status updates: Owner or assigned user
- **Location:** `src/cogs/projects.py` lines 147-220

#### 3. **Enhanced Commands**

**`/model`** (New - Dec 3, 2025)
- Allows dynamic LLM model selection
- Password-protected with modal input
- Displays available models from Requesty API
- One-click model switching via buttons
- No bot restart required
- Implementation: `src/bot.py` lines 194-380

**`/project info <project_id>`**
- Shows all project tasks (up to 15)
- Display format: `✅ Task name 📝(3) → @assigned_user`
- Note indicator count updates dynamically
- Fetches notes for each task from database

**`/project task details <task_id>`** (New)
- Comprehensive task information
- Shows all notes (up to 5 in detail view)
- Interactive button controls
- Permission-aware UI

**`/project task assign <task_id> <@user>`** (New)
- Assigns task to specified user
- Owner-only operation
- Creates confirmation embed

**`/project task unassign <task_id>`** (New)
- Removes task assignment
- Owner or assigned user can execute
- Clears the `assigned_to` field

### Data Flow

```
User clicks /project info
    ↓
Database query: get_project_tasks()
    ↓
For each task:
  - Get status (is_done)
  - Get assignment (assigned_to)
  - Get notes (get_task_notes)
    ↓
Format display with indicators
    ↓
Show embed with note counts & assignments
```

### Database Integration

**Existing Tables Used:**
- `tasks` - Contains all task data
  - `id` - Task ID
  - `project_id` - Foreign key to projects
  - `label` - Task description
  - `is_done` - Completion status (0/1)
  - `assigned_to` - User ID of assignee
  - `created_by` - User ID of creator

- `task_notes` - Note storage
  - `id` - Note ID
  - `task_id` - Foreign key to task
  - `author_id` - User ID of note author
  - `content` - Note text
  - `created_at` - Timestamp

**Database Methods Used:**
```python
await db.get_project_tasks(project_id)
await db.get_task(task_id)
await db.get_task_notes(task_id)
await db.add_task_note(task_id, author_id, content)
await db.toggle_task(task_id)
await db.assign_task(task_id, user_id)
await db.unassign_task(task_id)
await db.get_project(project_id)
```

### Permission Model

```python
# Check if user is project owner
is_owner = interaction.user.id in project.get('owners', [])

# Check if user is task assignee
is_assigned = interaction.user.id == task.get('assigned_to')

# Note permissions
if interaction.user.id == task.get('assigned_to'):
    allow_add_note()  # Only assigned can add

# Status update permissions
if is_owner or is_assigned:
    allow_toggle_status()
```

## Implementation Details

### Model Command (`/model`) - Password-Protected Selection

**Architecture:**
- `PasswordModal` class - Text input modal for authentication
- `ModelSelectView` class - Interactive button view for model selection
- `model_command()` function - Main command handler

**Flow:**
```
1. User runs /model
2. PasswordModal displayed → User enters password
3. Modal defers interaction response
4. Command checks password against MODEL_PASSWORD constant
5. If correct:
   → Fetches available models from LLM API
   → Creates ModelSelectView with button for each model
   → Displays current model and available options
6. If incorrect:
   → Ephemeral error message sent via followup
```

**Key Implementation Points:**
- `send_modal()` responds to interaction, subsequent actions use `followup.send()`
- Model list fetched from `bot.llm.get_available_models()`
- Button callbacks also require password re-entry for security
- Current model highlighted with `discord.ButtonStyle.success`
- Password stored as constant: `MODEL_PASSWORD = "platypus"`

**Database:**
- No database changes needed - model is stored in `bot.llm.model` property
- Model persists in memory for the bot's lifetime
- Reverts to default on bot restart (configurable via `.env` `LLM_MODEL`)

**Files Modified:**
- `src/bot.py`: PasswordModal, ModelSelectView, model_command definitions

---

### TaskDetailView Button Callbacks

#### Note Button (`note_button`)
```python
1. Fetch notes from database
2. If no notes AND user not assigned:
   → Send ephemeral warning
3. If notes exist:
   → Show up to 5 notes in embed (author, date, content)
4. If user is assigned:
   → Show modal for adding new note
   → Save note to database on submit
   → Confirm with ephemeral message
```

#### Complete Button (`complete_button`)
```python
1. Get project to check ownership
2. Verify user is owner OR assigned
3. If not authorized:
   → Send ephemeral warning
4. If authorized:
   → Toggle task completion
   → Disable button
   → Show confirmation
```

#### Incomplete Button (`incomplete_button`)
```python
Same as complete but for reverting completed tasks
```

### Enhanced Project Info Display

```python
# For each task in project
emoji = "✅" if task['is_done'] else "⬜"

# Get note indicator
notes = await db.get_task_notes(t['id'])
note_indicator = f" 📝({len(notes)})" if notes else ""

# Get assignment indicator
assigned = f" → <@{t['assigned_to']}>" if t.get('assigned_to') else ""

# Format line
task_list.append(f"{emoji} {t['label'][:60]}{note_indicator}{assigned}")
```

Result: `✅ Setup auth 📝(2) → @Kyle`

## Workflow Examples

### Example 1: Assignment Flow
```
Owner: /project task assign 5 @developer
  ↓
Bot checks: Owner in project.owners[] ✓
  ↓
DB: UPDATE tasks SET assigned_to = @developer WHERE id = 5
  ↓
Send confirmation embed
  ↓
Next /project info shows: → @developer
```

### Example 2: Note Addition Flow
```
Assignee: /project task details 5
  ↓
Display task embed + buttons
  ↓
Assignee clicks "📝 View/Add Note"
  ↓
Bot checks: interaction.user.id == task.assigned_to ✓
  ↓
Show TaskNoteModal
  ↓
Assignee types note and submits
  ↓
DB: INSERT INTO task_notes (task_id, author_id, content, created_at)
  ↓
Show "✅ Note added!"
  ↓
Next /project info shows: 📝(1)
```

### Example 3: Status Update Flow
```
Assignee: /project task details 5
  ↓
Assignee clicks "✅ Mark Complete"
  ↓
Bot checks: 
  - is_owner = interaction.user.id in project.owners[]
  - is_assigned = interaction.user.id == task.assigned_to
  ✓ (is_assigned = true)
  ↓
DB: UPDATE tasks SET is_done = NOT is_done WHERE id = 5
  ↓
Show confirmation
  ↓
Next /project info shows: ✅ (instead of ⬜)
```

## Performance Considerations

### Query Optimization
- `/project info` calls `get_task_notes()` for each task
- With 15 tasks, this is 15 queries
- Could be optimized with batch query if needed

### Caching Opportunities
- Note counts could be cached for 1 minute
- Assignment data already denormalized in tasks table
- Database queries are indexed by task_id

### Scalability Notes
- Discord embed field limit: 25 fields
- Task display limited to 15 tasks (prevent info overflow)
- Note preview limited to 5 notes (embed text limits)
- Full note history viewable in task details

## Testing Checklist

- [ ] `/project info` displays note indicators correctly
- [ ] `/project info` displays assignment arrows correctly
- [ ] `/project task details` shows all task information
- [ ] 📝 button shows existing notes correctly
- [ ] 📝 button allows assigned users to add notes
- [ ] 📝 button prevents non-assigned users from adding notes
- [ ] ✅ button marks task complete (owner can execute)
- [ ] ✅ button marks task complete (assignee can execute)
- [ ] ✅ button prevents unauthorized users
- [ ] ⬜ button reverts tasks correctly
- [ ] `/project task assign` assigns correctly
- [ ] `/project task assign` owner-only permission works
- [ ] `/project task unassign` removes assignment
- [ ] Notes persist after adding
- [ ] Assignment persists after setting

## Future Enhancements

### High Priority
- **Batch operations:** Assign multiple tasks at once
- **Task dependencies:** Block task A until task B completes
- **Time tracking:** Estimate and track time per task

### Medium Priority
- **Task priority:** Add priority levels with visual indicators
- **Subtasks:** Break down complex tasks
- **Comment threads:** Discord-style comments instead of modal notes

### Low Priority
- **Task templates:** Save common task patterns
- **Recurring tasks:** Set tasks to recur weekly/monthly
- **Task history:** View all past edits and assignments

## Error Handling

### Current Implementation
- Task not found: Ephemeral message "Task not found!"
- Project not found: Ephemeral message "Project not found!"
- Permission denied: Ephemeral message with reason
- Database errors: Try/except with silent failure (could improve)

### Recommended Improvements
- Log all errors to file for debugging
- More specific error messages for users
- Automatic retry on temporary failures
- Error notification to project owner

## Code Quality Notes

### Strengths
✅ Type hints on all methods
✅ Docstrings on classes and commands
✅ Permission checks before operations
✅ Ephemeral responses for security
✅ User-friendly error messages

### Areas for Improvement
- Add logging throughout task operations
- More granular permission system (custom roles?)
- Batch note retrieval instead of per-task
- Database transaction handling
- Unit tests for permission logic

## Integration with LLM System

The note system can enhance LLM capabilities:

```python
# In future LLM commands, read task notes:
notes = await db.get_task_notes(task_id)
context = "\n".join([n['content'] for n in notes])
# Use context in LLM prompt for better recommendations
```

Example: "Generate a summary of blockers from task notes"
