from .settings import ToolConfig


class SettingsService:
    def load(self) -> ToolConfig:
        return ToolConfig.from_db()
