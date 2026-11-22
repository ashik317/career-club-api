from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"

class EmailRateThrottle(AnonRateThrottle):
    scope = "email_send"

class RegisterRateThrottle(AnonRateThrottle):
    scope = "register"