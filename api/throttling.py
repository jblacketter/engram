from rest_framework.throttling import SimpleRateThrottle


class ReadRateThrottle(SimpleRateThrottle):
    scope = "read"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class WriteRateThrottle(SimpleRateThrottle):
    scope = "write"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
