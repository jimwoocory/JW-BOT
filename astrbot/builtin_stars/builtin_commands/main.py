from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, MessageEventResult, filter

from .commands import (
    AdminCommands,
    CaseCommands,
    ConversationCommands,
    HelpCommand,
    ProviderCommands,
    SetUnsetCommands,
    SIDCommand,
)


class Main(star.Star):
    def __init__(self, context: star.Context) -> None:
        self.context = context

        self.admin_c = AdminCommands(self.context)
        self.case_c = CaseCommands(self.context)
        self.conversation_c = ConversationCommands(self.context)
        self.help_c = HelpCommand(self.context)
        self.provider_c = ProviderCommands(self.context)
        self.setunset_c = SetUnsetCommands(self.context)
        self.sid_c = SIDCommand(self.context)

    @filter.command("help")
    async def help(self, event: AstrMessageEvent) -> None:
        """Show help message"""
        await self.help_c.help(event)

    @filter.command("sid")
    async def sid(self, event: AstrMessageEvent) -> None:
        """Get session ID and other related information"""
        await self.sid_c.sid(event)

    @filter.command("reset")
    async def reset(self, message: AstrMessageEvent) -> None:
        """Reset conversation history"""
        await self.conversation_c.reset(message)

    @filter.command("stop")
    async def stop(self, message: AstrMessageEvent) -> None:
        """Stop agent execution"""
        await self.conversation_c.stop(message)

    @filter.command("new")
    async def new_conv(self, message: AstrMessageEvent) -> None:
        """Create new conversation"""
        await self.conversation_c.new_conv(message)

    @filter.command("stats")
    async def stats(self, message: AstrMessageEvent) -> None:
        """Show token usage statistics for the current conversation"""
        await self.conversation_c.stats(message)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("provider")
    async def provider(
        self,
        event: AstrMessageEvent,
        idx: str | int | None = None,
        idx2: int | None = None,
    ) -> None:
        """View or switch LLM Provider"""
        await self.provider_c.provider(event, idx, idx2)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("dashboard_update")
    async def update_dashboard(self, event: AstrMessageEvent) -> None:
        """Update AstrBot WebUI"""
        await self.admin_c.update_dashboard(event)

    @filter.command("set")
    async def set_variable(self, event: AstrMessageEvent, key: str, value: str) -> None:
        """Set session variable"""
        await self.setunset_c.set_variable(event, key, value)

    @filter.command("unset")
    async def unset_variable(self, event: AstrMessageEvent, key: str) -> None:
        """Unset session variable"""
        await self.setunset_c.unset_variable(event, key)

    @filter.command("case")
    async def case(
        self,
        event: AstrMessageEvent,
        sub: str = "",
        *args: str,
    ) -> None:
        """Case 聚合层操作。子命令: new/context/list/attach/archive/status"""
        sub_normalized = (sub or "").strip().lower()
        rest = " ".join(args).strip()

        if sub_normalized == "new":
            await self.case_c.case_new(event, rest)
        elif sub_normalized in ("context", "ctx"):
            await self.case_c.case_context(event)
        elif sub_normalized in ("list", "ls"):
            await self.case_c.case_list(event)
        elif sub_normalized == "attach":
            await self.case_c.case_attach(event, rest)
        elif sub_normalized == "archive":
            await self.case_c.case_archive(event)
        elif sub_normalized == "status":
            await self.case_c.case_status(event, rest)
        else:
            event.set_result(
                MessageEventResult()
                .message(
                    "用法:\n"
                    "  /case new <名称> [--client <甲方>]\n"
                    "  /case context\n"
                    "  /case list\n"
                    "  /case attach <task_id>\n"
                    "  /case archive\n"
                    "  /case status <状态>",
                )
                .use_t2i(False),
            )
