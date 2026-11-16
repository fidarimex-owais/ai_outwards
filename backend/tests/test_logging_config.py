import logging

import app.main  # noqa: F401 - importing this module runs its logging.basicConfig() call
from app.core.config import settings


def test_app_import_configures_info_level_for_app_loggers():
    # This test assumes the default LOG_LEVEL ("INFO") is in effect - if that default ever
    # changes, update this assertion rather than letting it pass for the wrong reason.
    assert settings.log_level == "INFO"

    effective_level = logging.getLogger("app.features.llm.gemini").getEffectiveLevel()
    assert effective_level == logging.INFO
