"""
BRRR Bot - LLM Integration via Requesty.ai
Uses OpenAI-compatible API for inference
"""

import aiohttp
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    memories_to_save: List[Dict[str, str]]  # [{key, value, context}]
    usage: Dict[str, int]


class LLMClient:
    """Requesty.ai LLM client - OpenAI compatible API"""
    
    BASE_URL = "https://router.requesty.ai/v1"
    
    def __init__(self, api_key: str, model: str = "openai/gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _build_system_prompt(self, user_memories: Dict[str, Any], user_name: str) -> str:
        """Build the system prompt with user memories"""
        
        memory_context = ""
        if user_memories:
            memory_lines = []
            for key, data in user_memories.items():
                if isinstance(data, dict):
                    memory_lines.append(f"- {key}: {data.get('value', data)}")
                else:
                    memory_lines.append(f"- {key}: {data}")
            memory_context = f"\n\n**What I remember about {user_name}:**\n" + "\n".join(memory_lines)
        
        return f"""You are BRRR Bot, an energetic and helpful assistant for the BRRR Discord server focused on weekly coding projects.

**Your personality:**
- You go brrrrrrrrr (fast, efficient, high-energy)
- You're enthusiastic about coding projects and helping people build cool stuff
- You keep responses concise but helpful
- You use occasional "brrr" sounds when excited
- You're supportive and encourage people to ship their projects

**Your capabilities:**
- Help plan and manage weekly coding projects
- Answer coding questions
- Remember things about users to personalize interactions
- Provide encouragement and motivation

**Memory System:**
You can remember things about users. When you learn something worth remembering about a user (their preferences, skills, current projects, interests, timezone, etc.), you should include it in your response using this JSON format at the END of your message:

```json
{{"memories": [{{"key": "skill_python", "value": "advanced", "context": "mentioned they've been coding Python for 5 years"}}]}}
```

Memory keys should be descriptive like: current_project, skill_<language>, interest_<topic>, timezone, preferred_name, etc.
Only save memories that would be useful for future interactions. Don't save trivial or temporary information.
{memory_context}

**Current context:**
You're chatting with {user_name}.

Remember: You're here to help make weekly projects go BRRRRR! 🚀"""

    async def chat(
        self,
        messages: List[Dict[str, str]],
        user_memories: Dict[str, Any] = None,
        user_name: str = "User",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Send a chat completion request"""
        
        await self.ensure_session()
        
        system_prompt = self._build_system_prompt(user_memories or {}, user_name)
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.session.post(
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"LLM API error {response.status}: {error_text}")
            
            data = await response.json()
        
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        
        # Extract memories from response
        memories_to_save = []
        clean_content = content
        
        # Look for JSON memory block at the end
        if "```json" in content and '"memories"' in content:
            try:
                json_start = content.rfind("```json")
                json_end = content.rfind("```", json_start + 7)
                if json_start != -1 and json_end != -1:
                    json_str = content[json_start + 7:json_end].strip()
                    memory_data = json.loads(json_str)
                    if "memories" in memory_data:
                        memories_to_save = memory_data["memories"]
                    # Remove the JSON block from the displayed content
                    clean_content = content[:json_start].strip()
            except (json.JSONDecodeError, KeyError):
                pass  # No valid memory JSON found
        
        return LLMResponse(
            content=clean_content,
            memories_to_save=memories_to_save,
            usage=usage
        )
    
    async def generate_project_plan(
        self,
        project_title: str,
        project_description: str,
        user_context: str = ""
    ) -> str:
        """Generate a project plan/checklist"""
        
        await self.ensure_session()
        
        prompt = f"""Generate a concise project checklist for:

**Project:** {project_title}
**Description:** {project_description}
{f"**Context:** {user_context}" if user_context else ""}

Create 5-10 actionable tasks that break down this project into manageable steps.
Format each task as a simple one-line item.
Focus on the most important tasks to ship an MVP.

Respond with ONLY the task list, one task per line, no numbering or bullets."""

        messages = [{"role": "user", "content": prompt}]
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a project planning assistant. Be concise and practical."},
                *messages
            ],
            "temperature": 0.5,
            "max_tokens": 500
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.session.post(
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"LLM API error {response.status}: {error_text}")
            
            data = await response.json()
        
        return data["choices"][0]["message"]["content"]
    
    async def generate_retro_summary(self, project_title: str, tasks: List[Dict]) -> str:
        """Generate a retrospective summary"""
        
        await self.ensure_session()
        
        completed = [t for t in tasks if t.get('is_done')]
        incomplete = [t for t in tasks if not t.get('is_done')]
        
        prompt = f"""Generate a brief retro summary for this week's project:

**Project:** {project_title}
**Completed tasks:** {len(completed)}/{len(tasks)}
**Done:** {', '.join(t['label'] for t in completed) if completed else 'None'}
**Not done:** {', '.join(t['label'] for t in incomplete) if incomplete else 'All done!'}

Write a 2-3 sentence summary celebrating wins and noting what to carry forward.
Be encouraging and positive!"""

        messages = [{"role": "user", "content": prompt}]
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are BRRR Bot, celebrating weekly project progress. Be enthusiastic!"},
                *messages
            ],
            "temperature": 0.7,
            "max_tokens": 200
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.session.post(
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"LLM API error {response.status}: {error_text}")
            
            data = await response.json()
        
        return data["choices"][0]["message"]["content"]
