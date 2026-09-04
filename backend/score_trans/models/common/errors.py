from __future__ import annotations


class ExternalToolError(RuntimeError):
    """Raised when an external CLI tool fails.

    Carries optional ``stdout``/``stderr`` attributes with the raw captured
    output so callers can inspect details without it being dumped into the
    user-facing message via ``str()``.
    """

    def __init__(
        self,
        message: str,
        *,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


class OCRError(RuntimeError):
    """Raised when OCR provider calls or response parsing fail."""


class AITranscriptionError(RuntimeError):
    """Raised when AI score transcription calls or response parsing fail."""


class RenderError(RuntimeError):
    """Raised when score rendering cannot produce a usable output."""


class UploadTooLargeError(ValueError):
    """Raised when an uploaded file or request exceeds its configured limit."""


class CodedValidationError(ValueError):
    """A validation error carrying a stable machine-readable code.

    The API layer registers a dedicated handler for this class so subclasses
    are dispatched ahead of plain ``ValueError`` (Starlette walks the MRO) and
    produce ``{"error", "stage": "validation", "code"}`` responses.
    """

    error_code: str = ""


class JianpuValidationError(CodedValidationError):
    """Raised when Jianpu input cannot be rendered or exported."""

    error_code = "jianpu_syntax"


class MultiVoiceNotSupportedError(CodedValidationError):
    """声部内含多个 voice，简谱文本无法无损表达。

    简谱文本格式只有 ``// @part`` 一级多声部概念，没有 voice 级表达。
    当一个 MusicXML part 内同时存在多个 voice（复调、钢琴同谱双 voice 等），
    经简谱文本中转会把并行的音符串行化，小节时值翻倍且不可逆。

    注意：默认转换路径（``scores_to_jianpu_document``）不再自动抛出本异常——
    因为 OMR（Audiveris）常把单声部旋律伪拆成多个 voice，硬拦截会阻断整个
    识别流程。默认行为改为「拍平为单声部输出 + 警告日志」。本异常保留供需要
    严格止损的调用方显式抛出（如未来引入 ``strict_multi_voice`` 选项时）。
    """

    error_code = "multi_voice_not_supported"
