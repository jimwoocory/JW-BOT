from .route import Route, RouteContext


class StaticFileRoute(Route):
    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)

        index_ = [
            "/",
            "/auth/login",
            "/config",
            "/logs",
            "/extension",
            "/dashboard/default",
            "/alkaid",
            "/alkaid/knowledge-base",
            "/alkaid/long-term-memory",
            "/alkaid/other",
            "/console",
            "/chat",
            "/settings",
            "/platforms",
            "/providers",
            "/about",
            "/extension-marketplace",
            "/conversation",
            "/tool-use",
            "/hall",
            "/context-monitor",
        ]
        for i in index_:
            self.app.add_url_rule(i, view_func=self.index)

    async def index(self):
        return await self.app.send_static_file("index.html")
