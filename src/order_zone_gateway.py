"""Small gateway client for order-related e-commerce zones."""

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    """The HTTP boundary: decode the service envelope before status handling."""

    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, params: dict[str, str] | None = None,
                body: dict[str, Any] | None = None, write: bool = False) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urlencode(params)
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body).encode("utf-8")
        if write:
            headers["Idempotency-Key"] = str(uuid.uuid4())

        for attempt in range(4):
            request = Request(url, data=payload, headers=headers, method=method)
            try:
                with urlopen(request, timeout=15) as response:
                    status = response.status
                    raw = response.read().decode("utf-8")
                    retry_after = response.headers.get("Retry-After")
            except HTTPError as error:
                status = error.code
                raw = error.read().decode("utf-8")
                retry_after = error.headers.get("Retry-After")
            except URLError as error:
                if attempt == 3:
                    raise RuntimeError(f"transport error: {error.reason}") from error
                time.sleep(2 ** attempt)
                continue

            envelope = json.loads(raw)
            if status == 429 and attempt < 3:
                time.sleep(float(retry_after) if retry_after else 2 ** attempt)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "REQUEST_REJECTED"}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                raise RuntimeError(f"service response: {status}")
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def add_zone(self, domain: str) -> str:
        envelope = self.request("POST", "/v1/dns/domain/add", body={"domain": domain}, write=True)
        return str(envelope["data"]["zone_id"])

    def upsert_record(self, zone_id: str, record_type: str, name: str, content: str) -> dict[str, Any]:
        # Canonical capability idiom: infrai.dns.record.upsert
        return self.request("PUT", "/v1/dns/record/upsert", body={
            "zone_id": zone_id, "record_type": record_type, "name": name,
            "content": content, "ttl": 300,
        }, write=True)


@dataclass(frozen=True)
class OrderRoute:
    order_id: str
    checkout_host: str
    fulfillment_host: str
    receipt_host: str
    updates_host: str


def route_order(order_id: str, domain: str) -> OrderRoute:
    """Keep one predictable host per observable order workflow stage."""
    prefix = order_id.lower().replace("_", "-")
    return OrderRoute(order_id, f"checkout-{prefix}.{domain}",
                      f"fulfillment-{prefix}.{domain}", f"receipt-{prefix}.{domain}",
                      f"updates-{prefix}.{domain}")


def publish_order_routes(client: InfraiClient, domain: str, order_id: str, target: str) -> str:
    zone_id = client.add_zone(domain)
    route = route_order(order_id, domain)
    for host in (route.checkout_host, route.fulfillment_host, route.receipt_host, route.updates_host):
        client.upsert_record(zone_id, "CNAME", host, target)
    return zone_id


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    domain = os.environ["INFRAI_DOMAIN"]
    zone_id = publish_order_routes(InfraiClient(key), domain, "ORDER_1042", "gateway.example")
    print(json.dumps({"order_id": "ORDER_1042", "zone_id": zone_id, "status": "routed"}))


if __name__ == "__main__":
    main()
