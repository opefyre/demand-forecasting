import { t as uiText } from "./localization.mjs";
import { smoothUpdate, useSmoothState } from "./ui-motion.jsx";
import React, { useEffect, useState, useRef } from "react";
import {
  Paperclip,
  Database,
  Plugs,
  GlobeHemisphereWest,
  ChartLineUp,
  UsersThree,
} from "@phosphor-icons/react";
import { ChatSurface, ChatMessage } from "./ui-chat.jsx";
import { ChatHistory, ChatHistoryToggle } from "./ui-chat-history.jsx";
import { remembered, DemandImport } from "./sales-demand";
import { orderRevision } from "./order-revision.mjs";
import { AssistantFactorScenario } from "./assistant-factor-scenario";
import { FactorLink } from "./factor-links.jsx";
import { FactorBatch } from "./factor-batch.jsx";
import { AssistantFactorBatchCard } from "./assistant-factor-batch.jsx";
import { planningBasis } from "./planning-calendar.mjs";
import {
  chatKey,
  readChatHead,
  writeChatHead,
  chatPayload,
  readInputChoice,
  writeInputChoice,
} from "./assistant-history.mjs";
import { InputMappingProposal } from "./input-mapping-proposal";
import { InputCorrectionProposal } from "./input-correction-proposal";
import { AssistantComparison } from "./assistant-comparison";
import { AssistantSavedOrders } from "./order-reuse";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { canShare, recipient } from "./ai-sharing.mjs";

