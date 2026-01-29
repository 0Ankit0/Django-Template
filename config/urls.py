"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers,urls
from iam import views
from core import views as core_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # App URLs
    path('', include('core.urls')),
    path('iam/', include('iam.urls')),
    path('multitenancy/', include('multitenancy.urls')),
    path('finances/', include('finances.urls')),
    path('notifications/', include('notifications.urls')),
    path('content/', include('content.urls')),
    path('integrations/', include('integrations.urls')),
    # API URLs
    path('api/', include('config.urls_api')),

    # Test URLs for error pages
    path('test-400/', core_views.custom_400_view, name='test-400'),
    path('test-403/', core_views.custom_403_view, name='test-403'),
    path('test-404/', core_views.custom_404_view, name='test-404'),
    path('test-500/', core_views.custom_500_view, name='test-500'),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)