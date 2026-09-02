"""
Bot Protection Module:
- Cloudflare Turnstile verification (privacy-friendly, recommended)
- Google reCAPTCHA v3 support (fallback)
- User-Agent validation and bot detection
- Integration with rate limiting for enhanced protection
"""
from fastapi import Request, HTTPException, Depends
from typing import Optional
import httpx
import re
from app.core.config import get_settings
from app.infra.cache.redis_client import get_redis

settings = get_settings()

# ============================================================
# Bot Detection Patterns
# ============================================================

# Known bot user agent patterns (case-insensitive)
BOT_UA_PATTERNS = [
    # Generic bots/crawlers
    r"bot", r"crawler", r"spider", r"scraper", r"scanner",
    # Common tools
    r"curl", r"wget", r"python", r"go-http", r"java/", r"perl", r"ruby",
    r"axios", r"fetch", r"node", r"php", r"scrapy", r"selenium",
    r"webdriver", r"phantomjs", r"headless", r"puppeteer", r"playwright",
    # SEO/Marketing bots
    r"ahrefs", r"semrush", r"majestic", r"moz", r"screaming", r"sitebulb",
    # Security scanners
    r"nmap", r"nessus", r"openvas", r"burp", r"zap", r"sqlmap",
    # Generic automation
    r"automation", r"script", r"monitor", r"check", r"uptime",
]

# Suspicious patterns that need additional verification
SUSPICIOUS_UA_PATTERNS = [
    r"^$",  # Empty UA
    r"^.{1,10}$",  # Too short
    r"mozilla/5\.0$",  # Generic incomplete
    r"^mozilla/5\.0 \([^)]*\) applewebkit/537\.36$",  # Incomplete Chrome
]

# Known good bot user agents (allowlist)
GOOD_BOT_UAS = [
    "googlebot",
    "bingbot",
    "slurp",  # Yahoo
    "duckduckbot",
    "baiduspider",
    "yandexbot",
    "facebookexternalhit",
    "twitterbot",
    "linkedinbot",
    "whatsapp",
    "telegrambot",
    "slackbot",
    "discordbot",
]

# Compile patterns for performance
BOT_REGEX = re.compile("|".join(BOT_UA_PATTERNS), re.IGNORECASE)
SUSPICIOUS_REGEX = re.compile("|".join(SUSPICIOUS_UA_PATTERNS), re.IGNORECASE)
GOOD_BOT_REGEX = re.compile("|".join(GOOD_BOT_UAS), re.IGNORECASE)


# ============================================================
# Turnstile Verification (Cloudflare)
# ============================================================

class TurnstileVerifier:
    """Cloudflare Turnstile verification - privacy-friendly, no cookies."""
    
    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or settings.turnstile_secret
    
    async def verify(self, token: str, ip: str = None) -> tuple[bool, dict]:
        """
        Verify Turnstile token.
        Returns (success, response_data)
        """
        if not self.secret_key:
            # Not configured - allow in dev, block in prod
            if settings.env == "development":
                return True, {"success": True, "bypass": "dev_mode"}
            return False, {"success": False, "error": "Turnstile not configured"}
        
        if not token:
            return False, {"success": False, "error": "Missing token"}
        
        data = {
            "secret": self.secret_key,
            "response": token,
        }
        if ip:
            data["remoteip"] = ip
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.VERIFY_URL, data=data)
                result = resp.json()
                return result.get("success", False), result
        except httpx.TimeoutException:
            return False, {"success": False, "error": "Verification timeout"}
        except Exception as e:
            return False, {"success": False, "error": str(e)}


# ============================================================
# reCAPTCHA v3 Verification (Google)
# ============================================================

class RecaptchaVerifier:
    """Google reCAPTCHA v3 verification."""
    
    VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or settings.recaptcha_secret
        # Score threshold (0.0 - 1.0), higher = more strict
        self.min_score = 0.5
    
    async def verify(self, token: str, ip: str = None, action: str = None) -> tuple[bool, dict]:
        """
        Verify reCAPTCHA v3 token.
        Returns (success, response_data)
        """
        if not self.secret_key:
            if settings.env == "development":
                return True, {"success": True, "score": 0.9, "bypass": "dev_mode"}
            return False, {"success": False, "error": "reCAPTCHA not configured"}
        
        if not token:
            return False, {"success": False, "error": "Missing token"}
        
        data = {
            "secret": self.secret_key,
            "response": token,
        }
        if ip:
            data["remoteip"] = ip
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.VERIFY_URL, data=data)
                result = resp.json()
                
                success = result.get("success", False)
                score = result.get("score", 0.0)
                action_name = result.get("action", "")
                
                # Check score threshold
                if success and score >= self.min_score:
                    # Optionally verify action matches expected
                    if action and action_name != action:
                        return False, {"success": False, "error": "Action mismatch", "score": score}
                    return True, result
                
                return False, {"success": False, "error": "Low score", "score": score}
        except httpx.TimeoutException:
            return False, {"success": False, "error": "Verification timeout"}
        except Exception as e:
            return False, {"success": False, "error": str(e)}


