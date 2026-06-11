from django.apps import AppConfig

from commons.design import verify_cjk_font_available


class CommonsConfig(AppConfig):
    name = "commons"

    def ready(self) -> None:
        """Fail loudly at startup if no CJK-capable font is installed."""
        verify_cjk_font_available()
