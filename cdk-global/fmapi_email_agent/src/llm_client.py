"""LLM client with three-tier fallback across serving endpoints.

Fallback chain:
  Tier 1+2: fmapi-email-agent-llama-fmapi-gateway (AI Gateway endpoint,
            Maverick → 70B fallback handled server-side)
  Tier 3:   <target>-llama-4-maverick-pt           (provisioned throughput,
            deployed by DAB)

Tier 1+2 hits the AI Gateway URL. Tier 3 hits the workspace serving URL.
The app-layer client cascades between them on retriable errors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from databricks.sdk import WorkspaceClient
from openai import APIError, APITimeoutError, OpenAI

logger = logging.getLogger(__name__)

RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}

AI_GATEWAY_BASE_URL = "https://7474644652812129.ai-gateway.cloud.databricks.com/mlflow/v1"


@dataclass
class EndpointConfig:
    """Configuration for a single model serving endpoint."""

    name: str
    model: str
    client: OpenAI
    timeout: float = 60.0


@dataclass
class FallbackLLMClient:
    """LLM client that cascades requests across multiple serving endpoints.

    Tries each endpoint in order. Retriable errors (429, 5xx) and timeouts
    trigger fallback to the next endpoint. Non-retriable errors (400, 401,
    403) are raised immediately.

    Args:
        endpoints: Ordered list of endpoint configs to try.
    """

    endpoints: list[EndpointConfig]

    def __post_init__(self) -> None:
        if not self.endpoints:
            raise ValueError("At least one endpoint must be configured")

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """Send a chat completion request with endpoint fallback.

        Args:
            messages: Chat messages in OpenAI format.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional parameters forwarded to the API.

        Returns:
            OpenAI ChatCompletion response from the first successful endpoint.

        Raises:
            APIError: If all endpoints fail.
        """
        last_error: Exception | None = None

        for i, endpoint in enumerate(self.endpoints):
            try:
                logger.info(f"Attempting endpoint {endpoint.name} ({i + 1}/{len(self.endpoints)})")

                response = endpoint.client.chat.completions.create(
                    model=endpoint.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=endpoint.timeout,
                    **kwargs,
                )

                logger.info(f"Success on endpoint {endpoint.name}")
                return response

            except APITimeoutError as e:
                logger.warning(f"Timeout on endpoint {endpoint.name}: {e}")
                last_error = e

            except APIError as e:
                if e.status_code in RETRIABLE_STATUS_CODES:
                    logger.warning(
                        f"Retriable error {e.status_code} on endpoint {endpoint.name}: {e.message}"
                    )
                    last_error = e
                else:
                    raise

        raise last_error or RuntimeError("All endpoints failed with no captured error")


def create_default_client(
    target: str = "dev",
    profile: str = "group-demo",
) -> FallbackLLMClient:
    """Create a FallbackLLMClient with the standard three-tier config.

    Tier 1+2: AI Gateway endpoint (Maverick with 70B fallback server-side)
    Tier 3:   DAB-deployed provisioned throughput Llama 4 Maverick

    Args:
        target: DAB target name used in the PT endpoint name (e.g. "dev", "prod").
        profile: Databricks CLI profile for authentication.

    Returns:
        Configured FallbackLLMClient.
    """
    w = WorkspaceClient(profile=profile)
    headers = w.config.authenticate()
    token = headers.get("Authorization", "").removeprefix("Bearer ")

    gateway_client = OpenAI(
        api_key=token,
        base_url=AI_GATEWAY_BASE_URL,
    )

    workspace_client = w.serving_endpoints.get_open_ai_client()

    endpoints = [
        EndpointConfig(
            name="ai-gateway-fmapi",
            model="fmapi-email-agent-llama-fmapi-gateway",
            client=gateway_client,
        ),
        EndpointConfig(
            name="pt-maverick",
            model=f"{target}-llama-4-maverick-pt",
            client=workspace_client,
            timeout=120.0,
        ),
    ]

    return FallbackLLMClient(endpoints=endpoints)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

    client = create_default_client()
    response = client.chat(
        messages=[{"role": "user", "content": "What is Databricks?"}],
        max_tokens=256,
    )
    print(response.choices[0].message.content)
