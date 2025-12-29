Session & Context Design
========================

Background
----------

The gateway follows a **client-managed context** model:

- Chat requests are accepted on `POST /v1/chat/completions` (and compatible aliases).
- The gateway is **stateless** with respect to conversation context:
  - no `X-Session-Id` header support,
  - no Redis-backed per-session history persistence,
  - no `/context/{session_id}` debugging endpoint.

Rationale
---------

In practice, mainstream clients (e.g. Cherry Studio) send the full conversation
history in the request payload (typically in `messages`). Upstreams themselves
can also maintain context when they expose conversation/thread semantics.

Persisting request/response history in the gateway would be redundant and adds:

- storage cost and operational complexity,
- unclear semantics when clients do not provide a stable session identifier.

Summary
-------

- The gateway focuses on routing, proxying, auditing, and metrics.
- Conversation context is expected to be provided by clients (or maintained by upstreams).
