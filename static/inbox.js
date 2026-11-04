const REPLY_PREFIX = /^re:/i;

const mail = {
  folder: "inbox",
  messages: [],
  counts: { inbox: "", sent: "" },
  openUid: null,
  status: null,
  loading: false,
  composing: null,
};

const mailParts = {
  folders: document.getElementById("inbox-folder"),
  today: document.getElementById("inbox-today"),
  refresh: document.getElementById("inbox-refresh"),
  write: document.getElementById("inbox-write"),
  setup: document.getElementById("inbox-setup"),
  setupState: document.getElementById("inbox-setup-state"),
  panes: document.getElementById("inbox-panes"),
  list: document.getElementById("inbox-list"),
  empty: document.getElementById("inbox-empty"),
  reader: document.getElementById("inbox-reader"),
  dialog: document.getElementById("composer"),
  form: document.getElementById("composer-form"),
  title: document.getElementById("composer-title"),
  close: document.getElementById("composer-close"),
  to: document.getElementById("composer-to"),
  subject: document.getElementById("composer-subject"),
  body: document.getElementById("composer-body"),
  note: document.getElementById("composer-note"),
  send: document.getElementById("composer-send"),
  status: document.getElementById("composer-status"),
};

function personLabel(person) {
  if (!person) return "";
  return person.name || person.address;
}

function setupNote(status) {
  const missing = [];
  if (!status.address) missing.push("no address under Mailbox on the Settings page");
  if (!status.has_password) missing.push("MAILBOX_PASSWORD is empty in .env");
  return missing.length ? "Still missing: " + missing.join(", and ") + "." : "";
}

function todayLabel(sent, limit) {
  return sent + " of " + limit + " sent today";
}

async function loadInbox(quietly) {
  if (mail.loading) return;
  mail.loading = true;
  mailParts.refresh.disabled = true;
  try {
    mail.status = await requestJson("/api/mailbox");
    const ready = mail.status.ready;
    mailParts.setup.hidden = ready;
    mailParts.panes.hidden = !ready;
    mailParts.write.disabled = !ready;
    if (!ready) {
      mailParts.setupState.textContent = setupNote(mail.status);
      mailParts.today.textContent = "";
      markFilter(mailParts.folders, mail.folder, () => "");
      return;
    }
    if (!quietly) {
      mailParts.list.replaceChildren(element("li", "inbox-loading", "Opening " + mail.status.address + "…"));
      mailParts.empty.hidden = true;
    }
    const data = await requestJson("/api/mailbox/messages?folder=" + mail.folder);
    mail.messages = data.messages;
    mail.counts[mail.folder] = mail.folder === "inbox"
      ? String(data.messages.filter((item) => item.unread).length || "")
      : "";
    mailParts.today.textContent = todayLabel(data.sent_today, data.daily_limit);
    renderInbox();
  } catch (error) {
    mailParts.list.replaceChildren();
    mailParts.empty.hidden = false;
    mailParts.empty.textContent = error.message;
  } finally {
    mail.loading = false;
    mailParts.refresh.disabled = false;
  }
}

function leadTag(lead) {
  return element("span", "lead-tag", lead.name || lead.place_id);
}

function inboxItem(item) {
  const entry = element("li");
  const button = element("button", "inbox-item" + (item.unread ? " unread" : "") + (item.uid === mail.openUid ? " open" : ""));
  button.type = "button";
  const top = element("span", "inbox-item-top");
  const who = mail.folder === "sent"
    ? "To " + item.to.map(personLabel).join(", ")
    : personLabel(item.from);
  top.append(element("strong", "inbox-who", who || "(nobody)"), element("span", "inbox-when", whenLabel(item.date)));
  button.append(top, element("span", "inbox-subject", item.subject || "(no subject)"));
  if (item.lead) button.append(leadTag(item.lead));
  button.addEventListener("click", () => openMail(item.uid));
  entry.append(button);
  return entry;
}

function renderInbox() {
  markFilter(mailParts.folders, mail.folder, (name) => mail.counts[name]);
  mailParts.list.replaceChildren(...mail.messages.map(inboxItem));
  mailParts.empty.hidden = mail.messages.length > 0;
  mailParts.empty.textContent = mail.folder === "inbox" ? "Nothing in the inbox yet." : "Nothing sent from this mailbox yet.";
}

async function openMail(uid) {
  mail.openUid = uid;
  mailParts.reader.replaceChildren(element("p", "empty", "Opening the message…"));
  if (window.matchMedia("(max-width: 900px)").matches) mailParts.reader.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const message = await requestJson("/api/mailbox/messages/" + mail.folder + "/" + uid);
    if (mail.openUid !== uid) return;
    const listed = mail.messages.find((item) => item.uid === uid);
    if (listed && listed.unread) {
      listed.unread = false;
      mail.counts.inbox = String(mail.messages.filter((item) => item.unread).length || "");
    }
    renderInbox();
    renderReader(message);
  } catch (error) {
    mailParts.reader.replaceChildren(element("p", "empty error", error.message));
  }
}

