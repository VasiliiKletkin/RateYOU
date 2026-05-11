# Context Map

This document shows how the six bounded contexts relate. Relationships use
DDD strategic-design vocabulary (upstream/downstream, partnership, customer/
supplier, shared kernel, anti-corruption layer).

```
                     ┌──────────────────┐
                     │     Identity     │  (upstream of everyone)
                     │   - User         │
                     │   - UserId       │
                     └──────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
      ┌─────────┐       ┌─────────┐       ┌──────────────┐
      │ Profile │       │ Payment │       │ Subscription │
      │ - Profile│      │ - Transaction│   │ - Subscription│
      │ - Photo  │      │ - Money     │   │ - Tier        │
      └─────────┘       └─────────┘       └──────────────┘
            │                 │                 ▲
            │                 └─────partnership ┘
            │                  (PaymentConfirmed →
            ▼                   SubscriptionActivated)
      ┌──────────┐
      │  Rating  │
      │ - Rating │
      │ - Summary│  (read model)
      └──────────┘
            │
            ▼
      ┌─────────────────────────────────────┐
      │            Discovery                │
      │ (orchestrates Profile + Rating +    │
      │  Subscription + Skip registry)      │
      └─────────────────────────────────────┘
```

## Relationships

| From → To | Type | What flows |
|---|---|---|
| Profile → Identity | downstream (uses `UserId`) | `Profile.owner_id` references a User |
| Rating → Identity | downstream (uses `UserId`) | `Rating.rater_id`, `Rating.rated_id` |
| Subscription → Identity | downstream (uses `UserId`) | `Subscription.owner_id` |
| Payment → Identity | downstream (uses `UserId`) | `Transaction.payer_id` |
| Discovery → Profile, Rating, Subscription | downstream consumer | reads profiles, ratings, subscription tier; never writes |
| Rating → Profile | weak — only via `owner_id` | summary is keyed on rated user, not on profile |
| Payment ↔ Subscription | **partnership** | `ConfirmPaymentUseCase` activates a subscription; `RefundPaymentUseCase` revokes it. Two contexts coordinated by an application-layer flow. |

## Shared Kernel

`src/domain/shared/`:
- `uow.py` — `UnitOfWork` protocol (used by every context's use cases)
- `identifiers.py` — `UserId` (referenced by Profile / Rating / Subscription / Payment / Discovery)

These are the **only** things several contexts may share. Anything else lives
in its owning context.

## Anti-Corruption Layer for Telegram

The Telegram Bot API leaks two concepts that don't belong in the Payment
domain:

- The currency code `"XTR"` (Telegram Stars are not RUB/USD)
- `telegram_payment_charge_id` as the refund handle

These are translated at the **infrastructure boundary** in
`src/infrastructure/payment/telegram_stars.py` (`TelegramStarsGateway`).
The bot handler that receives `successful_payment` builds a clean
`ConfirmPaymentRequest` — no aiogram types reach the application layer.

The refund flow needs the user's Telegram ID, which is owned by Identity, not
Payment. `RefundPaymentUseCase` therefore takes `IUserRepository` to resolve
`payer_id → User.telegram_id` rather than denormalizing `telegram_id` onto
`Transaction`.

## Where events flow

Cross-context coordination happens through domain events published by
aggregates and dispatched by `IEventBus`. Examples:

| Source context | Event | Handlers in | Effect |
|---|---|---|---|
| Rating | `RatingGiven` | Rating (projection) | Recomputes `ProfileScoreSummary` |
| Payment | `PaymentConfirmed` | Subscription | Activates / renews tier |
| Payment | `PaymentRefunded` | Subscription | Revokes premium |
| Identity | `UserBanned` (future) | Profile | Hides their profile |

Events are dispatched in-process after `uow.commit()` succeeds. There is no
outbox yet — when reliable cross-process delivery is needed (e.g. external
notification webhooks), add an outbox table + worker.
