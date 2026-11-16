import hashlib

from django.contrib.auth.hashers import BasePasswordHasher
from django.utils.crypto import constant_time_compare


class LegacySHA256PasswordHasher(BasePasswordHasher):
    """
    Verifies passwords from the old PHP site, which stored hash('sha256', $pw)
    with no salt.  Stored here as ``legacy_sha256$$<hex>``.

    It is listed second in PASSWORD_HASHERS, so it is only ever used to check
    an old password; on the first successful login the account is re-hashed
    with PBKDF2.
    """

    algorithm = "legacy_sha256"

    def salt(self):
        return ""

    def encode(self, password, salt):
        digest = hashlib.sha256(password.encode()).hexdigest()
        return f"{self.algorithm}$${digest}"

    def decode(self, encoded):
        return {"algorithm": self.algorithm, "hash": encoded.split("$", 2)[2], "salt": ""}

    def verify(self, password, encoded):
        return constant_time_compare(encoded, self.encode(password, ""))

    def safe_summary(self, encoded):
        return {"algorithm": self.algorithm}

    def must_update(self, encoded):
        return True

    def harden_runtime(self, password, encoded):
        pass
