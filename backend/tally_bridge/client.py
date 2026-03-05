"""
Core async HTTP client for TallyPrime communication.
TallyPrime runs as an HTTP server. We POST XML requests and parse responses.
CONNECTION: http://<TALLY_HOST>:<TALLY_PORT> (default: localhost:9000)
"""
import httpx
from backend.tally_bridge.exceptions import TallyConnectionError, TallyResponseError
from backend.tally_bridge.request_builder import build_list_companies


class TallyClient:
    def __init__(self, host: str = "localhost", port: int = 9000):
        self.base_url = f"http://{host}:{port}"
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def post_xml(self, xml_payload: str) -> str:
        try:
            response = await self._client.post(
                self.base_url,
                content=xml_payload,
                headers={"Content-Type": "text/xml; charset=utf-8"},
            )
            response.raise_for_status()
            return response.text
        except httpx.ConnectError:
            raise TallyConnectionError(
                f"Cannot connect to TallyPrime at {self.base_url}. "
                "Ensure Tally is running with a company loaded and port is configured."
            )
        except httpx.TimeoutException:
            raise TallyConnectionError(
                f"TallyPrime at {self.base_url} timed out. "
                "The request may be too heavy or Tally is busy."
            )
        except httpx.HTTPStatusError as e:
            raise TallyResponseError(f"Tally returned HTTP {e.response.status_code}")
        except httpx.TransportError as e:
            raise TallyConnectionError(
                f"Transport error communicating with TallyPrime at {self.base_url}: {e}"
            )

    async def close(self) -> None:
        await self._client.aclose()

    async def health_check(self) -> bool:
        try:
            result = await self.post_xml(build_list_companies())
            return "<COMPANY>" in result or "COMPANY" in result.upper()
        except (TallyConnectionError, TallyResponseError):
            return False