# ============================================================
# User-Agent Analyzer
# ============================================================

class UserAgentAnalyzer:
    """Analyze User-Agent strings for bot detection."""
    
    @staticmethod
    def analyze(ua: str) -> dict:
        """
        Analyze User-Agent string.
        Returns dict with: is_bot, is_suspicious, is_known_good, risk_score, details
        """
        if not ua:
            return {
                "is_bot": False,
                "is_suspicious": True,
                "is_known_good": False,
                "risk_score": 80,
                "details": ["Missing User-Agent header"]
            }
        
        ua_lower = ua.lower()
        
        # Check known good bots first (allowlist)
        if GOOD_BOT_REGEX.search(ua_lower):
            return {
                "is_bot": True,
                "is_suspicious": False,
                "is_known_good": True,
                "risk_score": 10,
                "details": ["Known good bot (search engine/social)"]
            }
        
        # Check for malicious bot patterns
        bot_matches = BOT_REGEX.findall(ua_lower)
        if bot_matches:
            return {
                "is_bot": True,
                "is_suspicious": True,
                "is_known_good": False,
                "risk_score": 90,
                "details": [f"Bot pattern detected: {m}" for m in set(bot_matches)][:5]
            }
        
        # Check suspicious patterns
        suspicious_matches = SUSPICIOUS_REGEX.findall(ua_lower)
        if suspicious_matches:
            return {
                "is_bot": False,
                "is_suspicious": True,
                "is_known_good": False,
                "risk_score": 60,
                "details": [f"Suspicious UA pattern: {m}" for m in set(suspicious_matches)]
            }
        
        # Check for missing common browser features
        details = []
        risk = 0
        
        # Should have Mozilla, browser name, version
        if "mozilla" not in ua_lower:
            details.append("Missing 'Mozilla' token")
            risk += 20
        
        # Common browsers
        has_browser = any(b in ua_lower for b in ["chrome", "firefox", "safari", "edge", "opera"])
        if not has_browser:
            details.append("Unknown browser")
            risk += 30
        
        # Mobile check
        is_mobile = "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower
        
        return {
            "is_bot": False,
            "is_suspicious": risk > 30,
            "is_known_good": False,
            "risk_score": min(100, risk),
            "details": details,
            "is_mobile": is_mobile,
            "ua_length": len(ua)
        }


# ============================================================
# Bot Protection Manager
# ============================================================

class BotProtectionManager:
    """Main bot protection coordinator."""
    
    def __init__(self):
        self.turnstile = TurnstileVerifier()
        self.recaptcha = RecaptchaVerifier()
        self.ua_analyzer = UserAgentAnalyzer()
        self.enabled = settings.bot_protection_enabled
    
    async def verify_request(
        self,
        request: Request,
        turnstile_token: str = None,
        recaptcha_token: str = None,
        recaptcha_action: str = None,
        required: bool = True
    ) -> dict:
        """
        Comprehensive bot verification.
        Returns verification result dict.
        """
        if not self.enabled:
            return {"allowed": True, "bypass": "disabled"}
        
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "")
        
        results = {
            "allowed": True,
            "ip": ip,
            "ua_analysis": self.ua_analyzer.analyze(ua),
            "turnstile": None,
            "recaptcha": None,
        }
        
        # 1. User-Agent analysis (always run)
        ua_result = results["ua_analysis"]
        if ua_result["is_known_good"]:
            # Known good bot (search engine) - allow
            return {**results, "allowed": True, "reason": "known_good_bot"}
        
        if ua_result["is_bot"] and ua_result["risk_score"] > 80:
            # High-confidence malicious bot - block immediately
            return {
                **results,
                "allowed": False,
                "reason": "malicious_bot_detected",
                "error": "Automated access detected"
            }
        
        # 2. Turnstile verification (preferred)
        if turnstile_token:
            success, data = await self.turnstile.verify(turnstile_token, ip)
            results["turnstile"] = {"success": success, "data": data}
            if success:
                return {**results, "allowed": True, "reason": "turnstile_verified"}
            elif required:
                return {**results, "allowed": False, "reason": "turnstile_failed", "error": "Bot verification failed"}
        
        # 3. reCAPTCHA verification (fallback)
        if recaptcha_token:
            success, data = await self.recaptcha.verify(recaptcha_token, ip, recaptcha_action)
            results["recaptcha"] = {"success": success, "data": data}
            if success:
                return {**results, "allowed": True, "reason": "recaptcha_verified"}
            elif required:
                return {**results, "allowed": False, "reason": "recaptcha_failed", "error": "Bot verification failed"}
        
        # 4. No token provided - check if required
        sensitive_paths = [
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/verify-email",
            "/api/v1/support/chatbot",
        ]
        
        if required and any(request.url.path.startswith(p) for p in sensitive_paths):
            # Check if UA is suspicious enough to require challenge
            if ua_result["is_suspicious"] or ua_result["risk_score"] > 40:
                return {
                    **results,
                    "allowed": False,
                    "reason": "challenge_required",
                    "error": "Bot verification required",
                    "challenge_types": ["turnstile", "recaptcha"]
                }
        
        return results


