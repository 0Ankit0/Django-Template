from dj_control_room_base.core import PanelPlaceholderModel


class SentryPanelPlaceholder(PanelPlaceholderModel):
    class Meta(PanelPlaceholderModel.Meta):
        verbose_name = "Sentry Panel"
        verbose_name_plural = "Sentry Panel"
