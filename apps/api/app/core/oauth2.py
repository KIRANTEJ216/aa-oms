"""
OAuth2/OIDC Integration:
- External identity provider support (Google, Microsoft, GitHub, custom OIDC)
- Authorization code flow with PKCE
- Token exchange and user info retrieval
- Account linking and provisioning
- JWKS validation for ID tokens
"""
from fastapi import HTTPException, Request, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from pydantic import BaseModel
import secrets
import hashlib
import base64
import httpx
import jwt
from jwt import PyJWKClient
from app.infra.firestore.client import get_db
from app.core.auth import get_current_user
from app.core.tenant import get_current_tenant
from app.core.audit import log_audit
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token
from app.core.auth_strong import SessionManager


# ============================================================
# Provider Configuration
# ============================================================

@dataclass
class OAuth2Provider:
    """OAuth2/OIDC provider configuration."""
    id: str
    name: str
    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    scopes: List[str]
    pkce_required: bool = True
    issuer: str = None
    
    # Field mappings
    user_id_field: str = "sub"
    email_field: str = "email"
    name_field: str = "name"
    picture_field: str = "picture"


# Built-in provider configurations
BUILTIN_PROVIDERS = {
    "google": OAuth2Provider(
        id="google",
        name="Google",
        client_id="",
        client_secret="",
        authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        userinfo_endpoint="https://www.googleapis.com/oauth2/v3/userinfo",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        scopes=["openid", "email", "profile"],
        pkce_required=True,
        issuer="https://accounts.google.com",
    ),
    "microsoft": OAuth2Provider(
        id="microsoft",
        name="Microsoft",
        client_id="",
        client_secret="",
        authorization_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_endpoint="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        userinfo_endpoint="https://graph.microsoft.com/oidc/userinfo",
        jwks_uri="https://login.microsoftonline.com/common/discovery/v2.0/keys",
        scopes=["openid", "email", "profile", "User.Read"],
        pkce_required=True,
        issuer="https://login.microsoftonline.com/common/v2.0",
    ),
    "github": OAuth2Provider(
        id="github",
        name="GitHub",
        client_id="",
        client_secret="",
        authorization_endpoint="https://github.com/login/oauth/authorize",
        token_endpoint="https://github.com/login/oauth/access_token",
        userinfo_endpoint="https://api.github.com/user",
        jwks_uri="",  # GitHub doesn't use OIDC
        scopes=["read:user", "user:email"],
        pkce_required=True,
        issuer=None,
    ),
}


# ============================================================
# PKCE Helpers
# ============================================================

def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    return code_verifier, code_challenge


def verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    """Verify PKCE code verifier against challenge."""
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    return secrets.compare_digest(expected, code_challenge)


# ============================================================
# OAuth2 Manager
# ============================================================

