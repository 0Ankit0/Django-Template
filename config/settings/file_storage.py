from config.env import env, BASE_DIR

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("DO_SPACES_BUCKET"),
            "access_key": env("DO_SPACES_ACCESS_KEY"),
            "secret_key": env("DO_SPACES_SECRET_KEY"),
            "endpoint_url": env("DO_SPACES_ENDPOINT"),
            "region_name": env("DO_SPACES_REGION"),
            "default_acl": "public-read",
            "querystring_auth": False,
        },
    },
}