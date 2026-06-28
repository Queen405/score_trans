from __future__ import annotations

from score_trans.api import dependencies
from score_trans.exec import composition


def test_action_factories_share_upload_module(monkeypatch) -> None:
    uploads = object()
    monkeypatch.setattr(composition, "shared_uploads", lambda: uploads)

    assert dependencies.get_file_actions().uploads is uploads
    assert dependencies.get_export_actions().uploads is uploads
    assert dependencies.get_render_actions().uploads is uploads
