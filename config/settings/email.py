from config.env import env

EMAIL_HOST='smtp.google.com'
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST_USER= env.email('EMAIL_HOST_USER')
DEFAULT_FROM_EMAIL= env('EMAIL_HOST_USER')  
ACCOUNT_EMAIL_SUBJECT_PREFIX='[Django-Template]'
EMAIL_HOST_PASSWORD= env('EMAIL_HOST_PASSWORD')
