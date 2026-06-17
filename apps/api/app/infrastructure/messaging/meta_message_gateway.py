import httpx
from pydantic import SecretStr

from app.application.errors import MessageGatewayError
from app.domain.ports import MessageGateway

META_MESSAGES_ENDPOINT = "me/messages"


class MetaMessageGateway(MessageGateway):
    def __init__(
        self,
        *,
        page_access_token: SecretStr,
        api_version: str,
        graph_base_url: str,
        timeout_seconds: float,
    ) -> None:
        self._page_access_token = page_access_token
        self._api_version = api_version
        self._graph_base_url = graph_base_url
        self._timeout_seconds = timeout_seconds

    async def send_text(self, recipient_id: str, text: str) -> None:
        token = self._page_access_token.get_secret_value()
        if not token:
            raise MessageGatewayError("Facebook page access token is not configured")

        endpoint = META_MESSAGES_ENDPOINT
        if self._api_version:
            url = f"{self._graph_base_url}/{self._api_version}/{endpoint}"
        else:
            url = f"{self._graph_base_url}/{endpoint}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
        }

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise MessageGatewayError(
                    f"Meta API error (status {response.status_code}): {response.text}"
                ) from error
            except httpx.HTTPError as error:
                raise MessageGatewayError(f"Meta API request failed: {error}") from error
