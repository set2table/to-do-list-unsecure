class SecurityHeadersMiddleware:
    """Ajoute les en-tetes de securite que ZAP signale par defaut
    (CSP, Referrer-Policy). X-Frame-Options et nosniff sont deja geres
    par les middlewares/reglages Django."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", "default-src 'self'")
        response.setdefault("Referrer-Policy", "no-referrer")
        return response
