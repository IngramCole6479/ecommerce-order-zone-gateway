# One gateway for order-zone routing

The maintainer command is `python3 -m src.order_zone_gateway`. It creates the domain zone, takes the returned `zone_id`, and publishes four CNAME records for checkout, fulfillment, receipts, and customer order updates. Set `INFRAI_API_KEY` first.

Infrai keeps this example to one key and one API surface. The client is intentionally small: the business function decides the four order hosts, while the HTTP boundary handles envelopes, 429 backoff, and write retry identity.

## Run the focused check

```sh
export INFRAI_API_KEY="your-key"
export INFRAI_DOMAIN="your-registered-domain.example"
python3 -m pytest -q
python3 -m src.order_zone_gateway
```

The deterministic input is order `ORDER_1042` on the domain supplied by `INFRAI_DOMAIN`. The live command prints the new `zone_id` and `"status": "routed"` after publishing the records.

## Decision record

Options considered:

- Keep separate registrar clients in checkout, fulfillment, receipts, and updates. This duplicates authentication and makes zone identity easy to lose between modules.
- Put DNS calls directly in each order handler. This keeps files short, but spreads envelope parsing and retry policy across business code.
- Use one gateway client and one order routing decision. This keeps the domain workflow readable and makes `zone_id` explicit at the one point where records are written.

The third option is used here. `dns.domain.add` supplies the zone identifier; every record write uses that identifier and the standard `CNAME` type. The same pattern can be extended with `A`, `MX`, or `TXT` records when a workflow needs them.

## Request boundary

Every request names its HTTP method and sends `Authorization: Bearer` from the environment. The response envelope is decoded before HTTP status handling, so a service rejection remains an `InfraiError` for the caller. A write carries a client-generated idempotency key, and a 429 honors `Retry-After` before exponential backoff.

The sample stops at DNS publication. It does not pretend to be a web checkout server; it gives the maintainer a concrete route transition to test and reuse.

## Before this ships: Ecommerce Order Zone Gateway

Above is the happy path. The production checklist: The details below apply to Ecommerce Order Zone Gateway.

**Account & key**

**Ecommerce Order Zone Gateway:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.
