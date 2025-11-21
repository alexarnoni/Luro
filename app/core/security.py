from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer
from app.core.config import settings


class MagicLinkManager:
    """Manage magic link generation and verification."""
    
    def __init__(self):
        self.serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    
    def generate_token(self, email: str) -> str:
        """Generate a magic link token for the given email."""
        return self.serializer.dumps(email, salt='magic-link')
    
    def verify_token(self, token: str, max_age: int = None) -> str | None:
        """Verify a magic link token and return the email if valid."""
        if max_age is None:
            max_age = settings.MAGIC_LINK_EXPIRY_MINUTES * 60
        
        try:
            email = self.serializer.loads(
                token,
                salt='magic-link',
                max_age=max_age
            )
            return email
        except Exception:
            return None


magic_link_manager = MagicLinkManager()