export function AssistantWorkspace({
  api,
  ui,
  run: currentRun,
  datasets = [],
  canEdit,
  openRun,
  refresh,
  renderImport,
  startUpdate,
  runDataset,
  navigate,
  setDataView,
  home = false,
  onNewForecast,
}) {
  const { Button, ErrorBox, Modal, Field } = ui;
  const [renaming, setRenaming] = useState(null),
    [renameBusy, setRenameBusy] = useState(false),
    [renameError, setRenameError] = useState(null);
  const [chatFolder, setChatFolder] = useState("active"),
    [chatSearch, setChatSearch] = useState(""),
    [managing, setManaging] = useState(false),
    [trashing, setTrashing] = useState(null),
    [sharing, setSharing] = useState(null),
    [copied, setCopied] = useState(false);
  const historyFilter = useRef({ folder: "active", search: "" });
  historyFilter.current = { folder: chatFolder, search: chatSearch };
  const titleTimer = useRef(null);
  useEffect(() => () => clearTimeout(titleTimer.current), []);
  const [snapshot, setSnapshot] = useState(""),
    [contextReady, setContextReady] = useState(false);
  const [question, setQuestion] = useState(""),
    [consent, setConsent] = useState(null),
    [permission, setPermission] = useState(null);
  const [turns, setTurns] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [actionBusy, setActionBusy] = useState("");
  const [pending, setPending] = useState("");
  const [sourceChoice, setSourceChoice] = useState(() =>
      readInputChoice(localStorage, currentRun?.run_id, datasets),
    ),
    [choosing, setChoosing] = useState(false),
    [search, setSearch] = useState(""),
    [importing, setImporting] = useState(false);
  const [orderEditing, setOrderEditing] = useState(null);
  const [repeatInitial, setRepeatInitial] = useState(null);
  const [preparing, setPreparing] = useState(null);
  const [openedChat, setOpenedChat] = useState(null),
    [openingChat, setOpeningChat] = useState(false);
  const [chatReset, setChatReset] = useState(0);
  const [chats, setChats] = useState([]),
    [historyLoading, setHistoryLoading] = useState(false),
    [historyError, setHistoryError] = useState(false),
    [nextOffset, setNextOffset] = useState(null);
  const [historyVisible, setHistoryVisible] = useSmoothState(true),
    [historyMobile, setHistoryMobile] = useSmoothState(false);
  const historyRequest = useRef(0),
    openRequest = useRef(0);
  const run = openedChat ? openedChat.run : sourceChoice ? null : currentRun;
  const datasetId = openedChat
    ? openedChat.context.dataset_id
    : sourceChoice.startsWith("dataset:")
      ? sourceChoice.slice(8)
      : null;
  const dataset = datasets.find((d) => d.id === datasetId);
  const sourceName = run
    ? run.scenario_name || run.dataset_name || uiText("Current forecast")
    : dataset?.name || uiText("No sales data selected");
  const keyFor = (s) => chatKey(run?.run_id, s, datasetId);
  const generation = useRef(0);
  const previousRun = useRef(currentRun?.run_id);
  useEffect(() => {
    if (previousRun.current !== currentRun?.run_id) {
      previousRun.current = currentRun?.run_id;
      openRequest.current++;
      setOpeningChat(false);
      setOpenedChat(null);
      setSourceChoice("");
    }
  }, [currentRun?.run_id]);
  useEffect(() => {
    if (!openedChat)
      writeInputChoice(localStorage, currentRun?.run_id, datasetId);
  }, [currentRun?.run_id, datasetId, openedChat]);
  async function loadChats(offset = 0) {
    const request = ++historyRequest.current;
    setHistoryLoading(true);
    setHistoryError(false);
    try {
      const { folder, search } = historyFilter.current;
      const result = await api(
        "/api/ai/conversations?" +
          new URLSearchParams({ offset, status: folder, search }),
      );
      if (request !== historyRequest.current) return;
      setChats((previous) =>
        offset
          ? [
              ...previous,
              ...result.chats.filter(
                (chat) => !previous.some((item) => item.id === chat.id),
              ),
            ]
          : result.chats,
      );
      setNextOffset(result.next_offset);
    } catch {
      if (request === historyRequest.current) setHistoryError(true);
    } finally {
      if (request === historyRequest.current) setHistoryLoading(false);
    }
  }
  async function manageChat(chat, operation) {
    if (managing || busy || actionBusy) return;
    if (operation === "rename") {
      setRenameError(null);
      setRenaming({ ...chat });
      return;
    }
    if (operation === "share") {
      setCopied(false);
      setSharing(chat);
      return;
    }
    if (operation === "export") {
      const link = document.createElement("a");
      link.href = "/api/ai/conversations/" + chat.head_id + "/export";
      link.download = "conversation.txt";
      link.click();
      return;
    }
    if (operation === "trash") {
      setTrashing(chat);
      return;
    }
    await saveChatAction(chat, operation);
  }
  async function copyChatLink() {
    try {
      await navigator.clipboard.writeText(
        window.location.origin + "/today?chat=" + sharing.head_id,
      );
      setCopied(true);
    } catch {
      setError(uiText("Could not copy the link. Select and copy it above."));
    }
  }
  async function saveChatAction(chat, operation) {
    setManaging(true);
    setError("");
    try {
      await api("/api/ai/conversations/" + chat.head_id + "/manage", {
        operation,
      });
      if (chat.head_id === turns.at(-1)?.id || chat.id === openedChat?.id) {
        if (operation === "restore") await openChat(chat.head_id);
        else if (["archive", "trash"].includes(operation)) newChat();
      }
      setTrashing(null);
      await loadChats();
    } catch (e) {
      setError(e.message);
    } finally {
      setManaging(false);
    }
  }
  async function renameChat(e) {
    e.preventDefault();
    setRenameBusy(true);
    setRenameError(null);
    try {
      await api("/api/ai/conversations/" + renaming.head_id + "/rename", {
        title: renaming.title.trim(),
      });
      setRenaming(null);
      await loadChats();
    } catch (e) {
      setRenameError(e);
    } finally {
      setRenameBusy(false);
    }
  }
  function awaitTitle(attempt = 0) {
    clearTimeout(titleTimer.current);
    titleTimer.current = setTimeout(async () => {
      try {
        if (
          historyFilter.current.folder !== "active" ||
          historyFilter.current.search
        )
          return;
        const request = ++historyRequest.current;
        const result = await api("/api/ai/conversations?offset=0");
        if (request !== historyRequest.current) return;
        setChats(result.chats);
        setNextOffset(result.next_offset);
        if (result.chats.some((c) => c.title_pending) && attempt < 14)
          awaitTitle(attempt + 1);
      } catch {}
    }, 2000);
  }
  useEffect(() => {
    loadChats();
    return () => {
      historyRequest.current++;
      openRequest.current++;
    };
  }, [api]);
  useEffect(() => {
    historyRequest.current++;
    const timer = setTimeout(() => loadChats(), chatSearch ? 250 : 0);
    return () => clearTimeout(timer);
  }, [chatFolder, chatSearch]);
  useEffect(() => {
    const head = new URLSearchParams(window.location.search).get("chat");
    if (head && /^[a-f0-9]{32}$/.test(head)) openChat(head);
  }, []);
  async function openChat(head) {
    if (busy || actionBusy || openingChat) return;
    const request = ++openRequest.current;
    setOpeningChat(true);
    setError("");
    try {
      const saved = await api(
        "/api/ai/conversations/" + encodeURIComponent(head),
      );
      const savedRun = saved.context.run_id
        ? await api("/api/runs/" + encodeURIComponent(saved.context.run_id))
        : null;
      if (request !== openRequest.current) return;
      setOpenedChat({ ...saved, run: savedRun });
      setHistoryMobile(false);
    } catch (e) {
      if (request === openRequest.current) setError(e.message);
    } finally {
      if (request === openRequest.current) setOpeningChat(false);
    }
  }
  function chooseSource(value) {
    openRequest.current++;
    setOpeningChat(false);
    setOpenedChat(null);
    setSourceChoice(value);
  }
  useEffect(() => {
    let live = true;
    generation.current++;
    setSnapshot("");
    setTurns([]);
    setPending("");
    setQuestion("");
    setError("");
    setBusy(false);
    setActionBusy("");
    setContextReady(false);
    setConsent(false);
    setPermission(false);
    setOrderEditing(null);
    setPreparing(null);
    (async () => {
      if (openedChat) {
        setSnapshot(openedChat.context.snapshot_id || "");
        setTurns(openedChat.turns);
        setContextReady(true);
        writeChatHead(
          localStorage,
          keyFor(openedChat.context.snapshot_id),
          openedChat.head_id,
        );
        return;
      }
      const data = run
        ? await api("/api/sales/runs/" + run.run_id + "/inputs")
        : { snapshots: [] };
      if (!live) return;
      const selected = run
        ? data.snapshots.find((s) => s.id === remembered(run.run_id))?.id ||
          data.snapshots[0]?.id ||
          ""
        : "";
      setSnapshot(selected);
      const key = keyFor(selected),
        head = readChatHead(localStorage, key);
      if (head) {
        try {
          const history = await api(
            "/api/ai/conversations/" + encodeURIComponent(head),
          );
          if (
            history.context.run_id !== (run?.run_id || null) ||
            history.context.dataset_id !== (datasetId || null) ||
            history.context.snapshot_id !== (selected || null)
          )
            throw Error("Chat inputs changed.");
          if (live) setTurns(history.turns);
        } catch (e) {
          if (live) {
            writeChatHead(localStorage, key, null);
            setError(
              "Previous chat could not be reopened. You can start a new conversation.",
            );
          }
        }
      }
      if (live) setContextReady(true);
    })().catch((e) => live && setError(e.message));
    return () => {
      live = false;
      generation.current++;
    };
  }, [run?.run_id, datasetId, openedChat, chatReset]);
  function newChat() {
    setChatFolder('active');setChatSearch('');
    smoothUpdate(() => {
      writeChatHead(localStorage, keyFor(snapshot), null);
      if (openedChat)
        setOpenedChat({
          ...openedChat,
          id: null,
          status: "active",
          head_id: null,
          turns: [],
        });
      else setChatReset((value) => value + 1);
      setTurns([]);
      setQuestion("");
      setError("");
    });
    setHistoryMobile(false);
  }
  async function send(approved = false) {
    if (busy || openingChat || question.trim().length < 2) return;
    setError("");
    if (!contextReady) {
      setError("Sales data is still loading. Please try again.");
      return;
    }
    setBusy(true);
    const current = generation.current,
      submittedQuestion = question.trim();
    try {
      const status = await api("/api/ai/status");
      if (current !== generation.current) return;
      if (!status.ready) {
        setError(status.message + " Your message has not been sent.");
        return;
      }
      const allowed = approved === true ? permission?.consent_id : consent;
      if (!canShare(status, allowed)) {
        setPermission(status);
        return;
      }
      setPermission(null);
      smoothUpdate(() => {
        setPending(submittedQuestion);
        setQuestion("");
      });
      const result = await api("/api/ai/chat", {
        ...chatPayload(
          submittedQuestion,
          run?.run_id,
          snapshot,
          turns,
          datasetId,
        ),
        provider_id: status.consent_id,
      });
      if (current !== generation.current) return;
      writeChatHead(localStorage, keyFor(snapshot), result.id);
      setTurns((v) => [...v, { ...result, question: submittedQuestion }]);
      loadChats();
      if (result.title_pending) awaitTitle();
    } catch (e) {
      if (current === generation.current) {
        setError(e.message);
        setQuestion(submittedQuestion);
      }
    } finally {
      if (current === generation.current) {
        setBusy(false);
        setPending("");
      }
    }
  }
  async function execute(turn, index, confirmation = {}) {
    const key = turn.id + index;
    setActionBusy(key);
    setError("");
    const current = generation.current;
    try {
      const result = await api(
        "/api/ai/turns/" + turn.id + "/actions/" + index,
        confirmation,
      );
      if (current !== generation.current) return;
      if (result.workflow === "new_forecast") {
        setTurns((v) =>
          v.map((t) =>
            t.id === turn.id
              ? { ...t, results: { ...t.results, [index]: result } }
              : t,
          ),
        );
        await refresh?.();
        onNewForecast?.(result.dataset_id, result.method, result.customer);
      } else if (result.workflow === "factor_batch_review") {
        if (!run || result.run_id !== run.run_id)
          throw Error(
            "Choose the matching forecast before reviewing the batch.",
          );
        setPreparing(result);
      } else if (result.workflow === "factor_preparation") {
        if (!run || result.run_id !== run.run_id)
          throw Error("Choose the matching forecast before reviewing sources.");
        setPreparing(result);
      } else if (result.workflow === "monthly_update") {
        setTurns((v) =>
          v.map((t) =>
            t.id === turn.id
              ? { ...t, results: { ...t.results, [index]: result } }
              : t,
          ),
        );
        await startUpdate?.(
          result.run_id,
          "assistant-update-" + turn.id + "-" + index,
        );
      } else if (result.workflow === "history_refresh") {
        const source = datasets.find((d) => d.id === result.dataset_id);
        if (!source) throw Error("Refresh Data and choose this history again.");
        const sourceObjects = Object.fromEntries(
          await Promise.all(
            Object.entries(source.sources).map(async ([role, id]) => [
              role,
              await api("/api/sources/" + id),
            ]),
          ),
        );
        if (current === generation.current) {
          setRepeatInitial({ ...source, sourceObjects, repeat_upload: true });
          setImporting(true);
        }
      } else if (result.workflow === "order_import") {
        if (!run || result.run_id !== run.run_id)
          throw new Error("Choose the matching forecast before adding orders.");
        const initial = result.snapshot_id
          ? orderRevision(await api("/api/sales/inputs/" + result.snapshot_id))
          : {
              inputs: await api(
                "/api/sales/runs/" + result.run_id + "/starter",
              ),
            };
        if (current === generation.current) setOrderEditing(initial);
      } else
        setTurns((v) =>
          v.map((t) =>
            t.id === turn.id
              ? { ...t, results: { ...t.results, [index]: result } }
              : t,
          ),
        );
    } catch (e) {
      if (current === generation.current) setError(e.message);
    } finally {
      if (current === generation.current) setActionBusy("");
    }
  }
  if (importing && renderImport)
    return renderImport({
      initial: repeatInitial,
      returnLabel: home ? "Back to Home" : "Back to Assistant",
      onCancel: () => {
        setImporting(false);
        setRepeatInitial(null);
      },
      onSaved: async (d) => {
        await refresh?.();
        chooseSource("dataset:" + d.id);
        setImporting(false);
        setRepeatInitial(null);
      },
    });
  if (orderEditing && run)
    return (
      <DemandImport
        api={api}
        ui={ui}
        run={run}
        initial={orderEditing}
        onCancel={() => setOrderEditing(null)}
        onSaved={async (value) => {
          localStorage.setItem(`demandlab.orders.${run.run_id}`, value.id);
          setOrderEditing(null);
          openRun(run.run_id, "demand");
        }}
      />
    );
  const tools = [
    ...(canEdit && renderImport
      ? [
          {
            id: "import",
            label: uiText("Add sales history"),
            icon: Paperclip,
            onSelect: () => {
              setRepeatInitial(null);
              setImporting(true);
            },
          },
        ]
      : []),
    {
      id: "data",
      label: uiText("Choose sales data"),
      icon: Database,
      onSelect: () => {
        setSearch("");
        setChoosing(true);
      },
    },
    ...(canEdit && navigate
      ? [
          {
            id: "factors",
            label: uiText("External factors"),
            icon: GlobeHemisphereWest,
            onSelect: () => {
              setDataView?.("external");
              navigate("data");
            },
          },
          {
            id: "connections",
            label: uiText("Connections"),
            icon: Plugs,
            onSelect: () => {
              setDataView?.("connections");
              navigate("data");
            },
          },
        ]
      : []),
  ].map((tool) => ({
    ...tool,
    disabled: !!actionBusy || openingChat || !contextReady,
  }));
  const quickActions = [
    ...(canEdit && renderImport
      ? [
          {
            id: "import",
            label: uiText("Import sales"),
            icon: Paperclip,
            onSelect: () => {
              setRepeatInitial(null);
              setImporting(true);
            },
          },
        ]
      : []),
    ...(navigate
      ? [
          {
            id: "inputs",
            label: uiText("Customers & orders"),
            icon: UsersThree,
            onSelect: () => {
              setDataView?.("customers");
              navigate("data");
            },
          },
          {
            id: "forecasts",
            label: uiText("View forecasts"),
            icon: ChartLineUp,
            onSelect: () => navigate("demand"),
          },
        ]
      : []),
  ];
  const readOnlyChat = openedChat && openedChat.status !== "active";
  return (
    <>
      <Modal
        title={uiText("Move chat to Trash?")}
        open={!!trashing}
        dismissible={!managing}
        onClose={() => setTrashing(null)}
      >
        <p>
          {uiText(
            "You can restore it from Trash. Forecasts and data stay unchanged.",
          )}
        </p>
        <div className="modal-actions">
          <Button disabled={managing} onClick={() => setTrashing(null)}>
            {uiText("Cancel")}
          </Button>
          <Button
            kind="primary"
            disabled={managing}
            onClick={() => saveChatAction(trashing, "trash")}
          >
            {uiText("Move to Trash")}
          </Button>
        </div>
      </Modal>
      <Modal
        title={uiText("Share conversation")}
        open={!!sharing}
        onClose={() => setSharing(null)}
      >
        <div className="ui-stack">
          <p>
            {uiText(
              "This link opens the chat in your signed-in workspace. It does not make it public. To share elsewhere, download the conversation.",
            )}
          </p>
          <Field title={uiText("Conversation link")}>
            <input
              readOnly
              value={
                sharing
                  ? window.location.origin + "/today?chat=" + sharing.head_id
                  : ""
              }
            />
          </Field>
          <div className="modal-actions">
            <Button onClick={() => manageChat(sharing, "export")}>
              {uiText("Download conversation")}
            </Button>
            <Button kind="primary" onClick={copyChatLink}>
              {uiText(copied ? "Copied" : "Copy link")}
            </Button>
          </div>
        </div>
      </Modal>
      <Modal
        title={uiText("Rename chat")}
        open={!!renaming}
        dismissible={!renameBusy}
        onClose={() => setRenaming(null)}
      >
        {renaming && (
          <form className="ui-stack" onSubmit={renameChat}>
            <ErrorBox error={renameError} />
            <Field title={uiText("Chat name")}>
              <input
                autoFocus
                maxLength={100}
                disabled={renameBusy}
                value={renaming.title}
                onChange={(e) =>
                  setRenaming((v) => ({ ...v, title: e.target.value }))
                }
              />
            </Field>
            <div className="modal-actions">
              <Button
                type="button"
                disabled={renameBusy}
                onClick={() => setRenaming(null)}
              >
                {uiText("Cancel")}
              </Button>
              <Button
                type="submit"
                kind="primary"
                disabled={renameBusy || !renaming.title.trim()}
              >
                {uiText("Save")}
              </Button>
            </div>
          </form>
        )}
      </Modal>
      {preparing?.workflow === "factor_batch_review" && run && (
        <FactorBatch
          key={run.run_id + JSON.stringify(preparing.series_ids)}
          run={run}
          api={api}
          ui={ui}
          canEdit={canEdit}
          autoOpen
          allowedSeriesIds={preparing.series_ids}
          onDismiss={() => setPreparing(null)}
          onManageSources={() => {
            setDataView?.("external");
            navigate?.("data");
          }}
          onManageProfiles={() => navigate?.("customers")}
          onSaved={async (saved, request_id) => {
            await refresh?.();
            const job = await runDataset(saved.id, {
              base_run_id: run.run_id,
              request_id,
            });
            if (!job)
              throw Error(
                "Inputs saved, but calculation could not start. Reopen the reviewed batch.",
              );
          }}
        />
      )}
      {preparing?.workflow === "factor_preparation" && run && (
        <FactorLink
          key={run.run_id + "-" + preparing.profile_series_id}
          run={run}
          api={api}
          ui={ui}
          canEdit={canEdit}
          autoOpen
          initialProfileSeriesId={preparing.profile_series_id}
          onDismiss={() => setPreparing(null)}
          onManageSources={() => {
            setDataView?.("external");
            navigate?.("data");
          }}
          onSaved={async (saved, request_id) => {
            await refresh?.();
            const job = await runDataset(saved.id, {
              base_run_id: run.run_id,
              request_id,
            });
            if (!job)
              throw Error(
                "Inputs saved, but calculation could not start. Retry the reviewed comparison.",
              );
          }}
        />
      )}
      <div
        className="ui-chat-workspace"
        data-history-visible={historyVisible}
        data-history-mobile={historyMobile}
      >
        <ChatHistory
          chats={chats}
          activeHead={turns.at(-1)?.id}
          busy={busy || !!actionBusy || openingChat || managing}
          loading={historyLoading}
          error={historyError}
          nextOffset={nextOffset}
          onMore={loadChats}
          onOpen={openChat}
          onNewChat={newChat}
          onToggle={() => {
            setHistoryVisible(false);
            setHistoryMobile(false);
          }}
          onAction={manageChat}
          folder={chatFolder}
          onFolder={setChatFolder}
          search={chatSearch}
          onSearch={setChatSearch}
        />
        <div className="ui-chat-page">
          <ChatHistoryToggle
            visible={historyVisible}
            mobileOpen={historyMobile}
            onToggle={() => setHistoryVisible((value) => !value)}
            onMobileToggle={() => setHistoryMobile((value) => !value)}
          />
          <ChatSurface
            active={turns.length > 0 || !!pending}
            value={question}
            onChange={setQuestion}
            onSend={send}
            busy={busy}
              readOnly={!!readOnlyChat}
            ready={contextReady && !openingChat && !readOnlyChat}
            tools={tools}
            quickActions={quickActions}
            sourceName={sourceName}
            pending={pending}
            showNewChat={!historyVisible}
            scrollKey={turns}
            onNewChat={newChat}
            newChatDisabled={
              busy || !!actionBusy || openingChat || !contextReady
            }
            error={
              <>
                <ErrorBox error={error} />
                {readOnlyChat && (
                  <Button
                    disabled={managing}
                    onClick={() =>
                      saveChatAction(
                        { id: openedChat.id, head_id: openedChat.head_id },
                        "restore",
                      )
                    }
                  >
                    {uiText("Restore to continue")}
                  </Button>
                )}
              </>
            }
          >
            <AssistantMessages
              turns={turns}
              ui={ui}
              api={api}
              openBatchResult={(id) => openRun(id, "demand")}
              basis={planningBasis(run || { run_settings: dataset?.settings })}
              canEdit={canEdit}
              actionBusy={actionBusy}
              execute={execute}
              openResult={(result) => {
                localStorage.setItem(
                  `demandlab.orders.${result.run_id}`,
                  result.snapshot_id,
                );
                openRun(result.run_id, "demand");
              }}
              useInputs={async (result) => {
                await refresh?.();
                chooseSource("dataset:" + result.dataset_id);
              }}
            />
          </ChatSurface>
        </div>
      </div>
      <Modal
        title={uiText("Choose sales data")}
        open={choosing}
        onClose={() => setChoosing(false)}
      >
        <input
          aria-label={uiText("Find sales data")}
          placeholder={uiText("Find sales data")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="ai-source-list">
          {currentRun &&
            (!search ||
              (
                currentRun.scenario_name ||
                currentRun.dataset_name ||
                uiText("Current forecast")
              )
                .toLowerCase()
                .includes(search.toLowerCase())) && (
              <button
                onClick={() => {
                  chooseSource("");
                  setChoosing(false);
                }}
              >
                <strong>
                  {currentRun.scenario_name ||
                    currentRun.dataset_name ||
                    uiText("Current forecast")}
                </strong>
                <small>{uiText("Current forecast and orders")}</small>
              </button>
            )}
          {datasets
            .filter(
              (d) =>
                !d.scenario_provenance &&
                !d.sources?.operations &&
                d.name.toLowerCase().includes(search.toLowerCase()),
            )
            .map((d) => (
              <button
                key={d.id}
                onClick={() => {
                  chooseSource("dataset:" + d.id);
                  setChoosing(false);
                }}
              >
                <strong>{d.name}</strong>
                <small>
                  {uiText("Sales history")} ·{" "}
                  {d.settings.month_basis === "jalali"
                    ? uiText("Persian")
                    : uiText("Gregorian")}{" "}
                  {uiText("months")}
                </small>
              </button>
            ))}
        </div>
        {canEdit && renderImport && (
          <Button
            onClick={() => {
              setChoosing(false);
              setImporting(true);
            }}
          >
            {uiText("Add sales history")}
          </Button>
        )}
      </Modal>
      <Modal
        title={uiText("Allow AI to review your data?")}
        description={uiText(
          "Your messages and relevant sales, order and factor data, including customer names, will be sent to {{recipient}}. Changes still need your confirmation.",
          { recipient: recipient(permission) },
        )}
        open={!!permission}
        onClose={() => setPermission(null)}
      >
        <div className="demand-actions">
          <Button onClick={() => setPermission(null)}>
            {uiText("Cancel")}
          </Button>
          <Button
            kind="primary"
            onClick={() => {
              setConsent(permission.consent_id);
              send(true);
            }}
          >
            {uiText("Allow & send")}
          </Button>
        </div>
      </Modal>
    </>
  );
}

export function AssistantMessages({
  turns,
  ui,
  canEdit,
  actionBusy,
  execute,
  openResult,
  useInputs,
  basis,
  api,
  openBatchResult,
}) {
  const { Button } = ui;
  return turns.map((turn) => (
    <React.Fragment key={turn.id}>
      <ChatMessage side="user">
        <div className="ui-chat-text" dir="auto">
          {turn.question}
        </div>
      </ChatMessage>
      <ChatMessage>
        <div className="ai-answer">
          <AssistantReply turn={turn} />
          {(turn.actions || []).map((action, index) => {
            const props = {
              action,
              result: turn.results?.[index],
              expired: turn.actions_expired,
              busy: !!actionBusy,
              canEdit,
              onConfirm: () => execute(turn, index),
              ui,
            };
            if (action.kind === "input_mapping")
              return (
                <InputMappingProposal
                  key={index}
                  {...props}
                  onUse={
                    useInputs ? () => useInputs(turn.results[index]) : null
                  }
                />
              );
            if (action.kind === "input_correction")
              return (
                <InputCorrectionProposal
                  key={index}
                  {...props}
                  onConfirm={() =>
                    execute(turn, index, { corrections_confirmed: true })
                  }
                  onUse={
                    useInputs ? () => useInputs(turn.results[index]) : null
                  }
                />
              );
            if (action.kind === "monthly_update")
              return (
                <div className="ai-proposal" key={index}>
                  <h3>{uiText("Update your monthly forecast")}</h3>
                  <p>
                    {uiText(
                      "Review sales history, factors, current orders and changes. Existing results stay unchanged.",
                    )}
                  </p>
                  {turn.actions_expired ? (
                    <p>
                      {uiText(
                        "This proposal expired. Open your saved update from Home, or ask again.",
                      )}
                    </p>
                  ) : (
                    <Button
                      kind="primary"
                      disabled={!canEdit || !!actionBusy}
                      onClick={() => execute(turn, index)}
                    >
                      {turn.results?.[index]
                        ? uiText("Open forecast update")
                        : uiText("Start forecast update")}
                    </Button>
                  )}
                </div>
              );
            if (action.kind === "history_refresh")
              return (
                <div className="ai-proposal" key={index}>
                  <h3>{uiText("Update sales history")}</h3>
                  <p>
                    {uiText(
                      "Upload complete updated history, then review what changed. Orders and existing forecasts stay unchanged.",
                    )}
                  </p>
                  {turn.actions_expired ? (
                    <p>{uiText("This proposal expired. Ask again.")}</p>
                  ) : (
                    <Button
                      kind="primary"
                      disabled={!canEdit || !!actionBusy}
                      onClick={() => execute(turn, index)}
                    >
                      {uiText("Open history upload")}
                    </Button>
                  )}
                </div>
              );
            if (action.kind === "order_scenario")
              return (
                <AssistantComparison
                  key={index}
                  {...props}
                  onOpen={() => openResult?.(turn.results[index])}
                />
              );
            if (action.kind === "order_reuse")
              return (
                <AssistantSavedOrders
                  key={index}
                  {...props}
                  onConfirm={() =>
                    execute(turn, index, { coverage_confirmed: true })
                  }
                  onOpen={() => openResult?.(turn.results[index])}
                />
              );
            if (action.kind === "factor_scenario")
              return (
                <AssistantFactorScenario
                  key={index}
                  {...props}
                  basis={basis}
                  onConfirm={() =>
                    execute(turn, index, { assumptions_confirmed: true })
                  }
                />
              );
            if (action.kind === "factor_batch")
              return (
                <AssistantFactorBatchCard
                  key={index}
                  {...props}
                  basis={basis}
                  api={api}
                  turnId={turn.id}
                  index={index}
                  onOpen={openBatchResult}
                  onConfirm={() =>
                    execute(turn, index, { batch_confirmed: true })
                  }
                />
              );
            if (action.kind === "factor_batch_review")
              return (
                <section className="ai-proposal" key={index}>
                  <h3>{uiText("Review customer/product factors")}</h3>
                  <p>
                    {action.scope
                      .map((s) => s.customer + " · " + s.sku)
                      .join(", ")}
                  </p>
                  {turn.actions_expired ? (
                    <p>{uiText("This proposal expired. Ask again.")}</p>
                  ) : (
                    <Button
                      kind="primary"
                      disabled={!canEdit || !!actionBusy}
                      onClick={() => execute(turn, index)}
                    >
                      {uiText("Review batch")}
                    </Button>
                  )}
                </section>
              );
            if (action.kind === "factor_preparation")
              return (
                <section className="ai-proposal" key={index}>
                  <h3>{uiText("Review forecast factors")}</h3>
                  <p>
                    {action.profile.customer} · {action.profile.target_sku} ·{" "}
                    {action.profile.target_unit}
                  </p>
                  <details className="help-details">
                    <summary>{uiText("Source checks")}</summary>
                    {action.sources.map((s, i) => (
                      <p key={i}>
                        <strong>{s.name}</strong> — {s.note}
                      </p>
                    ))}
                  </details>
                  {turn.actions_expired ? (
                    <p>{uiText("This proposal expired. Ask again.")}</p>
                  ) : (
                    <Button
                      kind="primary"
                      disabled={!canEdit || !!actionBusy}
                      onClick={() => execute(turn, index)}
                    >
                      {uiText("Review sources")}
                    </Button>
                  )}
                </section>
              );
            if (action.kind === "order_import")
              return (
                <div className="ai-proposal" key={index}>
                  <h3>
                    {action.snapshot_id
                      ? uiText("Update customer orders")
                      : uiText("Add customer orders")}
                  </h3>
                  <p>
                    {uiText(
                      "Choose a file, match its columns, then review demand. Nothing is saved until you confirm.",
                    )}
                  </p>
                  {turn.actions_expired ? (
                    <p>
                      {uiText(
                        "This proposal expired. Ask again to refresh it.",
                      )}
                    </p>
                  ) : (
                    <Button
                      kind="primary"
                      disabled={!canEdit || !!actionBusy}
                      onClick={() => execute(turn, index)}
                    >
                      {actionBusy === turn.id + index
                        ? uiText("Opening…")
                        : uiText("Open order upload")}
                    </Button>
                  )}
                </div>
              );
            return (
              <div className="ai-proposal" key={index}>
                <h3>
                  {action.kind === "forecast"
                    ? uiText("Review forecast inputs")
                    : uiText("Prepare this export?")}
                </h3>
                <p>
                  {action.kind === "forecast"
                    ? [
                        action.customer || "All customers",
                        action.months + " months",
                        action.method === "recommended"
                          ? "Compare available methods"
                          : action.method.replace(/^model:/, ""),
                      ].join(" · ")
                    : "All customers · " +
                      (action.mode === "remaining_forecast"
                        ? uiText("Expected demand only")
                        : uiText("Orders + expected demand")) +
                      " · " +
                      action.format.toUpperCase()}
                </p>
                {turn.results?.[index]?.url ? (
                  <a className="btn primary" href={turn.results[index].url}>
                    {uiText("Download draft")}
                  </a>
                ) : turn.results?.[index]?.job ? (
                  <p role="status">
                    {uiText(
                      "Forecast queued. Open the result from the progress panel when ready.",
                    )}
                  </p>
                ) : turn.actions_expired ? (
                  <p>
                    {uiText("This proposal expired. Ask again to refresh it.")}
                  </p>
                ) : (
                  <Button
                    disabled={!canEdit || !!actionBusy}
                    kind="primary"
                    onClick={() => execute(turn, index)}
                  >
                    {actionBusy === turn.id + index
                      ? uiText("Preparing…")
                      : action.kind === "forecast"
                        ? uiText("Review inputs & continue")
                        : uiText("Confirm export")}
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      </ChatMessage>
    </React.Fragment>
  ));
}

function AssistantReply({ turn }) {
  const message = (
    <Markdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        img: () => null,
        a: ({ children }) => <span>{children}</span>,
        table: ({ children }) => (
          <div className="ai-message-table">
            <table>{children}</table>
          </div>
        ),
      }}
    >
      {turn.answer}
    </Markdown>
  );
  // The factor card is the review surface. Keep the full explanation available,
  // without repeating its scope, assumptions and warnings above the same card.
  const factor = (turn.actions || []).some((a) =>
    ["factor_scenario", "factor_batch", "factor_batch_review"].includes(a.kind),
  );
  const correction = (turn.actions || []).some(
    (a) => a.kind === "input_correction",
  );
  const compact = (factor || correction) && turn.answer.length > 240;
  return (
    <div className="ai-message" dir="auto">
      {compact ? (
        <details className="help-details">
          <summary>
            {factor
              ? uiText("Why this scenario?")
              : uiText("Why these changes?")}
          </summary>
          {message}
        </details>
      ) : (
        message
      )}
    </div>
  );
}
