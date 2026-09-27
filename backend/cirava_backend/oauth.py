from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import secrets
import socket
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable


AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def oauth_completion_page() -> bytes:
    """Return the loopback callback page with a browser-safe close fallback."""
    return b'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Cirava sign-in</title>
<style>body{font:16px system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0;color:#263249;background:#f5f8ff}main{text-align:center;padding:32px;max-width:440px}p{line-height:1.55;color:#586783}button{margin-top:16px;padding:10px 16px;border:0;border-radius:9px;color:white;background:#617dea;cursor:pointer}</style>
</head><body><main><strong>Google sign-in returned to Cirava.</strong><p id="completion-message" aria-live="polite">Return to Cirava. This tab will try to close; if it stays open, close it here.</p><button type="button" onclick="window.close()">Close tab</button></main>
<script>
window.setTimeout(function(){window.close();},350);
window.setTimeout(function(){
  var message=document.getElementById('completion-message');
  if(message) message.textContent='Return to Cirava to finish sign-in. If this tab is still open, close it here.';
},1200);
</script></body></html>'''


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    client_secret: str = ""
    redirect_host: str = "127.0.0.1"
    # Port 0 asks the OS flow below to choose a free five-digit loopback port.
    # This avoids conflicts with other local apps while keeping the callback
    # valid for Google's installed-app OAuth flow.
    redirect_port: int = 0
    scope: str = DRIVE_SCOPE


class OAuthSession:
    def __init__(self, config: OAuthConfig, opener: Callable[[str], object] = webbrowser.open_new_tab):
        self.config = config
        self._opener = opener
        self._verifier = secrets.token_urlsafe(64)
        self._state = secrets.token_urlsafe(32)
        self.redirect_port = config.redirect_port

    @property
    def redirect_uri(self) -> str:
        return f"http://{self.config.redirect_host}:{self.redirect_port}/oauth/callback"

    def authorization_url(self) -> str:
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self._verifier.encode()).digest()).rstrip(b"=").decode()
        query = urllib.parse.urlencode({
            "client_id": self.config.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.config.scope,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": self._state,
        })
        return f"{AUTH_ENDPOINT}?{query}"

    def login(self) -> dict:
        callback: dict[str, str] = {}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/oauth/callback":
                    self.send_error(404)
                    return
                callback.update({key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items() if values})
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                # System-browser tabs may not be script-closable. Attempt it,
                # but provide a truthful instruction if the browser blocks it.
                self.wfile.write(oauth_completion_page())

            def log_message(self, *_args):
                return

        server = None
        if self.config.redirect_port:
            server = HTTPServer((self.config.redirect_host, self.config.redirect_port), CallbackHandler)
        else:
            # Bind before opening Google so the chosen port cannot be claimed
            # by another local process between URL creation and the callback.
            for _ in range(40):
                candidate = secrets.randbelow(55536) + 10000
                try:
                    server = HTTPServer((self.config.redirect_host, candidate), CallbackHandler)
                    break
                except OSError:
                    continue
            if server is None:
                raise OSError("Could not reserve a free five-digit OAuth callback port")
        self.redirect_port = server.server_address[1]
        authorization_url = self.authorization_url()
        # The production desktop path continues to use the system browser. The
        # opt-in E2E harness can hand the non-secret authorization URL to an
        # already-authenticated browser session without exposing credentials.
        url_file = os.environ.get("CIRAVA_OAUTH_URL_FILE", "")
        if url_file:
            Path(url_file).write_text(authorization_url, encoding="utf-8")
            opened = True
        else:
            opened = self._opener(authorization_url)
        if opened is False:
            server.server_close()
            raise RuntimeError("Could not open the system browser")
        server.timeout = 1
        for _ in range(300):
            server.handle_request()
            if callback:
                break
        server.server_close()
        if callback.get("state") != self._state:
            raise RuntimeError("OAuth state validation failed")
        if "error" in callback:
            raise RuntimeError(f"Google authorization failed: {callback['error']}")
        if not callback.get("code"):
            raise TimeoutError("Google authorization timed out")
        return self.exchange_code(callback["code"])

    def exchange_code(self, code: str) -> dict:
        body = urllib.parse.urlencode({
            "client_id": self.config.client_id,
            "code": code,
            "code_verifier": self._verifier,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }).encode()
        if self.config.client_secret:
            body = urllib.parse.urlencode({
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "code": code,
                "code_verifier": self._verifier,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            }).encode()
        request = urllib.request.Request(TOKEN_ENDPOINT, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            raw = error.read().decode(errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {}
            reason = payload.get("error") or error.reason
            description = payload.get("error_description")
            detail = f": {description}" if description else ""
            raise RuntimeError(f"Google OAuth token exchange failed ({reason}){detail}. Check that the full Desktop OAuth client ID is correct and that the browser callback completed for the same attempt.") from error


class TokenStore:
    """Small encrypted credential store for the current Windows user.

    On Windows the payload is protected with DPAPI, so the token and client
    secret can only be decrypted by the same Windows user on this machine.
    The file itself is kept under %APPDATA%\\Cirava by the desktop backend.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, tokens: dict) -> None:
        raw = json.dumps(tokens, separators=(",", ":")).encode()
        protected = _protect(raw)
        temporary = self.path.with_name(f".{self.path.name}.{secrets.token_hex(8)}.tmp")
        try:
            temporary.write_bytes(protected)
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            temporary.replace(self.path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(_unprotect(self.path.read_bytes()).decode())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            # A token cache can outlive the Windows user/profile that created it.
            # Treat it as signed out so the normal OAuth flow can replace it.
            return None

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


class TokenManager:
    """Keeps access tokens fresh without exposing refresh credentials to the UI."""

    def __init__(self, store: TokenStore, client_id: str = "", client_secret: str = "", refresh_request: Callable[[str], dict] | None = None):
        self.store = store
        self.client_id = client_id
        self.client_secret = client_secret
        self._refresh_request = refresh_request or self._refresh_over_http
        self._lock = threading.Lock()

    def access_token(self) -> str:
        with self._lock:
            tokens = self.store.load()
            if not tokens or not tokens.get("access_token"):
                raise RuntimeError("Google account is not connected")
            if float(tokens.get("expires_at", 0)) > time.time() + 60:
                return tokens["access_token"]
            refresh_token = tokens.get("refresh_token")
            if not refresh_token:
                raise RuntimeError("Google session expired; sign in again")
            refreshed = self._refresh_request(refresh_token)
            tokens.update(refreshed)
            tokens["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
            self.store.save(tokens)
            return tokens["access_token"]

    def _refresh_over_http(self, refresh_token: str) -> dict:
        values = {"client_id": self.client_id, "refresh_token": refresh_token, "grant_type": "refresh_token"}
        if self.client_secret:
            values["client_secret"] = self.client_secret
        body = urllib.parse.urlencode(values).encode()
        request = urllib.request.Request(TOKEN_ENDPOINT, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())


def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    input_blob = Blob(len(data), source)
    output_blob = Blob()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)):
        raise OSError("Windows credential protection failed")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    source = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    input_blob = Blob(len(data), source)
    output_blob = Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)):
        raise OSError("Windows credential unprotection failed")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)
