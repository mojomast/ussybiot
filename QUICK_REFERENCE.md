# 🎮 Quick Reference - New Commands & Features

## New Commands Added

### `/model`
Switch between different AI models (LLM selection).

**How to use:**
```
/model
→ You're prompted for a password
→ Enter: platypus
→ View available models and click to select
```

**What you'll see:**
- Current model in use
- List of available models (GPT-5-nano, GPT-4o, GPT-4o-mini, etc.)
- One-click buttons to instantly switch models
- No restart needed!

**Password:** `platypus`

**Models available:**
- `openai/gpt-5-nano` - Fast and efficient (current default)
- `openai/gpt-4o` - Most capable, higher quality
- `openai/gpt-4o-mini` - Balanced speed/quality
- Other providers available via Requesty API

**Note:** The password protects this from accidental misuse, but anyone can use it!

---

### `/project task details <task_id>`
Shows detailed task information with interactive controls.

**Display includes:**
- Task name and ID
- Status (Completed/Pending)
- Project association
- Assignment (who it's assigned to)
- Creator information
- All notes (up to 5) with author, date, and content
- Three interactive buttons

**Buttons:**
- 📝 View/Add Note - Show existing notes or add new (assigned users only)
- ✅ Mark Complete - Mark task as done (owner or assignee)
- ⬜ Mark Incomplete - Revert task to pending (owner or assignee)

---

### `/project task assign <task_id> <@user>`
Assign a task to a team member.

**Usage:**
```
/project task assign 5 @Kyle
→ Assigns task 5 to Kyle
→ Kyle can now add notes and mark complete
→ Shows in /project info as → @Kyle
```

**Permissions:**
- Project owners only

---

### `/project task unassign <task_id>`
Remove task assignment.

**Usage:**
```
/project task unassign 5
→ Removes assignment from task 5
→ Task becomes available for reassignment
```

**Permissions:**
- Project owners can unassign anyone
- Assigned users can unassign themselves

---

### Enhanced: `/project info <project_id>`
Now shows assignment and note indicators!

**Display format:**
```
✅ Setup database 📝(2) → @Kyle
⬜ Implement API 📝(4) → @Alex
⬜ Create frontend → @Jordan
✅ Write tests 📝(1)
⬜ Deploy
```

**What it shows:**
- `✅/⬜` - Task completion status
- `📝(n)` - Number of notes on task
- `→ @user` - Who's assigned (if anyone)

**Improvements over before:**
- Shows up to 15 tasks (was 10)
- Note count visible (helps spot active discussion)
- Assignment visible (know who's working on what)

---

## 📊 Permission Matrix

| Action | Owner | Assigned | Team Member |
|--------|:-----:|:--------:|:--------:|
| View project info | ✅ | ✅ | ✅ |
| View task details | ✅ | ✅ | ✅ |
| View notes | ✅ | ✅ | ✅ |
| **Add notes** | ✅ | ✅ | ❌ |
| **Mark complete** | ✅ | ✅ | ❌ |
| **Mark incomplete** | ✅ | ✅ | ❌ |
| **Assign task** | ✅ | ❌ | ❌ |
| **Unassign task** | ✅ | ✅ | ❌ |

---

## 🔄 Common Workflows

### Workflow 1: Delegate Work
```
Owner: /project task assign 7 @Alex
     ↓
Alex can see in: /project info (shows → @Alex)
     ↓
Alex runs: /project task details 7
     ↓
Alex clicks: 📝 View/Add Note
     ↓
Alex adds progress: "Started implementing JWT auth"
     ↓
Owner sees: 📝(1) indicator next to task in /project info
```

### Workflow 2: Quick Status Check
```
Owner/Team: /project info 1
     ↓
See visual status:
  ✅ = done
  ⬜ = pending
  📝 = being discussed
  → @user = who's doing it
     ↓
Owner clicks on task with 📝 to see discussion
```

### Workflow 3: Complete Task
```
Assignee: /project task details 5
     ↓
Review full info and notes
     ↓
Click: ✅ Mark Complete
     ↓
Everyone sees in /project info: ✅ (changed from ⬜)
```

---

## 💡 Pro Tips

**Tip 1: Spot Blockers**
Look for tasks with high note counts (📝(5) or more) in `/project info` - they might be stuck!

**Tip 2: Quick Reassign**
If someone's blocked:
```
/project task unassign 5
/project task assign 5 @NewPerson
```

**Tip 3: Add Notes Early**
Don't wait until task is done - add notes as you go:
- "Starting on this"
- "Hit issue with X"
- "Fixed it! Now testing"
- "Ready for review"

**Tip 4: Use @mentions**
When assigning, use `/project task assign 5 @Username` (Discord will complete it)

**Tip 5: Weekly Review**
Review tasks with many notes during retrospectives - good discussion history!

---

## 🚨 Common Issues & Solutions

**Issue: Can't add note**
- Solution: Only assigned users can add notes. Ask owner to assign you first.

**Issue: Button disabled**
- Solution: You don't have permission. Only owner or assignee can modify tasks.

**Issue: Notes not showing**
- Solution: Notes only appear in `/project task details`. Check there instead of `/project info`.

**Issue: Can't unassign someone else**
- Solution: Only owners can unassign other people. Assigned users can only unassign themselves.

**Issue: Wrong person assigned**
- Solution: Use `/project task unassign` then `/project task assign` to the correct person.

---

## 📱 Mobile-Friendly Commands

All commands work on mobile! Recommended workflow:

1. **Mobile:**
   ```
   /project info 1  (quick status)
   ```

2. **Desktop (optional):**
   ```
   /project task details 5  (see full notes)
   ```

3. **Mobile:**
   ```
   Click 📝 button to add note
   ```

---

## 🎨 Visual Indicators

| Icon | Meaning |
|------|---------|
| ✅ | Task completed |
| ⬜ | Task pending |
| 📝 | Notes on this task |
| → | Assignment arrow |
| 🟢 | Project active |
| 📦 | Project archived |

---

## 🔗 Related Commands (Existing)

These still work and are often used together:

- `/project status` - List all projects
- `/project checklist list <id>` - Toggle buttons for quick marking
- `/project checklist add <id> <task>` - Add new task
- `/project start` - Create new project
- `/project archive <id>` - Close project when done

---

## 📋 Command Hierarchy

```
/project
├── start              (Create project)
├── status             (List projects)
├── info               (View project) ← ENHANCED
├── archive            (Close project)
├── checklist
│   ├── add            (Add task)
│   ├── list           (Toggle tasks)
│   ├── toggle         (Quick mark)
│   └── remove         (Delete task)
└── task               ← NEW
    ├── details        (View task details) ← NEW
    ├── assign         (Assign to user) ← NEW
    └── unassign       (Remove assignment) ← NEW
```

---

## ⚡ Speed Comparison

### Before (Old Way)
```
1. /project info 1                    (see tasks)
2. Look for task                      (scan list)
3. /project checklist toggle 5        (mark complete)
4. /project info 1 again              (refresh)
4 steps + manual tracking
```

### After (New Way)
```
1. /project info 1                    (see EVERYTHING with assignments & notes)
2. /project task details 5            (click for more info)
3. Click ✅ button                    (instant update)
2 steps + automatic tracking
```

**Result: 2x faster workflow! 🚀**

---

## 🎓 Training Checklist for Your Team

- [ ] Show team `/project info` command (explain emoji indicators)
- [ ] Show how to view task details with `/project task details`
- [ ] Demo adding a note (click 📝 button)
- [ ] Demo marking task complete (click ✅ button)
- [ ] Explain permission boundaries
- [ ] Show how owner assigns work (`/project task assign`)
- [ ] Explain note etiquette (add often, be descriptive)
- [ ] Show permission matrix (what each role can do)

---

## 📞 Questions Your Team Might Ask

**Q: Why use notes instead of Discord messages?**
A: Notes stay with the task, organized in one place, not lost in chat.

**Q: Can multiple people work on one task?**
A: Currently one person assigned, but anyone can add notes/review.

**Q: What if I make a mistake in a note?**
A: Note history is kept. Describe the fix in a new note.

**Q: Do notes show in the project thread?**
A: No, only in task details. Intentional for organization.

**Q: Can I assign multiple people to one task?**
A: Currently one primary assignee. Could be enhanced later.

**Q: When should I mark complete vs leave for review?**
A: When YOU are done with it. Leave for review process if needed via notes.

---

## 🎯 Success Metrics

Your new system is working well when:

✅ Team knows exactly what they're working on (assignments visible)
✅ Blockers get identified quickly (high note counts stand out)
✅ Status updates are instant (buttons work fast)
✅ Everyone feels informed (no surprises in updates)
✅ Collaboration increases (notes allow asynchronous discussion)
✅ Fewer Discord message interruptions (notes keep info organized)
✅ Retrospectives have great context (note history shows decisions)

---

**Ready to ship? Let's go BRRRRR! 🚀**
