# PayCore integration notes

Base URL comes from `PAYMENTS_BASE_URL`; authenticate with `Authorization: Bearer <PAYMENTS_API_KEY>`.

## POST /v1/refunds

Request:

```json
{ "payment_ref": "pi_3QxL2a", "amount": "12.50", "currency": "GBP" }
```

### 200 OK

```json
{ "id": "rf_9KdQ1m", "status": "succeeded", "amount": "12.50", "currency": "GBP" }
```

### 402 Payment Required (declined)

```json
{
  "id": "rf_9KdQ2x",
  "status": "declined",
  "decline_code": "expired_card",
  "message": "Refund to Visa ending 4242 declined: card expired 03/24. Billing: 14 Larch Rd, Leeds LS6 2AB.",
  "card": {
    "brand": "visa",
    "card_last4": "4242",
    "card_fingerprint": "fp_7Hc2LqPz",
    "billing_address": { "line1": "14 Larch Rd", "city": "Leeds", "postcode": "LS6 2AB" }
  }
}
```

`decline_code` values seen so far: `expired_card`, `charge_disputed`, `insufficient_merchant_balance`, `refund_window_closed`, `card_closed`.

### 4xx/5xx (other)

```json
{ "error": { "type": "invalid_request", "message": "payment_ref not found" } }
```
