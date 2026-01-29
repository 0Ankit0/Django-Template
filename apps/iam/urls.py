from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter
from social_django import views as django_social_views

from . import views
from . import web_views # Import web views


# Social auth patterns
social_patterns = [
    # authentication / association
    re_path(r'^login/(?P<backend>[^/]+)/$', django_social_views.auth, name='begin'),
    re_path(r'^complete/(?P<backend>[^/]+)/$', views.complete, name='complete'),
    # disconnection
    re_path(r'^disconnect/(?P<backend>[^/]+)/$', django_social_views.disconnect, name='disconnect'),
    re_path(
        r'^disconnect/(?P<backend>[^/]+)/(?P<association_id>\d+)/$',
        django_social_views.disconnect,
        name='disconnect_individual',
    ),
]

# Profile router
router = DefaultRouter()
router.register(r'profile', views.UserProfileViewSet, basename='profile')

user_patterns = [
    # JWT Auth
    path("token-refresh/", views.CookieTokenRefreshView.as_view(), name="jwt_token_refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),

    # User Registration & Confirmation
    path("signup/", views.UserSignupView.as_view(), name='signup'),
    path("confirm/", views.UserAccountConfirmView.as_view(), name='confirm-email'),

    # Password Management
    path("password/reset/", views.PasswordResetView.as_view(), name='password-reset'),
    path("password/reset/confirm/", views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path("password/change/", views.PasswordChangeView.as_view(), name='password-change'),

    # OTP / 2FA
    path("otp/generate/", views.OTPGenerateView.as_view(), name='otp-generate'),
    path("otp/verify/", views.OTPVerifyView.as_view(), name='otp-verify'),
    path("otp/disable/", views.OTPDisableView.as_view(), name='otp-disable'),

    # Social Auth
    path('social/', include((social_patterns, 'social'), namespace='social')),
]

# User me endpoint
profile_patterns = [
    path('me/', views.UserProfileViewSet.as_view({'get': 'me', 'patch': 'update_me', 'put': 'update_me'}), name='user-me'),
]

urlpatterns = [
    path("auth/", include(user_patterns)),
    path("users/", include(profile_patterns)),
    path("users/", include(router.urls)),
    path("users/", include(router.urls)),
]

# Web URL patterns
web_urlpatterns = [
    path('login/', web_views.LoginView.as_view(), name='login'),
    path('signup/', web_views.SignupView.as_view(), name='signup'),
    path('logout/', web_views.LogoutView.as_view(), name='logout'),
    path('otp/verify/', web_views.OTPVerifyView.as_view(), name='otp_verify'),
    path('otp/enable/', web_views.OTPEnableView.as_view(), name='otp_setup'),
    path('otp/disable/', web_views.OTPDisableView.as_view(), name='otp_disable'),
    path('password/reset/', web_views.PasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', web_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('settings/', web_views.SettingsView.as_view(), name='settings'),
    path('settings/profile/', web_views.ProfileUpdateView.as_view(), name='settings_profile'),
    path('settings/password/', web_views.PasswordChangeView.as_view(), name='settings_password'),
    path('settings/security/', web_views.SecuritySettingsView.as_view(), name='settings_security'),
]

urlpatterns += web_urlpatterns