# Global instance
bot_protection = BotProtectionManager()


# ============================================================
# FastAPI Dependencies
# ============================================================

async def verify_bot_protection(
    request: Request,
    turnstile_token: Optional[str] = None,
    recaptcha_token: Optional[str] = None,
    recaptcha_action: Optional[str] = None,
) -> dict:
    """
    FastAPI dependency for bot protection.
    Usage:
        @router.post("/login")
        async def login(..., bot_result: dict = Depends(verify_bot_protection)):
    """
    # Get tokens from headers if not provided as params
    if not turnstile_token:
        turnstile_token = request.headers.get("X-Turnstile-Token")
    if not recaptcha_token:
        recaptcha_token = request.headers.get("X-Recaptcha-Token")
    if not recaptcha_action:
        recaptcha_action = request.headers.get("X-Recaptcha-Action")
    
    result = await bot_protection.verify_request(
        request,
        turnstile_token=turnstile_token,
        recaptcha_token=recaptcha_token,
        recaptcha_action=recaptcha_action,
        required=True
    )
    
    if not result["allowed"]:
        # Add headers for client to know what challenge to show
        headers = {}
        if "challenge_types" in result:
            headers["X-Challenge-Types"] = ",".join(result["challenge_types"])
        if result.get("turnstile", {}).get("data", {}).get("error"):
            headers["X-Turnstile-Error"] = result["turnstile"]["data"]["error"]
        if result.get("recaptcha", {}).get("data", {}).get("error"):
            headers["X-Recaptcha-Error"] = result["recaptcha"]["data"]["error"]
        
        raise HTTPException(
            status_code=403,
            detail=result.get("error", "Bot verification failed"),
            headers=headers
        )
    
    return result


async def optional_bot_check(request: Request) -> dict:
    """Optional bot check - logs but doesn't block."""
    return await bot_protection.verify_request(request, required=False)


# ============================================================
# Middleware for Automatic Bot Detection
# ============================================================

class BotDetectionMiddleware:
    """Middleware to automatically detect and log bots."""
    
    def __init__(self, app):
        self.app = app
        self.manager = BotProtectionManager()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Create a minimal request-like object for analysis
        from starlette.requests import Request
        request = Request(scope, receive)
        
        # Skip for health checks, static assets, etc.
        path = request.url.path
        skip_paths = ["/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"]
        if any(path.startswith(p) for p in skip_paths):
            await self.app(scope, receive, send)
            return
        
        # Quick UA check
        ua = request.headers.get("user-agent", "")
        ua_result = UserAgentAnalyzer().analyze(ua)
        
        # Add bot info to request state for downstream use
        scope["state"] = scope.get("state", {})
        scope["state"]["bot_analysis"] = ua_result
        
        # Log suspicious requests
        if ua_result["is_suspicious"] or ua_result["is_bot"]:
            from app.core.audit import log_audit
            import asyncio
            # Fire and forget - don't block request
            asyncio.create_task(self._log_suspicious_request(request, ua_result))
        
        await self.app(scope, receive, send)
    
    async def _log_suspicious_request(self, request: Request, ua_result: dict):
        """Log suspicious request for analysis."""
        try:
            ip = request.client.host if request.client else "unknown"
            await log_audit(
                tenant_id="",  # Will be resolved by auth middleware
                actor_id=None,
                action="BOT_DETECTED",
                entity="security/bot_detection",
                diff={
                    "path": request.url.path,
                    "method": request.method,
                    "ip": ip,
                    "ua_risk_score": ua_result["risk_score"],
                    "ua_details": ua_result["details"],
                    "is_bot": ua_result["is_bot"],
                },
                ip=ip
            )
        except Exception:
            pass  # Silent fail


# ============================================================
# Challenge Page Helper (for frontend)
# ============================================================

def get_turnstile_site_key() -> str:
    """Get Turnstile site key for frontend."""
    return settings.turnstile_site_key if hasattr(settings, 'turnstile_site_key') else ""


def get_recaptcha_site_key() -> str:
    """Get reCAPTCHA site key for frontend."""
    return settings.recaptcha_site_key if hasattr(settings, 'recaptcha_site_key') else ""


# Add to config.py if not present:
# turnstile_site_key: str = ""
# recaptcha_site_key: str = ""