class OAuth2Manager:
    """Manages OAuth2/OIDC flows for multiple providers."""
    
    def __init__(self):
        self.providers: Dict[str, OAuth2Provider] = {}
        self._load_providers()
        self._jwks_clients: Dict[str, PyJWKClient] = {}
    
    def _load_providers(self):
        """Load provider configurations from settings."""
        settings = get_settings()
        
        # Load built-in providers
        for provider_id, provider in BUILTIN_PROVIDERS.items():
            client_id = getattr(settings, f"oauth_{provider_id}_client_id", "")
            client_secret = getattr(settings, f"oauth_{provider_id}_client_secret", "")
            
            if client_id and client_secret:
                provider.client_id = client_id
                provider.client_secret = client_secret
                self.providers[provider_id] = provider
        
        # Load custom providers from settings
        custom_providers = getattr(settings, "oauth_custom_providers", {})
        for provider_id, config in custom_providers.items():
            if isinstance(config, dict) and config.get("client_id") and config.get("client_secret"):
                self.providers[provider_id] = OAuth2Provider(
                    id=provider_id,
                    name=config.get("name", provider_id),
                    client_id=config["client_id"],
                    client_secret=config["client_secret"],
                    authorization_endpoint=config["authorization_endpoint"],
                    token_endpoint=config["token_endpoint"],
                    userinfo_endpoint=config.get("userinfo_endpoint", ""),
                    jwks_uri=config.get("jwks_uri", ""),
                    scopes=config.get("scopes", ["openid", "email", "profile"]),
                    pkce_required=config.get("pkce_required", True),
                    issuer=config.get("issuer"),
                )
    
    def get_provider(self, provider_id: str) -> Optional[OAuth2Provider]:
        """Get provider by ID."""
        return self.providers.get(provider_id)
    
    def list_providers(self) -> List[Dict[str, Any]]:
        """List available providers for UI."""
        return [
            {
                "id": p.id,
                "name": p.name,
                "scopes": p.scopes,
            }
            for p in self.providers.values()
        ]
    
    def _get_jwks_client(self, provider: OAuth2Provider) -> PyJWKClient:
        """Get or create JWKS client for provider."""
        if provider.id not in self._jwks_clients:
            if provider.jwks_uri:
                self._jwks_clients[provider.id] = PyJWKClient(provider.jwks_uri)
        return self._jwks_clients.get(provider.id)
    
    # ============================================================
    # Authorization Code Flow
    # ============================================================
    
    def get_authorization_url(
        self,
        provider_id: str,
        redirect_uri: str,
        state: str = None,
        nonce: str = None,
        code_challenge: str = None,
        code_challenge_method: str = "S256"
    ) -> Dict[str, Any]:
        """Generate authorization URL for provider."""
        provider = self.get_provider(provider_id)
        if not provider:
            raise HTTPException(404, f"Provider not found: {provider_id}")
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(provider.scopes),
            "state": state,
        }
        
        if provider.pkce_required and code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method
        
        if nonce:
            params["nonce"] = nonce
        
        # Build URL
        auth_url = provider.authorization_endpoint + "?" + "&".join(
            f"{k}={httpx.URL.encode_component(v)}" for k, v in params.items()
        )
        
        return {
            "authorization_url": auth_url,
            "state": state,
            "provider": provider_id,
        }
    
    async def exchange_code_for_tokens(
        self,
        provider_id: str,
        code: str,
        redirect_uri: str,
        code_verifier: str = None
    ) -> Dict[str, Any]:
        """Exchange authorization code for access/ID tokens."""
        provider = self.get_provider(provider_id)
        if not provider:
            raise HTTPException(404, f"Provider not found: {provider_id}")
        
        data = {
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        
        if code_verifier:
            data["code_verifier"] = code_verifier
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Accept": "application/json"}
            resp = await client.post(provider.token_endpoint, data=data, headers=headers)
            
            if resp.status_code != 200:
                error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"error": resp.text}
                raise HTTPException(400, f"Token exchange failed: {error_data}")
            
            return resp.json()
    
    async def get_userinfo(
        self,
        provider_id: str,
        access_token: str
    ) -> Dict[str, Any]:
        """Get user info from provider."""
        provider = self.get_provider(provider_id)
        if not provider:
            raise HTTPException(404, f"Provider not found: {provider_id}")
        
        if not provider.userinfo_endpoint:
            # For providers without userinfo endpoint (like GitHub), get from ID token
            raise HTTPException(501, "Userinfo endpoint not configured for this provider")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            resp = await client.get(provider.userinfo_endpoint, headers=headers)
            
            if resp.status_code != 200:
                raise HTTPException(400, f"Userinfo request failed: {resp.text}")
            
            return resp.json()
    
    # ============================================================
    # ID Token Validation
    # ============================================================
    
    async def validate_id_token(
        self,
        provider_id: str,
        id_token: str,
        nonce: str = None,
        client_id: str = None
    ) -> Dict[str, Any]:
        """Validate OIDC ID token."""
        provider = self.get_provider(provider_id)
        if not provider:
            raise HTTPException(404, f"Provider not found: {provider_id}")
        
        if not provider.jwks_uri:
            raise HTTPException(501, "Provider does not support ID token validation (no JWKS)")
        
        jwks_client = self._get_jwks_client(provider)
        if not jwks_client:
            raise HTTPException(500, "JWKS client not available")
        
        try:
            # Get signing key
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)
            
            # Decode and validate
            payload = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=client_id or provider.client_id,
                issuer=provider.issuer,
                options={"verify_exp": True, "verify_iat": True}
            )
            
            # Verify nonce if provided
            if nonce and payload.get("nonce") != nonce:
                raise HTTPException(400, "Nonce mismatch")
            
            return payload
        
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "ID token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(401, f"Invalid ID token: {e}")
    
    # ============================================================
    # Account Linking / Provisioning
    # ============================================================
    
    async def find_or_create_user(
        self,
        provider_id: str,
        userinfo: Dict[str, Any],
        tenant_id: str,
        id_token: str = None
    ) -> Dict[str, Any]:
        """Find existing user or create new one from OAuth2 userinfo."""
        db = get_db()
        provider = self.get_provider(provider_id)
        
        # Extract user identifiers
        provider_user_id = userinfo.get(provider.user_id_field)
        email = userinfo.get(provider.email_field, "").lower()
        name = userinfo.get(provider.name_field, "")
        picture = userinfo.get(provider.picture_field, "")
        
        if not provider_user_id:
            raise HTTPException(400, "Provider user ID not found in userinfo")
        
        # Check for existing linked account
        linked_query = db.collection("userIdentities").where(
            "provider_id", "==", provider_id
        ).where("provider_user_id", "==", provider_user_id).limit(1)
        
        linked_docs = list(linked_query.stream())
        if linked_docs:
            # Existing linked account
            linked_data = linked_docs[0].to_dict()
            user_id = linked_data["user_id"]
            
            # Verify tenant
            user_doc = db.collection("users").document(user_id).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                if user_data.get("tenant_id") == tenant_id:
                    # Update last login
                    db.collection("users").document(user_id).update({
                        "lastLoginAt": datetime.now(timezone.utc),
                        "picture": picture,
                    })
                    
                    await log_audit(
                        tenant_id=tenant_id,
                        actor_id=user_id,
                        action="OAUTH_LOGIN",
                        entity="auth/oauth",
                        entity_id=user_id,
                        diff={"provider": provider_id}
                    )
                    
                    return {
                        "user_id": user_id,
                        "user_data": user_data,
                        "linked": True,
                    }
        
        # Check for existing user by email (for account linking)
        if email:
            existing_users = list(db.collection("users")
                                .where("tenant_id", "==", tenant_id)
                                .where("email", "==", email)
                                .limit(1)
                                .stream())
            
            if existing_users:
                # Link to existing account
                user_id = existing_users[0].id
                
                # Create identity link
                identity_id = secrets.token_urlsafe(16)
                db.collection("userIdentities").document(identity_id).set({
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "provider_id": provider_id,
                    "provider_user_id": provider_user_id,
                    "email": email,
                    "created_at": datetime.now(timezone.utc),
                    "last_used_at": datetime.now(timezone.utc),
                })
                
                await log_audit(
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action="OAUTH_LINK",
                    entity="userIdentities",
                    entity_id=identity_id,
                    diff={"provider": provider_id}
                )
                
                return {
                    "user_id": user_id,
                    "user_data": existing_users[0].to_dict(),
                    "linked": True,
                    "new_link": True,
                }
        
        # Auto-provision new user if enabled
        settings = get_settings()
        if not getattr(settings, "oauth_auto_provision", True):
            raise HTTPException(401, "No local account matches this identity. Contact admin.")
        
        # Create new user
        user_id = secrets.token_urlsafe(16)
        user_doc = {
            "tenant_id": tenant_id,
            "name": name or email.split("@")[0],
            "email": email,
            "password_hash": "",  # No password for OAuth users
            "role": "Client",
            "mobile": "",
            "mfaEnabled": False,
            "mfaSecretEnc": None,
            "isActive": True,
            "emailVerified": True,
            "picture": picture,
            "authProvider": provider_id,
            "createdAt": datetime.now(timezone.utc),
            "lastLoginAt": None,
        }
        
        db.collection("users").document(user_id).set(user_doc)
        
        # Create identity link
        identity_id = secrets.token_urlsafe(16)
        db.collection("userIdentities").document(identity_id).set({
            "user_id": user_id,
            "tenant_id": tenant_id,
            "provider_id": provider_id,
            "provider_user_id": provider_user_id,
            "email": email,
            "created_at": datetime.now(timezone.utc),
            "last_used_at": datetime.now(timezone.utc),
        })
        
        await log_audit(
            tenant_id=tenant_id,
            actor_id=user_id,
            action="CREATE",
            entity="users",
            entity_id=user_id,
            diff={"provider": provider_id, "auto_provisioned": True}
        )
        
        return {
            "user_id": user_id,
            "user_data": user_doc,
            "linked": False,
            "new_user": True,
        }


# Global OAuth2 manager instance
oauth2_manager = OAuth2Manager()


# ============================================================
# FastAPI Dependencies
# ============================================================

async def get_oauth2_manager() -> OAuth2Manager:
    return oauth2_manager


# ============================================================
# Pydantic Models
# ============================================================

class OAuth2AuthorizeRequest(BaseModel):
    provider: str
    redirect_uri: str
    state: Optional[str] = None
    nonce: Optional[str] = None


class OAuth2CallbackRequest(BaseModel):
    provider: str
    code: str
    redirect_uri: str
    state: str
    code_verifier: Optional[str] = None


class OAuth2LinkRequest(BaseModel):
    provider: str
    access_token: str