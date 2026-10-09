# Sidebar and chat history — 8 October 2026

## Delivered

- Main navigation expands to labels or collapses to icons. The choice survives reload.
- Collapsed icons retain accessible names, tooltips and the current-page indicator.
- A separate history column sits between navigation and the conversation on desktop.
- History lists each conversation once, newest first, using its first question as the title.
- Selecting a chat restores its complete messages, receipts and original forecast/data/order context.
- New chat starts a separate conversation without deleting existing chats or forecasts.
- History can be hidden independently. On smaller screens it opens as a full-width view; choosing a chat returns to the conversation.
- English/Persian navigation, mirrored layout, shared visual tokens, no inline styles.

## Storage and safeguards

The existing SQLite journal is reused and migrated in place. Messages and receipts
are unchanged. Chats are private to their original user. The list is paginated in
groups of 50. Browser storage contains opaque pointers/preferences, not messages.
Reading older messages does not renew expired actions or bypass evidence checks.
The assistant still receives only bounded recent exchanges; showing full history
does not increase the provider memory limit or make an AI call.

## Verification

- 30 focused backend tests pass, including migration, pagination, privacy, complete
  history restoration, context separation and unchanged action expiry.
- 187 frontend tests pass; production build passes.
- Synthetic browser checks: collapse/reload, 12-exchange restoration, context-correct
  follow-up, New chat preserving earlier chats, mobile history at 390px, and Persian
  laptop layout. No provider calls.
- Running app: existing journal conversations load and the November 2026 chat
  reopens with its saved answer. Local history endpoint responds successfully.

Evidence: `screenshots/chat-sidebar-history-live.png`.
