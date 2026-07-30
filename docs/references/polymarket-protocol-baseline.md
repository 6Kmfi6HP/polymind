# Polymarket Protocol, SDK, Identity, and Recovery Baseline

**Status:** Current first-party research baseline  
**Checked:** 2026-07-30  
**Scope:** Polymarket prediction-market CLOB V2; not Polymarket Perps or Combos

## Decision summary

Polymind's future Polymarket adapter must target the production CLOB V2
contract and wire model through the official unified Python SDK,
[`polymarket-client`](https://docs.polymarket.com/getting-started/python), behind
project-owned ports. It must not treat a display outcome such as `"Yes"`, a
Gamma market ID, a condition ID, and an outcome token ID as interchangeable.

The adapter must expose four separately scoped identifiers:

- event/market metadata identity for discovery;
- CTF condition ID for the binary condition and market-scoped operations;
- outcome token ID (CLOB `asset_id`) for order books, orders, balances, and
  outcome-scoped cancellation;
- CLOB order ID and trade ID for OMS lifecycle reconciliation.

The live recovery contract is snapshot-plus-stream: authenticated WebSocket
events are low-latency notifications, but after every reconnect the OMS must
refresh all paginated open orders and recent account trades before resuming.
Final asset ownership is reconciled against Polygon pUSD/ERC-20 and outcome
token/ERC-1155 balances; CLOB reads remain authoritative for offchain resting
orders and the CLOB settlement state machine. No official, funded public
sandbox is documented, so live promotion must use recorded/mock protocol tests
plus explicitly gated, small funded-wallet conformance on production.

## Authoritative facts

### 1. Identity and market structure

- A Polymarket **event** groups one or more **markets**. A market is a binary
  question with a CTF **condition ID**, a resolution **question ID**, and two
  CLOB **token IDs**, one per outcome. A market can exist onchain without being
  CLOB-tradable; `enableOrderBook` must be true. The event/market slug is a
  discovery identifier, not an execution identifier. See
  [Markets & Events](https://docs.polymarket.com/concepts/markets-events).
- Outcome tokens are ERC-1155 assets on Polygon. A complete Yes/No pair is
  backed by one pUSD; split creates both tokens, merge consumes an equal pair,
  and redemption consumes the winning token after resolution. See
  [Positions & Tokens](https://docs.polymarket.com/concepts/positions-tokens).
- The CLOB market-info endpoint is keyed by condition ID and returns outcome
  token IDs/outcome labels plus venue parameters such as minimum tick size,
  minimum order size, fee details, and RFQ status. Conversely, the market-by-token
  endpoint resolves a token ID back to its parent condition. See
  [Get CLOB market info](https://docs.polymarket.com/api-reference/markets/get-clob-market-info)
  and
  [Get market by token](https://docs.polymarket.com/api-reference/markets/get-market-by-token).
- Public market WebSocket subscriptions use outcome token IDs (`assets_ids`).
  User WebSocket filters use condition IDs (`markets`). Events carry both
  `market` (condition ID) and `asset_id` (outcome token ID). See the
  [Market Channel](https://docs.polymarket.com/api-reference/wss/market) and
  [User Channel](https://docs.polymarket.com/api-reference/wss/user).

**Adapter constraint:** `EventId`, `MarketId`, `ConditionId`, `TokenId`,
`OrderId`, and `TradeId` must be distinct domain types. An outcome label is
metadata attached to a `TokenId`; it is never accepted as an execution asset.

### 2. Current SDK and protocol generation

- CLOB V2 has been production at `https://clob.polymarket.com` since
  2026-04-28. V1-signed orders and the legacy `py-clob-client` do not work
  against production. V2 changed exchange contracts, signed-order fields,
  EIP-712 exchange domain version, collateral from USDC.e to pUSD, and fee
  handling. See
  [Migrating to CLOB V2](https://docs.polymarket.com/v2-migration).
- The official current Python integration is the unified
  [`polymarket-client`](https://docs.polymarket.com/getting-started/python)
  package from the non-archived
  [`Polymarket/py-sdk`](https://github.com/Polymarket/py-sdk). It provides
  public/secure, async/sync clients, typed identifiers, `Decimal` for
  precision-sensitive values, consistent pagination, and async realtime
  subscriptions. Its latest release observed during this review was
  `polymarket-client-v0.2.0` (2026-07-24); its README warns that minor releases
  on the pre-1.0 line may break APIs.
- The intermediate `py-clob-client-v2` repository itself recommends the unified
  `py-sdk` for new projects. The older
  [`py-clob-client`](https://github.com/Polymarket/py-clob-client) is archived.

**Adapter constraint:** pin an exact `polymarket-client` version; translate its
models at one adapter boundary; do not expose SDK types to strategy, risk, OMS,
or persistence schemas. Upgrade requires adapter conformance evidence, not an
unbounded dependency bump.

### 3. Wallet identity and authentication

- Current account wallet types are Deposit Wallet, legacy Proxy Wallet, legacy
  Safe Wallet, and allowlisted EOA. Deposit Wallet is the default for accounts
  deployed on or after 2026-05-04. The signer and account wallet can be
  different identities. See
  [Wallets and Authentication](https://docs.polymarket.com/trading/wallets-auth).
- CLOB L1 authentication uses an EIP-712 wallet signature to create or derive
  API credentials. Private CLOB requests use L2 credentials: API key, secret,
  passphrase, signer address, timestamp, and an HMAC signature. The private key
  remains required for order signing. The official SDK resolves the account
  wallet/wallet type and creates or derives credentials for a secure client.
- pUSD and Conditional Token approvals are required for the applicable
  exchange before placing orders. The current Polygon mainnet contract
  addresses, including pUSD, Conditional Tokens, standard CTF Exchange, and Neg
  Risk CTF Exchange, are maintained on the official
  [Contracts](https://docs.polymarket.com/resources/contracts) page.

**Adapter constraint:** configuration must persist an explicit tuple of
`signer`, `account_wallet`, `wallet_type`, `chain_id`, and credential reference.
It must verify the resolved identity and current official contract addresses at
preflight. Secrets/private keys must not enter plans, logs, OMS events, or
browser/client code.

### 4. Orders, signing, and order types

- Every order is an offchain-created EIP-712 signed limit order that the CLOB
  matches and the exchange settles onchain. A so-called market order is a
  marketable limit order. The order names an outcome token ID, side, price,
  size, expiration, and millisecond timestamp used for uniqueness. See
  [Order Lifecycle](https://docs.polymarket.com/concepts/order-lifecycle).
- The supported execution policies are GTC, GTD, FOK, and FAK. GTC and GTD can
  rest; FOK is all-or-nothing immediate execution; FAK fills available size and
  cancels the remainder. Post-only is an independent constraint on GTC/GTD: an
  order that would cross is rejected. GTD expires one minute before the stated
  expiration as a safety buffer. See
  [Place Orders](https://docs.polymarket.com/trading/place-orders).
- Price must conform to the market tick size, and size to its minimum order
  size. The market-info response is the joined source for these live venue
  constraints. Order acceptance is not settlement finality: order status and
  trade settlement status are separate lifecycles.
- Trade statuses progress through nonterminal matched/mined/retrying states to
  terminal confirmed or failed states. A successful submit response can carry
  order ID, insertion status, associated trade IDs, and transaction hashes; the
  OMS must not count a request attempt as an accepted or settled order.
- During matching-engine restarts, order-related endpoints return HTTP 425.
  After restart, the engine is post-only for two minutes; cancels remain
  accepted, and blindly retrying an unchanged non-post-only order is invalid.
  See
  [Matching Engine Restarts](https://docs.polymarket.com/trading/matching-engine).

**Adapter constraint:** preserve `order_type`, `post_only`, expiration,
condition/token identity, venue parameters, SDK request ID/timestamp, returned
order ID, associated trade IDs, and every observed status transition. Use exact
decimal/fixed-point values; never map all immediate execution to a generic
"market" flag.

### 5. Cancellation scope and dead-man protection

- Cancellation exists at four distinct scopes: one order ID, a set of order
  IDs, one outcome token or entire condition, and the entire authenticated
  account. Condition/token cancellation requires at least one filter;
  account-wide `cancel_all` is an emergency action. See
  [Manage Orders](https://docs.polymarket.com/trading/manage-orders).
- Cancellation responses contain both `canceled` and `not_canceled`; a 200
  response can therefore be partially successful. For a partially filled
  order, only the unfilled remainder can be canceled. Cancels remain available
  in cancel-only mode.
- The CLOB order-heartbeat dead-man switch is separate from WebSocket PING/PONG.
  After the first accepted order heartbeat, the same CLOB credentials must send
  it every five seconds. Missing a valid heartbeat for ten seconds causes all
  open orders owned by those credentials to be canceled; the server check can
  add up to five seconds. See
  [Order Heartbeats](https://docs.polymarket.com/trading/manage-orders#order-heartbeats).

**Adapter constraint:** represent cancellation scope as a required tagged
union. Never translate a market/condition request into account-wide
`cancel_all`. Reconcile partial cancellation results. Live quoting requires the
authenticated order heartbeat and must fail closed if its acknowledgements or
schedule are unhealthy.

### 6. WebSocket authentication, heartbeat, reconnect, and recovery

- Market and user channels are at
  `wss://ws-subscriptions-clob.polymarket.com/ws/market` and `/ws/user`.
  Market data is public. The user subscription sends CLOB API key, secret, and
  passphrase immediately after connecting; it may optionally filter by
  condition IDs. Credentials must remain server-side. See
  [Real-Time Order Updates](https://docs.polymarket.com/trading/realtime-order-updates).
- Both channels use application text frames: client `PING` every ten seconds,
  server `PONG`. This connection liveness mechanism does not replace the
  separate REST order-heartbeat dead-man switch.
- The market stream supplies books/deltas, last trades, tick-size changes, best
  bid/ask, and optional lifecycle events. The user stream supplies order
  placement/update/cancellation and trade settlement changes.
- The official recovery rule is explicit: realtime updates neither replace
  authoritative account reads nor replay everything missed during a
  disconnect. After reconnecting, fetch paginated open orders and recent
  account trades, rebuild local state, then resume applying new events.

**Adapter/OMS constraint:** use a connection state machine with subscription
acknowledgement, PING/PONG deadline, bounded reconnect/backoff, and a
`RECOVERING` barrier. The executor must not emit new orders until snapshot
refresh and stream handoff are consistent. Since the official docs specify no
replay cursor, the OMS needs an overlap window and idempotency by order/trade ID
to close the snapshot/stream race.

### 7. Orders, trades, fills, balances, and reconciliation truth

- Authenticated `GET /data/orders` returns current open orders with pagination
  and optional order/condition/token filters. `GET /data/trades` returns account
  trades with pagination and filters including trade, maker, condition, token,
  and time. See
  [Get user orders](https://docs.polymarket.com/api-reference/trade/get-user-orders)
  and [Get trades](https://docs.polymarket.com/api-reference/trade/get-trades).
- An order can be accepted/live, matched, delayed, unmatched, or canceled;
  trade records separately carry settlement status. The OMS must join order
  updates to associated trade IDs rather than infer fills only from disappearing
  open orders.
- Outcome tokens are Polygon ERC-1155 balances and pUSD is Polygon ERC-20
  collateral. The exchange settlement transfers these assets atomically, and a
  confirmed trade has reached Polygon finality. Current addresses come from the
  official Contracts registry.

**Reconciliation inference:** no single source answers every state question.
Use the CLOB open-order endpoint for current offchain resting exposure; CLOB
trade records for matching and settlement progression; and direct Polygon
pUSD/ERC-1155 reads for final asset ownership. Gamma/Data API or indexed
analytics may enrich discovery/history but must not override direct chain reads
for funds. This is an architectural inference from the documented hybrid
offchain-match/onchain-settle lifecycle, not a verbatim Polymarket guarantee
that one endpoint is globally authoritative.

### 8. Fees

- Fees are market-dependent and applied at match time rather than embedded in
  the signed V2 order. Platform makers are currently not charged; takers pay
  according to the market's fee curve. Fee-enabled status and parameters must
  be queried per condition through CLOB market info. See
  [Fees](https://docs.polymarket.com/trading/fees).
- The official formula is `shares × feeRate × price × (1 - price)`; category
  rates and rebate percentages are product policy and may change. Maker rebates
  are distributed separately and must not be assumed as guaranteed trade PnL.
- Optional builder fees are additive to platform fees and require an explicit
  builder code; Polymind's single-operator MVP has no need to attach one unless
  that product decision is made separately.

**Adapter/accounting constraint:** snapshot fee configuration with the order
decision, but book actual fees from confirmed trade/account evidence. PnL and
risk must not hardcode “Polymarket is fee-free” or treat expected rebates as
realized cash.

### 9. Test and sandbox availability

- The official CLOB OpenAPI specification lists both production and a staging
  base URL. However, current integration guidance does not document public
  staging credentials, faucets, funded test assets, lifecycle guarantees, or a
  supported prediction-market sandbox.
- The CLOB V2 migration guide says the pre-cutover testing host is no longer the
  production target and directs integrators to test with a **small funded
  wallet on production**, including discovery, signing, posting, cancellation,
  and settlement. The unified Python SDK's published environment module exposes
  a production environment; its repository gates order-placing integration
  tests behind both credentials and an explicit metered-test opt-in. See
  [CLOB V2 migration](https://docs.polymarket.com/v2-migration) and the
  [`py-sdk` testing guidance](https://github.com/Polymarket/py-sdk#testing).

**Known unknown:** the mere presence of `clob-staging.polymarket.com` in the
OpenAPI server list does not establish that third-party developers can obtain
funds/credentials or rely on it. Treat public sandbox support as unavailable
until Polymarket publishes an onboarding and lifecycle contract.

## Required adapter conformance baseline

Before any live-promotion decision, the adapter test matrix must demonstrate:

1. exact event/market/condition/token/order/trade identity round trips;
2. official SDK version pinning and typed translation without SDK leakage;
3. signer/account-wallet/wallet-type resolution and allowance preflight;
4. GTC, GTD, FOK, FAK, post-only, tick-size, minimum-size, and fee handling;
5. order acceptance versus trade confirmation as separate durable lifecycles;
6. all four cancellation scopes plus partial cancellation reconciliation;
7. WebSocket auth, subscription, PING/PONG, reconnect, snapshot refresh,
   overlap deduplication, and no-order recovery barrier;
8. order-heartbeat expiry and emergency cancellation behavior;
9. paginated open-order/trade recovery and direct-chain pUSD/ERC-1155 balance
   reconciliation;
10. HTTP 425, cancel-only/post-only modes, timeouts, duplicate responses,
    delayed/out-of-order events, and process crash at every durable boundary;
11. a manually armed, capital-capped production smoke test using a dedicated
    funded wallet only after all non-live evidence passes.

## Unknowns that later decisions must not silently fill in

- Public access and operational guarantees for the documented staging host.
- Exact retention/time-window guarantees for account trades and whether every
  status transition remains queryable after long downtime.
- A server-supported replay cursor or sequence number for user WebSocket events;
  none is documented in the current channel contract.
- Reorg/finality depth and RPC-provider policy appropriate for direct Polygon
  balance reconciliation.
- Whether Polymind will use a Deposit Wallet, a legacy wallet, or an allowlisted
  EOA. The adapter contract can support an explicit wallet type, but live
  promotion must select and test exactly one.

These are promotion blockers where they affect recovery or funds; they are not
license to substitute optimistic defaults.

