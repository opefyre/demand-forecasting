import React, { useRef } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  NotePencil,
  SidebarSimple,
  DotsThree,
  PushPin,
  Archive,
  Trash,
  ArrowCounterClockwise,
  Link,
  DownloadSimple,
  CaretDown,
  MagnifyingGlass,
} from "@phosphor-icons/react";
import { t as uiText, interfaceDirection } from "./localization.mjs";
import {useMenuHandoff} from './ui-layout.jsx';

function ChatMenu({ chat, busy, onAction }) {
  const trigger = useRef(null),handoff=useMenuHandoff();
  const items =
    chat.status === "active"
      ? [
          ["rename", "Rename", NotePencil],
          [
            chat.pinned ? "unpin" : "pin",
            chat.pinned ? "Unpin" : "Pin",
            PushPin,
          ],
          ["archive", "Archive", Archive],
          ["share", "Share", Link],
          ["export", "Download conversation", DownloadSimple],
          ["trash", "Move to Trash", Trash],
        ]
      : [
          ["restore", "Restore", ArrowCounterClockwise],
          ["export", "Download conversation", DownloadSimple],
          ...(chat.status === "archived"
            ? [["trash", "Move to Trash", Trash]]
            : []),
        ];
  return (
    <DropdownMenu.Root dir={interfaceDirection()} modal={false}>
      <DropdownMenu.Trigger asChild>
        <button
          ref={trigger}
          type="button"
          className="ui-chat-history-menu"
          disabled={busy}
          aria-label={uiText("Chat options for {{name}}", { name: chat.title })}
          title={uiText("Chat options")}
        >
          <DotsThree aria-hidden="true" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="ui-menu"
          align="start"
          side="right"
          collisionPadding={12}
          onCloseAutoFocus={handoff.close}
        >
          {items.map(([id, label, Icon]) => (
            <DropdownMenu.Item
              className="ui-menu-item"
              key={id}
              onSelect={() => {
                handoff.select(trigger.current,()=>onAction(chat,id));
              }}
            >
              <Icon aria-hidden="true" />
              <span>{uiText(label)}</span>
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function ChatHistory({
  chats,
  activeHead,
  busy,
  loading,
  error,
  nextOffset,
  onMore,
  onOpen,
  onNewChat,
  onToggle,
  onAction,
  folder = "active",
  onFolder,
  search = "",
  onSearch,
}) {
  return (
    <aside
      className="ui-chat-history"
      id="chat-history"
      aria-label={uiText("Chat history")}
    >
      <header className="ui-chat-history-header">
        <DropdownMenu.Root dir={interfaceDirection()} modal={false}>
          <DropdownMenu.Trigger asChild>
            <button
              className="ui-chat-history-folder"
              type="button"
              aria-label={uiText("Chat folders")}
            >
              {uiText(
                folder === "archived"
                  ? "Archived chats"
                  : folder === "trash"
                    ? "Trash"
                    : "Chats",
              )}
              <CaretDown aria-hidden="true" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content className="ui-menu" align="start">
              {[
                ["active", "Chats"],
                ["archived", "Archived chats"],
                ["trash", "Trash"],
              ].map(([id, label]) => (
                <DropdownMenu.Item
                  key={id}
                  className="ui-menu-item"
                  onSelect={() => onFolder(id)}
                >
                  {uiText(label)}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
        <button
          type="button"
          className="ui-chat-history-toggle"
          onClick={onToggle}
          aria-controls="chat-history"
          aria-expanded="true"
          aria-label={uiText("Hide chat history")}
          title={uiText("Hide chat history")}
        >
          <SidebarSimple aria-hidden="true" />
        </button>
      </header>
      <button
        type="button"
        className="ui-chat-history-new"
        disabled={busy}
        onClick={onNewChat}
      >
        <NotePencil aria-hidden="true" />
        {uiText("New chat")}
      </button>
      <label className="ui-chat-history-search">
        <MagnifyingGlass aria-hidden="true" />
        <input
          aria-label={uiText("Search chats")}
          placeholder={uiText("Search chats")}
          value={search}
          maxLength={100}
          onChange={(event) => onSearch(event.target.value)}
        />
      </label>
      <nav
        className="ui-chat-history-list"
        aria-label={uiText("Previous chats")}
        aria-busy={loading}
      >
        {chats.map((chat, index) => (
          <React.Fragment key={chat.id}>
            {chat.pinned && (index === 0 || !chats[index - 1].pinned) && (
              <h3 className="ui-chat-history-group">{uiText("Pinned")}</h3>
            )}
            {!chat.pinned && index > 0 && chats[index - 1].pinned && (
              <h3 className="ui-chat-history-group">{uiText("Recent")}</h3>
            )}
            <div
              className="ui-chat-history-row"
              data-current={activeHead === chat.head_id}
            >
              <button
                type="button"
                disabled={busy}
                aria-current={activeHead === chat.head_id ? "true" : undefined}
                className="ui-chat-history-item"
                title={chat.title}
                onClick={() => onOpen(chat.head_id)}
              >
                <span dir="auto">{chat.title}</span>
              </button>
              <ChatMenu chat={chat} busy={busy} onAction={onAction} />
            </div>
          </React.Fragment>
        ))}
        {!chats.length && !loading && !error && (
          <p className="ui-chat-history-status">
            {uiText(
              search
                ? "No matching chats"
                : folder === "active"
                  ? "No chats yet"
                  : "No conversations",
            )}
          </p>
        )}
        {loading && (
          <p role="status" className="ui-chat-history-status">
            {uiText("Loading chats…")}
          </p>
        )}
        {error && (
          <p role="alert" className="ui-chat-history-status">
            {uiText("Could not load chats.")}{" "}
            <button
              type="button"
              className="text-btn"
              onClick={() => onMore(0)}
            >
              {uiText("Retry")}
            </button>
          </p>
        )}
        {nextOffset != null && (
          <button
            type="button"
            className="ui-chat-history-more"
            disabled={loading}
            onClick={() => onMore(nextOffset)}
          >
            {uiText("Show older chats")}
          </button>
        )}
      </nav>
    </aside>
  );
}

export function ChatHistoryToggle({
  visible,
  mobileOpen,
  onToggle,
  onMobileToggle,
}) {
  return (
    <header className="ui-chat-history-controls">
      {!visible && (
        <button
          type="button"
          className="ui-chat-history-toggle ui-chat-history-desktop"
          onClick={onToggle}
          aria-controls="chat-history"
          aria-expanded="false"
          title={uiText("Show chat history")}
          aria-label={uiText("Show chat history")}
        >
          <SidebarSimple aria-hidden="true" />
        </button>
      )}
      <button
        type="button"
        className="ui-chat-history-toggle ui-chat-history-mobile"
        onClick={onMobileToggle}
        aria-controls="chat-history"
        aria-expanded={mobileOpen}
        title={uiText("Chat history")}
        aria-label={uiText("Chat history")}
      >
        <SidebarSimple aria-hidden="true" />
      </button>
    </header>
  );
}
