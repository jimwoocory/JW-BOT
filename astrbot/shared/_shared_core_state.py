from __future__ import annotations

import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PermissionMode(Enum):
    DEFAULT = "default"
    PLAN = "plan"
    BYPASS = "bypass"
    AUTO = "auto"


@dataclass
class PermissionRule:
    pattern: str
    allow: bool


class PermissionManager:
    def __init__(self):
        self.rules = []
        self.mode = PermissionMode.DEFAULT
        self._add_default_rules()

    def _add_default_rules(self):
        self.add_rule("FileRead(*)", allow=True)
        self.add_rule("Bash(git *)", allow=True)
        self.add_rule("ClawTeam(*)", allow=True)

    def add_rule(self, pattern, allow):
        self.rules.append(PermissionRule(pattern=pattern, allow=allow))

    def set_mode(self, mode):
        self.mode = mode

    def get_rules(self):
        return [deepcopy(rule) for rule in self.rules]


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    LOCAL_SHELL = "local_shell"
    DREAM = "dream"


@dataclass
class Task:
    id: str
    type: TaskType
    status: TaskStatus
    created_at: datetime
    started_at: datetime = None
    completed_at: datetime = None
    payload: dict = field(default_factory=dict)
    result: object = None
    error: str = None
    progress: float = 0.0
    logs: list = field(default_factory=list)


class TaskManager:
    def __init__(self):
        self.tasks = {}

    def create_task(self, task_type, payload=None):
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            type=task_type,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            payload=deepcopy(payload or {}),
        )
        self.tasks[task_id] = task
        return task_id

    def list_tasks(self, status=None, task_type=None):
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if task_type:
            tasks = [t for t in tasks if t.type == task_type]
        return [
            deepcopy(task)
            for task in sorted(tasks, key=lambda t: t.created_at, reverse=True)
        ]

    def get_task(self, task_id):
        task = self.tasks.get(task_id)
        return deepcopy(task) if task else None


@dataclass
class Memory:
    id: str
    content: str
    source: str
    created_at: datetime
    importance: float = 0.5
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class MemoryManager:
    def __init__(self):
        self.memories = {}

    def add_memory(self, content, source="manual", importance=0.5, tags=None):
        memory_id = str(uuid.uuid4())
        memory = Memory(
            id=memory_id,
            content=content,
            source=source,
            created_at=datetime.now(),
            importance=importance,
            tags=deepcopy(tags or []),
        )
        self.memories[memory_id] = memory
        return memory_id

    def list_memories(self, source=None, limit=100):
        memories = list(self.memories.values())
        if source:
            memories = [m for m in memories if m.source == source]
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return [deepcopy(memory) for memory in memories[:limit]]

    def search_memories(self, query, limit=10, min_importance=0.0):
        results = []
        query_lower = query.lower()
        for memory in self.memories.values():
            if memory.importance < min_importance:
                continue
            if query_lower in memory.content.lower():
                results.append(memory)
        results.sort(key=lambda m: m.importance, reverse=True)
        return [deepcopy(memory) for memory in results[:limit]]

    def compress_memories(self, max_age_days=30):
        cutoff = time.time() - (max_age_days * 86400)
        to_compress = []
        for memory_id, memory in list(self.memories.items()):
            if memory.created_at.timestamp() < cutoff:
                to_compress.append(memory_id)
        for memory_id in to_compress:
            memory = self.memories[memory_id]
            memory.importance *= 0.5
        return len(to_compress)
