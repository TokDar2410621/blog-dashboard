from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginThrottle(AnonRateThrottle):
    scope = 'login'


class AIGenerateThrottle(UserRateThrottle):
    scope = 'ai_generate'
