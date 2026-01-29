from enum import Enum


class ExportUserArchiveRootPaths(str, Enum):
    LOCAL_ROOT = "tmp"
    S3_ROOT = "exports"


class UserEmails(str, Enum):
    USER_EXPORT = "USER_EXPORT"
    USER_EXPORT_ADMIN = "USER_EXPORT_ADMIN"

class OTPErrors(str, Enum):
    OTP_WRONG_ISSER = "otp_wrong_issuer"
    OTP_VERIFICATION_FAILED = "otp_verification_failed"
    OTP_NOT_VERIFIED = "otp_not_verified"
    VERIFICATION_TOKEN_INVALID = "verification_token_invalid"