function fullDate(text) {
  const parsed = parseStamp(text);
  if (!parsed) return "";
  return parsed.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function quoted(message) {
  const lines = message.text.split("\n").map((line) => "> " + line);
  const when = fullDate(message.date);
  return "\n\n" + (when ? "On " + when + ", " : "") + personLabel(message.from) + " wrote:\n" + lines.join("\n");
}

function replyTo(message) {
  const subject = REPLY_PREFIX.test(message.subject) ? message.subject : "Re: " + message.subject;
  openComposer({
    title: "Reply",
    to: message.folder === "sent" ? (message.to[0] || {}).address : message.from.address,
    subject,
    body: quoted(message),
    reply: { message_id: message.message_id, references: message.references },
  });
}

function answerPicker(message) {
  const line = element("label", "reader-answer");
  const select = element("select");
  REPLY_CHOICES.forEach(([value, label]) => {
    const option = element("option", "", value ? label : "Log their answer…");
    option.value = value;
    option.disabled = value === "";
    select.append(option);
  });
  select.value = "";
  const note = element("span", "hint");
  select.addEventListener("change", async () => {
    select.disabled = true;
    try {
      await requestJson("/api/sites/response", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ place_id: message.lead.place_id, response: select.value }),
      });
      note.textContent = "Logged for " + message.lead.name + ".";
    } catch (error) {
      note.textContent = error.message;
      select.value = "";
    }
    select.disabled = false;
  });
  line.append(select, note);
  return line;
}

function renderReader(message) {
  const head = element("div", "reader-head");
  head.append(element("h2", "", message.subject || "(no subject)"));
  const facts = element("p", "reader-facts");
  facts.append(
    element("strong", "", personLabel(message.from)),
    element("span", "", " <" + message.from.address + ">"),
    element("span", "reader-to", " to " + message.to.map((person) => person.address).join(", ")),
    element("span", "reader-when", " · " + whenLabel(message.date))
  );
  head.append(facts);
  const actions = element("div", "reader-actions");
  const reply = element("button", "", "Reply");
  reply.type = "button";
  reply.addEventListener("click", () => replyTo(message));
  actions.append(reply);
  if (message.lead) {
    actions.append(leadTag(message.lead));
    if (message.folder === "inbox") actions.append(answerPicker(message));
  }
  const body = element("div", "reader-text", message.text || "(This message has no text.)");
  const parts = [head, actions, body];
  if (message.attachments.length) {
    parts.push(element("p", "hint reader-files", "Attachments, open them in your mailbox: " + message.attachments.join(", ")));
  }
  mailParts.reader.replaceChildren(...parts);
}

function openComposer(draft) {
  mail.composing = draft;
  mailParts.title.textContent = draft.title || "New message";
  mailParts.to.value = draft.to || "";
  mailParts.subject.value = draft.subject || "";
  mailParts.body.value = draft.body || "";
  mailParts.to.readOnly = Boolean(draft.reply);
  const notes = [];
  if (mail.status && mail.status.address) notes.push("From " + mail.status.address + ".");
  const business = draft.name || "this business";
  if (draft.place_id && !draft.reply && !draft.followUp) notes.push("Sending it logs it as sent to " + business + ", so the follow-up reminder starts.");
  if (draft.place_id && !draft.reply && draft.followUp) notes.push("Sending it counts as the follow-up to " + business + ", so no further reminder comes.");
  if (draft.reply) notes.push("A reply is never held back by the daily limit.");
  mailParts.note.textContent = notes.join(" ");
  say(mailParts.status, "");
  mailParts.send.disabled = false;
  mailParts.dialog.showModal();
  (draft.to ? mailParts.body : mailParts.to).focus();
  if (draft.reply) mailParts.body.setSelectionRange(0, 0);
}

async function ensureMailStatus() {
  if (!mail.status) mail.status = await requestJson("/api/mailbox");
  return mail.status;
}

async function sendComposed(event) {
  event.preventDefault();
  const draft = mail.composing || {};
  mailParts.send.disabled = true;
  say(mailParts.status, "Sending…");
  try {
    await requestJson("/api/mailbox/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to: mailParts.to.value.trim(),
        subject: mailParts.subject.value.trim(),
        body: mailParts.body.value,
        place_id: draft.place_id || "",
        name: draft.name || "",
        reply: draft.reply || null,
      }),
    });
    mailParts.dialog.close();
    mail.composing = null;
    if (draft.onSent) draft.onSent();
    if (board.view === "inbox") loadInbox(true);
  } catch (error) {
    say(mailParts.status, error.message, true);
    mailParts.send.disabled = false;
  }
}

async function composeForSite(site) {
  try {
    const status = await ensureMailStatus();
    if (!status.ready) {
      goTo("inbox");
      return;
    }
  } catch (error) {
    return;
  }
  const first = !site.sent.some((item) => item.channel === "email");
  openComposer({
    title: first ? "Email " + site.name : "Write to " + site.name,
    to: site.email_to,
    subject: first && site.email_draft ? site.email_draft.subject : "",
    body: first && site.email_draft ? site.email_draft.body : "",
    place_id: site.place_id,
    name: site.name,
    followUp: !first,
    onSent: () => {
      loadSites();
      refreshNav();
    },
  });
}

mailParts.folders.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button || button.dataset.filter === mail.folder) return;
  mail.folder = button.dataset.filter;
  mail.openUid = null;
  mail.messages = [];
  mailParts.reader.replaceChildren(element("p", "empty", "Pick a message to read it."));
  renderInbox();
  loadInbox();
});
mailParts.refresh.addEventListener("click", () => loadInbox());
mailParts.write.addEventListener("click", () => openComposer({ title: "New message" }));
mailParts.close.addEventListener("click", () => mailParts.dialog.close());
mailParts.form.addEventListener("submit", sendComposed);
