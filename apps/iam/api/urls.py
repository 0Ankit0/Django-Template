from django.urls import include, path, re_path
from rest_framework import routers
from social_django import views as django_social_views
from . import views
from iam.api.views import UserViewSet, GroupViewSet

app_name = 'iam_api'

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
router = routers.DefaultRouter()
router.register(r'profile', views.UserProfileViewSet, basename='profile')
# Admin routers (from original api/urls.py)
router.register(r'users', UserViewSet)
router.register(r'groups', GroupViewSet)

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
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]