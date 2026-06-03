from __future__ import annotations

from ...models.settings.config import ToolConfig
from ...models.settings.schemas import SettingsResponse, SettingsUpdateRequest
from ...services.settings.settings_service import SettingsService


class SettingsActions:
    def __init__(self, service: SettingsService | None = None) -> None:
        self.service = service or SettingsService()

    def get_config(self) -> ToolConfig:
        return self.service.load()

    def get_settings(self) -> SettingsResponse:
        return self._response()

    def update_settings(self, req: SettingsUpdateRequest) -> SettingsResponse:
        config = self.service.load()
        if req.audiveris_path is not None:
            self.service.set("audiveris_path", req.audiveris_path)
            config.audiveris_path = req.audiveris_path

        if req.java_home is not None:
            self.service.set("java_home", req.java_home)
            config.java_home = req.java_home

        if req.output_dir is not None:
            self.service.set("output_dir", req.output_dir)

        if req.ocr_api_key is not None:
            self.service.set("ocr_api_key", req.ocr_api_key)

        if req.ocr_base_url is not None:
            self.service.set("ocr_base_url", req.ocr_base_url)

        if req.ocr_model is not None:
            self.service.set("ocr_model", req.ocr_model)

        if req.ai_api_key is not None:
            self.service.set("ai_api_key", req.ai_api_key)

        if req.ai_base_url is not None:
            self.service.set("ai_base_url", req.ai_base_url)

        if req.ai_model is not None:
            self.service.set("ai_model", req.ai_model)

        if req.omr_preprocess is not None:
            self.service.set("omr_preprocess", "1" if req.omr_preprocess else "0")
            config.omr_preprocess = req.omr_preprocess

        if req.omr_preprocess_long_edge is not None:
            value = max(0, req.omr_preprocess_long_edge)
            self.service.set("omr_preprocess_long_edge", str(value))
            config.omr_preprocess_long_edge = value

        if req.omr_preprocess_binarize is not None:
            self.service.set("omr_preprocess_binarize", "1" if req.omr_preprocess_binarize else "0")
            config.omr_preprocess_binarize = req.omr_preprocess_binarize

        return self._response()

    def _response(self) -> SettingsResponse:
        all_settings = self.service.get_all()
        return SettingsResponse(
            audiveris_path=all_settings.get("audiveris_path", ""),
            java_home=all_settings.get("java_home", ""),
            work_dir=str(self.service.load().work_dir),
            output_dir=all_settings.get("output_dir", ""),
            ocr_api_key=all_settings.get("ocr_api_key", ""),
            ocr_api_key_set=bool(all_settings.get("ocr_api_key", "")),
            ocr_base_url=all_settings.get("ocr_base_url", "https://api.siliconflow.cn/v1"),
            ocr_model=all_settings.get("ocr_model", "deepseek-ai/DeepSeek-OCR"),
            ai_api_key=all_settings.get("ai_api_key", ""),
            ai_api_key_set=bool(all_settings.get("ai_api_key", "")),
            ai_base_url=all_settings.get("ai_base_url", "https://api.siliconflow.cn/v1"),
            ai_model=all_settings.get("ai_model", "Qwen/Qwen3-VL-8B-Instruct"),
            omr_preprocess=self.service.get_bool("omr_preprocess", True),
            omr_preprocess_long_edge=self.service.get_int("omr_preprocess_long_edge", 3600),
            omr_preprocess_binarize=self.service.get_bool("omr_preprocess_binarize", False),
        )
