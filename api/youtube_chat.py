"""
YouTube Live Chat API Client
Handles reading chat messages and posting responses
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import aiohttp

logger = logging.getLogger("youtube_chat")

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


@dataclass
class ChatMessage:
    message_id: str
    author_id: str
    author_name: str
    author_display: str
    text: str
    timestamp: float
    is_moderator: bool = False
    is_owner: bool = False
    is_member: bool = False


class YouTubeChatClient:
    def __init__(self, config):
        self.config = config
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_page_token: Optional[str] = None
        self._polling_interval_ms: int = 5000
        self._live_chat_id: Optional[str] = None

    async def start(self):
        self._session = aiohttp.ClientSession()
        await self._refresh_access_token()
        if self.config.youtube_live_chat_id:
            self._live_chat_id = self.config.youtube_live_chat_id
        else:
            self._live_chat_id = await self._get_live_chat_id()
        if not self._live_chat_id:
            raise RuntimeError("Could not find live chat ID. Is there an active livestream?")
        logger.info(f"Connected to live chat: {self._live_chat_id}")

    async def close(self):
        if self._session:
            await self._session.close()

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def _refresh_access_token(self):
        if not self.config.youtube_refresh_token:
            raise ValueError("youtube_refresh_token is required for posting messages")

        async with aiohttp.ClientSession() as s:
            resp = await s.post(GOOGLE_TOKEN_URL, data={
                "client_id": self.config.youtube_client_id,
                "client_secret": self.config.youtube_client_secret,
                "refresh_token": self.config.youtube_refresh_token,
                "grant_type": "refresh_token",
            })
            data = await resp.json()

        if "error" in data:
            raise RuntimeError(f"Token refresh failed: {data}")

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 3600) - 60
        logger.info("Access token refreshed")

    async def _ensure_token(self):
        if time.time() > self._token_expires_at:
            await self._refresh_access_token()

    # ── Live Chat Discovery ───────────────────────────────────────────────────

    async def _get_live_chat_id(self) -> Optional[str]:
        """Find the active livestream's chat ID."""
        await self._ensure_token()
        url = f"{YOUTUBE_API_BASE}/liveBroadcasts"
        params = {
            "part": "snippet",
            "broadcastStatus": "active",
            "key": self.config.youtube_api_key,
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async with self._session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()

        items = data.get("items", [])
        if not items:
            # Try mine=true
            params["mine"] = "true"
            del params["key"]
            async with self._session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
            items = data.get("items", [])

        if items:
            chat_id = items[0]["snippet"]["liveChatId"]
            logger.info(f"Found live chat ID: {chat_id}")
            return chat_id
        return None

    # ── Reading Messages ──────────────────────────────────────────────────────

    async def poll_messages(self) -> list[ChatMessage]:
        """Poll for new messages. Returns list of new ChatMessage objects."""
        await self._ensure_token()
        url = "https://youtube.googleapis.com/youtube/v3/liveChat/messages?part=snippet"
        params = {
            "liveChatId": self._live_chat_id,
            "part": "snippet,authorDetails",
            "maxResults": 200,
        }
        if self._last_page_token:
            params["pageToken"] = self._last_page_token

        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            async with self._session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 403:
                    logger.error("403 Forbidden - quota exceeded or bad key. Backing off 60s.")
                    self._polling_interval_ms = 60000
                    return []
                if resp.status != 200:
                    logger.warning(f"Chat poll returned {resp.status}. Backing off 15s.")
                    self._polling_interval_ms = 15000
                    return []
                data = await resp.json()
        except Exception as e:
            logger.error(f"Poll error: {e}")
            return []

        self._last_page_token = data.get("nextPageToken")
        # Never poll faster than 10s — protects daily quota
        self._polling_interval_ms = max(10000, data.get("pollingIntervalMillis", 10000))

        messages = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            author = item.get("authorDetails", {})

            if snippet.get("type") != "textMessageEvent":
                continue

            msg = ChatMessage(
                message_id=item["id"],
                author_id=author.get("channelId", ""),
                author_name=author.get("channelUrl", ""),
                author_display=author.get("displayName", "unknown"),
                text=snippet.get("displayMessage", ""),
                timestamp=time.time(),
                is_moderator=author.get("isChatModerator", False),
                is_owner=author.get("isChatOwner", False),
                is_member=author.get("isChatSponsor", False),
            )
            messages.append(msg)

        return messages

    async def message_stream(self) -> AsyncIterator[ChatMessage]:
        """Async generator that yields messages as they arrive."""
        seen_ids = set()
        while True:
            messages = await self.poll_messages()
            for msg in messages:
                if msg.message_id not in seen_ids:
                    seen_ids.add(msg.message_id)
                    yield msg

            # Keep seen_ids from growing unbounded
            if len(seen_ids) > 10000:
                seen_ids = set(list(seen_ids)[-5000:])

            await asyncio.sleep(self._polling_interval_ms / 1000)

    # ── Sending Messages ──────────────────────────────────────────────────────

    async def send_message(self, text: str) -> bool:
        """Post a message to live chat."""
        if not text:
            return False
        # Truncate to YouTube's limit
        text = text[:200]

        await self._ensure_token()
        url = f"{YOUTUBE_API_BASE}/liveChat/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        body = {
            "snippet": {
                "liveChatId": self._live_chat_id,
                "type": "textMessageEvent",
                "textMessageDetails": {"messageText": text},
            }
        }

        try:
            async with self._session.post(url, json=body, headers=headers,
                                          timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (200, 201):
                    logger.debug(f"Sent message: {text}")
                    return True
                err = await resp.text()
                logger.warning(f"Send message failed {resp.status}: {err[:200]}")
                return False
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return False