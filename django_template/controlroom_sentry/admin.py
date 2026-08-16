from django.contrib import admin
from unfold.admin import ModelAdmin
from dj_control_room_base.core import BasePanelAdmin

from .conf import panel_config
from .models import SentryPanelPlaceholder


@admin.register(SentryPanelPlaceholder)
class SentryPanelPlaceholderAdmin(BasePanelAdmin, ModelAdmin):
    redirect_url_name = "controlroom_sentry:index"
    panel_config = panel_config
