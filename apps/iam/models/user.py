import hashid_field
from core.models.mixins import ImageWithThumbnailMixin
from core.storage import UniqueFilePathGenerator
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, Group, PermissionsMixin
from django.db import models
from django.utils.module_loading import import_string

from config.settings import DEFAULT_FILE_STORAGE


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, username=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")

        normalized_email = self.normalize_email(email)
        # Use email as username if username is not provided
        if not username:
            username = normalized_email

        user = self.model(email=normalized_email, username=username, **extra_fields)
        user.set_password(password)
        user_group, _ = Group.objects.get_or_create(name=settings.DEFAULT_USER_GROUP)
        user.save(using=self._db)

        user.groups.add(user_group)

        UserProfile.objects.create(user=user)

        from multitenancy.models.tenant_membership import TenantMembership

        TenantMembership.objects.associate_invitations_with_user(normalized_email, user)

        return user

    def create_superuser(self, email=None, password=None, username=None, **extra_fields):
        # If username is provided but not email, use username as email
        if username and not email:
            email = username
        elif not email and not username:
            raise ValueError("Email or username must be provided")

        # Set defaults for superuser
        extra_fields.setdefault("is_superuser", True)

        user = self.create_user(email=email, password=password, username=username, **extra_fields)
        user.is_superuser = True
        user.save(using=self._db)

        return user

    # def filter_admins(self):
    #     return self.filter(groups__name=CommonGroups.Admin)


class User(AbstractBaseUser, PermissionsMixin):
    id = hashid_field.HashidAutoField(primary_key=True)
    created = models.DateTimeField(editable=False, auto_now_add=True)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(
        # db_collation="case_insensitive", # Postgres only
        verbose_name="email address",
        max_length=255,
        unique=True,
    )
    is_confirmed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)

    otp_enabled = models.BooleanField(default=False)
    otp_verified = models.BooleanField(default=False)
    otp_base32 = models.CharField(max_length=255, blank=True, default="")
    otp_auth_url = models.CharField(max_length=255, blank=True, default="")

    groups = models.ManyToManyField(
        "iam.Group",
        verbose_name="groups",
        blank=True,
        help_text="The groups this user belongs to.",
        related_name="user_set",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        "iam.Permission",
        verbose_name="user permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        related_name="user_set",
        related_query_name="user",
    )

    objects = UserManager()

    USERNAME_FIELD = "username"

    def __str__(self) -> str:
        return self.username

    @property
    def is_staff(self):
        return self.is_superuser

    def has_group(self, name):
        return self.groups.filter(name=name).exists()


class UserAvatar(ImageWithThumbnailMixin, models.Model):
    original = models.ImageField(
        storage=import_string(DEFAULT_FILE_STORAGE)(), upload_to=UniqueFilePathGenerator("avatars"), null=True
    )
    thumbnail = models.ImageField(
        storage=import_string(DEFAULT_FILE_STORAGE)(),
        upload_to=UniqueFilePathGenerator("avatars/thumbnails"),
        null=True,
    )

    THUMBNAIL_SIZE = (128, 128)
    ERROR_FIELD_NAME = "avatar"

    def __str__(self) -> str:
        return str(self.id)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    first_name = models.CharField(max_length=40, blank=True, default="")
    last_name = models.CharField(max_length=40, blank=True, default="")
    avatar = models.OneToOneField(
        UserAvatar, on_delete=models.SET_NULL, null=True, blank=True, related_name="user_profile"
    )

    def __str__(self) -> str:
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.user.email
