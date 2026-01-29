from django.urls import path

from . import views

app_name = 'frontend'

urlpatterns = [
    # Home
    path('', views.HomeView.as_view(), name='home'),
    
    # Authentication
    path('login/', views.LoginView.as_view(), name='login'),
    path('signup/', views.SignupView.as_view(), name='signup'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('otp/verify/', views.OTPVerifyView.as_view(), name='otp_verify'),
    path('otp/enable/', views.OTPEnableView.as_view(), name='otp_enable'),
    path('otp/disable/', views.OTPDisableView.as_view(), name='otp_disable'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='notifications_read_all'),
    
    # Tenants
    path('tenants/', views.TenantListView.as_view(), name='tenants'),
    path('tenants/create/', views.TenantCreateView.as_view(), name='tenant_create'),
    path('tenants/<int:pk>/', views.TenantDetailView.as_view(), name='tenant_detail'),
    path('tenants/<int:pk>/invite/', views.TenantInviteView.as_view(), name='tenant_invite'),
    path('tenants/<int:pk>/switch/', views.switch_tenant, name='tenant_switch'),
    
    # Finances
    path('finances/', views.FinancesView.as_view(), name='finances'),
    path('finances/payment-methods/', views.PaymentMethodsView.as_view(), name='payment_methods'),
    path('finances/subscription/', views.SubscriptionView.as_view(), name='subscription'),
    
    # Settings
    path('settings/', views.SettingsView.as_view(), name='settings'),
    path('settings/profile/', views.ProfileUpdateView.as_view(), name='settings_profile'),
    path('settings/password/', views.PasswordChangeView.as_view(), name='settings_password'),
    path('settings/security/', views.SecuritySettingsView.as_view(), name='settings_security'),
    
    # Documents
    path('documents/', views.DocumentListView.as_view(), name='documents'),
    path('documents/upload/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),
    
    # Integrations
    path('ai-ideas/', views.SaaSIdeasView.as_view(), name='ai_ideas'),
    
    # Products
    path('products/', views.ProductListView.as_view(), name='products'),
]
