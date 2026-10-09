import React, { useEffect, useRef } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ArrowUp, CircleNotch, Plus, User } from "@phosphor-icons/react";
import { t as uiText, interfaceDirection } from "./localization.mjs";
import { AssistantMascot } from "./assistant-mascot";
import {useMenuHandoff} from './ui-layout.jsx';

export const CHAT_EXAMPLES = [
  "Forecast the next 6 months",
  "Check my sales data",
  "Compare forecasting methods",
];

export function composerShouldSend(event) {
  return (
    event.key === "Enter" &&
    !event.shiftKey &&
    !event.nativeEvent?.isComposing &&
    event.keyCode !== 229
  );
}

/** One shared chat layout: centred welcome, then a scrolling conversation and docked input. */
export function ChatSurface({
  active,
  children,
  value,
  onChange,
  onSend,
  busy = false,
  ready = true,
  readOnly = false,
  tools = [],
  sourceName,
  onNewChat,
  newChatDisabled = false,
  pending = "",
  error,
  scrollKey,
  showNewChat = true,
  quickActions = [],
}) {
  const input = useRef(null),
    transcript = useRef(null);
  const previousBusy = useRef(busy);
  useEffect(() => {
    if (previousBusy.current && !busy && active) input.current?.focus();
    previousBusy.current = busy;
  }, [busy, active]);
  useEffect(() => {
    const node = transcript.current;
    if (node) node.scrollTo({ top: node.scrollHeight });
  }, [active, pending, scrollKey]);
  const disabled = busy || !ready || value.trim().length < 2;
  function submit(event) {
    event.preventDefault();
    if (!disabled) onSend();
  }
  return (
    <section
      className={"ui-chat " + (active ? "ui-chat-active" : "ui-chat-empty")}
      aria-label={uiText("Sales forecast chat")}
    >
      {active ? (
        <header className="ui-chat-header">
          {showNewChat && (
            <button
              type="button"
              className="text-btn"
              disabled={newChatDisabled}
              title={uiText(
                "Start without earlier messages. Saved forecasts are unchanged.",
              )}
              onClick={() => {
                onNewChat();
                input.current?.focus();
              }}
            >
              {uiText("New chat")}
            </button>
          )}
        </header>
      ) : (
        <div className="ui-chat-welcome">
          <span className="ui-chat-welcome-character" aria-hidden="true">
            <AssistantMascot />
          </span>
          <h1>{uiText("What would you like to forecast?")}</h1>
        </div>
      )}
      {active && (
        <div
          className="ui-chat-transcript"
          dir="ltr"
          ref={transcript}
          role="log"
          aria-label={uiText("Conversation")}
        >
          {children}
          {pending && (
            <>
              <ChatMessage side="user">
                <div className="ui-chat-text" dir="auto">
                  {pending}
                </div>
              </ChatMessage>
              <ChatMessage>
                <p className="ui-chat-working" role="status">
                  <CircleNotch className="ai-working" aria-hidden="true" />
                  {uiText("Assistant is working")}
                </p>
              </ChatMessage>
            </>
          )}
        </div>
      )}
      <div className="ui-chat-dock">
        <form
          className="ui-chat-composer"
          onSubmit={submit}
          aria-label={uiText("Message the assistant")}
        >
        <ChatTools tools={tools} sourceName={sourceName} disabled={busy||readOnly} />
          <textarea
            ref={input}
            rows={1}
            aria-label={uiText("Message the assistant")}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            maxLength={4000}
          disabled={busy||readOnly}
            placeholder={uiText("Ask about your sales forecast…")}
            onKeyDown={(event) => {
              if (composerShouldSend(event)) {
                event.preventDefault();
                if (!disabled) onSend();
              }
            }}
          />
          <button
            type="submit"
            className="ui-chat-send"
            disabled={disabled}
            title={uiText("Send message")}
            aria-label={
              busy ? uiText("Assistant is working") : uiText("Send message")
            }
          >
            {busy ? (
              <CircleNotch className="ai-working" aria-hidden="true" />
            ) : (
              <ArrowUp aria-hidden="true" />
            )}
          </button>
        </form>
        {error}
      </div>
      {!active && (
        <div className="ui-chat-suggestions" aria-label={uiText("Try asking")}>
          {CHAT_EXAMPLES.map((example) => (
            <button
              type="button"
              key={example}
            disabled={busy}
              onClick={() => {
                onChange(uiText(example));
                input.current?.focus();
              }}
            >
              {uiText(example)}
            </button>
          ))}
        </div>
      )}
      {!active && quickActions.length > 0 && (
        <div
          className="ui-chat-quick-actions"
          aria-label={uiText("Quick actions")}
        >
          {quickActions.map(({ id, label, icon: Icon, onSelect }) => (
            <button
              key={id}
              type="button"
              disabled={busy}
              onClick={onSelect}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

/** Message identity and appearance are shared by saved, new and pending turns. */
export function ChatMessage({ side = "assistant", children }) {
  const user = side === "user",
    label = user ? uiText("Your message") : uiText("Assistant message");
  return (
    <section
      className={
        "ui-chat-message " +
        (user ? "ui-chat-message-user" : "ui-chat-message-assistant")
      }
      aria-label={label}
      dir="ltr"
    >
      <span
        className="ui-chat-avatar"
        role="img"
        aria-label={label}
        title={label}
      >
        {user ? <User weight="fill" aria-hidden="true" /> : <AssistantMascot />}
      </span>
      <div className="ui-chat-bubble" dir="auto">{children}</div>
    </section>
  );
}

function ChatTools({ tools, sourceName, disabled }) {
  const handoff=useMenuHandoff(),trigger = useRef(null);
  return (
    <DropdownMenu.Root dir={interfaceDirection()} modal={false}>
      <DropdownMenu.Trigger asChild>
        <button
          ref={trigger}
          type="button"
          className="ui-chat-tools"
          disabled={disabled}
          title={uiText("Add data & tools")}
          aria-label={uiText("Add data & tools")}
        >
          <Plus aria-hidden="true" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="ui-menu"
          side="top"
          align="start"
          collisionPadding={16}
          aria-label={uiText("Add data & tools")}
          onCloseAutoFocus={handoff.close}
        >
          <DropdownMenu.Label className="ui-menu-context">
            {uiText("Using: {{name}}", { name: sourceName })}
          </DropdownMenu.Label>
          {tools.map(
            ({ id, label, icon: Icon, onSelect, disabled: itemDisabled }) => (
              <DropdownMenu.Item
                className="ui-menu-item"
                key={id}
                disabled={itemDisabled}
                onSelect={() => {
                  // A dialog opened by this action must return to a live opener, not a removed menu item.
                handoff.select(trigger.current,onSelect);
                }}
              >
                <Icon aria-hidden="true" />
                <span>{label}</span>
              </DropdownMenu.Item>
            ),
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
