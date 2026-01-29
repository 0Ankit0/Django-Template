from django.urls import include, path, re_path
from . import web_views # Import web views

app_name = 'iam'

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
    path('password/reset/confirm/<uidb64>/<token>/', web_views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password/reset/complete/', web_views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('settings/', web_views.SettingsView.as_view(), name='settings'),
    path('settings/security/', web_views.SecuritySettingsView.as_view(), name='settings_security'),
]

urlpatterns = web_urlpatterns



