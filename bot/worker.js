// Sleep Factory Telegram bot — Cloudflare Worker (free plan).
// Instant menus + edits of the repo's data/ files; heavy jobs are dispatched to GitHub Actions.
// Secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GH_TOKEN, WEBHOOK_SECRET. Var: GH_REPO ("owner/repo").

const CATS = {
  topics_favor: "Topics that work",
  topics_avoid: "Topics to avoid",
  title_rules: "Title rules",
  description_rules: "Description rules",
  thumbnail_rules: "Thumbnail rules",
  intro_rules: "Intro / hook rules",
  script_rules: "Script rules",
};
const ICON = { private: "🔒", public: "🌍" };

export default {
  async fetch(req, env) {
    if (req.method !== "POST") return new Response("sleep-factory bot ok");
    if (req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) return new Response("no", { status: 403 });
    const upd = await req.json();
    try {
      await handle(upd, env);
    } catch (e) {
      const chat = upd.message?.chat?.id || upd.callback_query?.message?.chat?.id;
      if (String(chat) === String(env.TELEGRAM_CHAT_ID)) await tg(env, "sendMessage", { chat_id: chat, text: "⚠️ " + String(e).slice(0, 300) });
    }
    return new Response("ok");
  },
};

// ---------- helpers ----------
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const kb = (rows) => ({ inline_keyboard: rows.map((r) => r.map(([text, data]) => ({ text, callback_data: data }))) });
const back = (to = "m:main") => [["⬅️ Back", to], ["🏠 Menu", "m:main"]];

async function tg(env, method, body) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  return r.json();
}

async function say(env, text, rows, edit) {
  const body = { chat_id: env.TELEGRAM_CHAT_ID, text: text.slice(0, 4000), parse_mode: "HTML", disable_web_page_preview: true };
  if (rows) body.reply_markup = kb(rows);
  if (edit) {
    const r = await tg(env, "editMessageText", { ...body, message_id: edit });
    if (r.ok || String(r.description || "").includes("not modified")) return r;
  }
  return tg(env, "sendMessage", body);
}

async function gh(env, path, opts = {}) {
  const r = await fetch(`https://api.github.com/repos/${env.GH_REPO}${path}`, {
    ...opts,
    headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "sleep-factory-bot", ...(opts.headers || {}) },
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`GitHub ${r.status}: ${(await r.text()).slice(0, 150)}`);
  return r.status === 204 ? {} : r.json();
}

const b64d = (s) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
const b64e = (s) => { const b = new TextEncoder().encode(s); let x = ""; for (const c of b) x += String.fromCharCode(c); return btoa(x); };

async function readJson(env, path, dflt) {
  const f = await gh(env, `/contents/${path}`);
  if (!f) return { data: dflt, sha: null };
  return { data: JSON.parse(b64d(f.content)), sha: f.sha };
}

async function writeJson(env, path, data, sha, msg) {
  await gh(env, `/contents/${path}`, {
    method: "PUT",
    body: JSON.stringify({ message: `${msg} [skip ci]`, content: b64e(JSON.stringify(data, null, 2) + "\n"), ...(sha ? { sha } : {}) }),
  });
}

async function dispatch(env, event_type, client_payload = {}) {
  await gh(env, "/dispatches", { method: "POST", body: JSON.stringify({ event_type, client_payload }) });
}

const pending = {
  get: async (env) => (await readJson(env, "data/bot_pending.json", {})).data,
  set: async (env, p) => { const cur = await readJson(env, "data/bot_pending.json", {}); await writeJson(env, "data/bot_pending.json", p, cur.sha, "bot: pending"); },
};

// ---------- router ----------
async function handle(upd, env) {
  const cq = upd.callback_query;
  const msg = upd.message;
  const chat = String(cq?.message?.chat?.id ?? msg?.chat?.id ?? "");
  if (chat !== String(env.TELEGRAM_CHAT_ID)) {
    if (msg) await tg(env, "sendMessage", { chat_id: chat, text: `This is a private bot. Your chat id: ${chat}` });
    return;
  }
  if (cq) {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
    return onButton(env, cq.data, cq.message.message_id);
  }
  if (msg) return onMessage(env, msg);
}

async function onMessage(env, msg) {
  const text = (msg.text || "").trim();
  if (["/start", "/menu", "menu"].includes(text.toLowerCase())) { await pending.set(env, {}); return mainMenu(env); }
  if (text === "/cancel") { await pending.set(env, {}); return say(env, "Cancelled.", [[["🏠 Menu", "m:main"]]]); }
  const p = await pending.get(env);
  const photo = msg.photo?.length ? msg.photo[msg.photo.length - 1].file_id : msg.document?.mime_type?.startsWith("image/") ? msg.document.file_id : null;

  if (photo) {
    if (p.action !== "thumb") return say(env, "I got an image, but no video is waiting for one. Open 🎬 Videos → a video → 🖼 Send thumbnail first.", [[["🎬 Videos", "m:videos"]]]);
    await pending.set(env, {});
    await dispatch(env, "bot_action", { action: "thumbnail", vid: p.vid, file_id: photo, concept: p.concept });
    return say(env, "⏳ Got it! Setting the thumbnail and making the video <b>public</b>… I'll confirm here in ~1 minute.");
  }
  if (!text) return;
  if (p.action === "edit") {
    await pending.set(env, {});
    await dispatch(env, "bot_action", { action: "edit", vid: p.vid, field: p.field, value: text });
    return say(env, `⏳ Updating the ${p.field} on YouTube… I'll confirm in ~1 minute.`);
  }
  if (p.action === "add_topic") {
    await pending.set(env, {});
    const [title, ...rest] = text.split("|");
    const topic = rest.join("|").trim() || title.trim();
    const q = await readJson(env, "data/topic_queue.json", []);
    const list = [{ title: title.trim().slice(0, 80), topic, source: "manual" }, ...q.data].slice(0, 5);
    await writeJson(env, "data/topic_queue.json", list, q.sha, "bot: add topic");
    return topicsMenu(env, null, "✅ Added to the top of the queue (queue keeps max 5).");
  }
  if (p.action === "add_rule") {
    await pending.set(env, {});
    const pb = await readJson(env, "data/playbook.json", {});
    pb.data[p.key] = [...(pb.data[p.key] || []), text.slice(0, 200)];
    await writeJson(env, "data/playbook.json", pb.data, pb.sha, "bot: add rule");
    return playbookMenu(env, null, "✅ Rule added. Every next video follows it.");
  }
  if (p.action === "set_chapters") {
    const n = parseInt(text, 10);
    await pending.set(env, {});
    if (!(n >= 2 && n <= 24)) return say(env, "Send a number between 2 and 24.", [[["⚙️ Settings", "m:set"]]]);
    return saveSetting(env, "chapters", n, null);
  }
  return mainMenu(env);
}

async function onButton(env, d, mid) {
  const [k, a, b] = d.split(":");
  switch (k) {
    case "m":
      if (a === "main") return mainMenu(env, mid);
      if (a === "dash") return dashboard(env, mid);
      if (a === "videos") return videosMenu(env, mid);
      if (a === "topics") return topicsMenu(env, mid);
      if (a === "pb") return playbookMenu(env, mid);
      if (a === "set") return settingsMenu(env, mid);
      if (a === "runs") return runsMenu(env, mid);
      if (a === "help") return help(env, mid);
      return;
    case "v": return videoView(env, a, mid);
    case "vp": return videoPrompts(env, a);
    case "vd": return videoDescription(env, a);
    case "vr": return videoReport(env, a);
    case "vt": return say(env, "Which concept did you use for the thumbnail?", [[["Concept 1", `thumb:${a}:1`], ["Concept 2", `thumb:${a}:2`], ["Concept 3", `thumb:${a}:3`]], [["Other / my own idea", `thumb:${a}:own`]], back(`v:${a}`)], mid);
    case "thumb":
      await pending.set(env, { action: "thumb", vid: a, concept: b });
      return say(env, `🖼 Now send me the thumbnail image (concept ${b}).\nTip: send it as a <b>file</b> to keep full quality. /cancel to stop.`);
    case "pub": return say(env, "Publish <b>without</b> a custom thumbnail? YouTube will pick a frame (weaker clicks).", [[["✅ Yes, publish", `pubok:${a}`], ["❌ No", `v:${a}`]]], mid);
    case "pubok":
      await dispatch(env, "bot_action", { action: "publish", vid: a });
      return say(env, "⏳ Publishing… I'll confirm in ~1 minute.", null, mid);
    case "ve":
      await pending.set(env, { action: "edit", vid: a, field: b });
      return say(env, `✏️ Send the new <b>${b}</b> as a message. /cancel to stop.`);
    case "t": return topicAction(env, a, b, mid);
    case "p": return playbookAction(env, a, b, d, mid);
    case "s": return settingAction(env, a, b, mid);
    case "run":
      if (a === "render") { await dispatch(env, "render_now", {}); return say(env, "▶️ Rendering a video now (2-4 h). I'll message you when it's uploaded.", [[["🩺 Runs", "m:runs"], ["🏠 Menu", "m:main"]]], mid); }
      if (a === "analyze") { await dispatch(env, "analyze_now", {}); return say(env, "🔍 Analyzing every public video now (even if under 72h). Report in a few minutes.", [[["🏠 Menu", "m:main"]]], mid); }
  }
}

// ---------- screens ----------
async function mainMenu(env, mid) {
  return say(env, "🌙 <b>Sleep Factory</b>\nWhat do you want to see or change?", [
    [["📊 Dashboard", "m:dash"], ["🎬 Videos", "m:videos"]],
    [["🗂 Topics", "m:topics"], ["🧠 Playbook", "m:pb"]],
    [["⚙️ Settings", "m:set"], ["🩺 Runs", "m:runs"]],
    [["▶️ Render now", "run:render"], ["🔍 Analyze now", "run:analyze"]],
    [["❓ How it works", "m:help"]],
  ], mid);
}

async function help(env, mid) {
  return say(env,
    "<b>How it works</b>\n\n" +
    "1. Every night at 02:07 (Tunisia) a video is rendered and uploaded <b>private</b>.\n" +
    "2. You get its title, description and 3 thumbnail prompts here.\n" +
    "3. Make the thumbnail, tap the concept you used, send the image → the video goes <b>public</b>.\n" +
    "4. 72h after going public, the analyzer reads YouTube Analytics, explains what worked/failed, " +
    "updates the 🧠 Playbook and re-plans the next 5 topics.\n" +
    "5. If anything breaks, the 🩺 watcher tells you why and retries when it can.\n\n" +
    "You can edit topics, playbook rules, titles, descriptions and settings anytime from this menu.",
    [back()], mid);
}

async function index(env) {
  return (await readJson(env, "data/videos_index.json", [])).data;
}

async function dashboard(env, mid) {
  const [idx, pb, q, st] = await Promise.all([
    index(env), readJson(env, "data/playbook.json", {}), readJson(env, "data/topic_queue.json", []), readJson(env, "data/settings.json", {}),
  ]);
  const waiting = idx.filter((v) => v.status === "private").length;
  const pub = idx.filter((v) => v.status === "public");
  const analyzed = idx.filter((v) => v.analyzed);
  const best = [...analyzed].sort((x, y) => (y.views || 0) - (x.views || 0))[0];
  const runs = await gh(env, "/actions/runs?per_page=1&event=schedule").catch(() => null);
  const last = runs?.workflow_runs?.[0];
  return say(env,
    "📊 <b>Dashboard</b>\n\n" +
    `🎬 Videos: ${idx.length} total · 🔒 ${waiting} waiting for thumbnail · 🌍 ${pub.length} public · 📈 ${analyzed.length} analyzed\n` +
    `🧠 Playbook v${pb.data.version || 0} (${pb.data.videos_analyzed || 0} videos learned from)\n` +
    `🗂 Planned topics: ${q.data.length}/5 — next: ${esc(q.data[0]?.title || "auto")}\n` +
    `⚙️ ${st.data.chapters || 18} chapters · nightly ${st.data.paused ? "⏸ PAUSED" : "▶️ on at 02:07"}\n` +
    (best ? `🏆 Best so far: ${esc(best.title)} (${best.views} views, CTR ${best.ctr ?? "?"}%)\n` : "") +
    (last ? `\nLast nightly run: ${last.conclusion || last.status} · ${last.created_at.slice(0, 16).replace("T", " ")} UTC` : ""),
    [[["🎬 Videos", "m:videos"], ["🩺 Runs", "m:runs"]], back()], mid);
}

async function videosMenu(env, mid) {
  const idx = (await index(env)).slice(-12).reverse();
  if (!idx.length) return say(env, "No videos yet. The first one arrives after tonight's run (or tap ▶️ Render now).", [back()], mid);
  const rows = idx.map((v) => [[`${ICON[v.status] || "•"}${v.analyzed ? "📈" : ""} ${v.title.slice(0, 48)}`, `v:${v.id}`]]);
  return say(env, "🎬 <b>Videos</b> (newest first)\n🔒 waiting for thumbnail · 🌍 public · 📈 analyzed", [...rows, back()], mid);
}

async function videoView(env, vid, mid) {
  const v = (await readJson(env, `data/videos/${vid}.json`, null)).data;
  if (!v) return say(env, "Video not found.", [back("m:videos")], mid);
  const st = v.stats || {};
  const rows = [
    [["🎨 Thumbnail prompts", `vp:${vid}`], ["📝 Description", `vd:${vid}`]],
    [["✏️ Edit title", `ve:${vid}:title`], ["✏️ Edit description", `ve:${vid}:description`]],
  ];
  if (v.status === "private") rows.unshift([["🖼 Send thumbnail → publish", `vt:${vid}`]], [["🚀 Publish without thumbnail", `pub:${vid}`]]);
  if (v.diagnosis) rows.push([["📈 72h report", `vr:${vid}`]]);
  rows.push(back("m:videos"));
  return say(env,
    `${ICON[v.status] || ""} <b>${esc(v.title)}</b>\nhttps://youtu.be/${vid}\n\n` +
    `Topic: ${esc(v.topic)}\nCreated: ${v.created?.slice(0, 10)} · ${(v.duration_sec / 3600).toFixed(1)} h · playbook v${v.playbook_version}\n` +
    (v.published ? `Public since: ${v.published.slice(0, 16).replace("T", " ")} UTC · thumbnail concept ${v.thumb_concept}\n` : "Status: waiting for your thumbnail\n") +
    (v.stats ? `\n📈 Views ${st.views} · CTR ${st.ctr_pct}% · avg viewed ${st.avg_view_pct}% · watch ${st.watch_hours} h\nVerdict: <b>${esc(v.diagnosis?.verdict)}</b>` : ""),
    rows, mid);
}

async function videoPrompts(env, vid) {
  const v = (await readJson(env, `data/videos/${vid}.json`, null)).data;
  const parts = String(v?.thumbnail_brief || "").split("## Concept ").slice(1);
  if (!parts.length) return say(env, "No prompts stored for this video.");
  for (const [i, c] of parts.entries()) {
    const seg = c.split("```");
    const head = c.split("\n")[0].split(":").slice(1).join(":").trim();
    await say(env, `🎨 <b>Concept ${i + 1}</b> — ${esc(head)}\n\n<code>${esc((seg[1] || c).trim())}</code>\n\n${esc((seg[2] || "").trim())}`);
  }
  return say(env, "Tap the concept you used once your image is ready:", [[["Concept 1", `thumb:${vid}:1`], ["Concept 2", `thumb:${vid}:2`], ["Concept 3", `thumb:${vid}:3`]], back(`v:${vid}`)]);
}

async function videoDescription(env, vid) {
  const v = (await readJson(env, `data/videos/${vid}.json`, null)).data;
  await say(env, `📝 <b>Description</b>\n\n${esc(v?.description || "(none)")}`);
  return say(env, "Options:", [[["✏️ Edit description", `ve:${vid}:description`]], back(`v:${vid}`)]);
}

async function videoReport(env, vid) {
  const v = (await readJson(env, `data/videos/${vid}.json`, null)).data;
  const d = v?.diagnosis || {}, s = v?.stats || {}, r = s.retention || {};
  const keep = r.still_watching_pct ? Object.entries(r.still_watching_pct).map(([k, x]) => `${k}: ${x}%`).join(" · ") : "n/a";
  const drops = (r.biggest_drops || []).map((x) => `${x.at} (−${x.lost_pct}%${x.chapter ? `, ${esc(x.chapter)}` : ""})`).join("\n") || "n/a";
  return say(env,
    `📈 <b>72h report</b> — ${esc(v.title)}\nVerdict: <b>${esc(d.verdict)}</b>\n\n` +
    `Impressions ${s.impressions} · CTR ${s.ctr_pct}% · views ${s.views} · avg viewed ${s.avg_view_pct}% (${s.avg_view_minutes} min) · watch ${s.watch_hours} h · subs +${s.subs_gained}\n\n` +
    `<b>Still watching</b>: ${keep}\n<b>Biggest drop-offs</b>:\n${drops}\n\n` +
    `<b>Clicks</b>: ${esc(d.click_problem)}\n<b>Retention</b>: ${esc(d.retention_problem)}\n\n${esc(d.summary_for_owner)}`,
    [back(`v:${vid}`)]);
}

async function topicsMenu(env, mid, note) {
  const q = (await readJson(env, "data/topic_queue.json", [])).data;
  const lines = q.map((t, i) => `${i + 1}. <b>${esc(t.title)}</b>${t.source === "manual" ? " ✍️" : ""}\n    ${esc(t.topic).slice(0, 160)}`);
  const rows = q.map((t, i) => [[`⬆️ ${i + 1}`, `t:up:${i}`], [`🗑 ${i + 1}`, `t:del:${i}`]]);
  rows.push([["➕ Add my topic", "t:add"], ["🔄 Re-plan all", "t:replan"]], back());
  return say(env, `${note ? note + "\n\n" : ""}🗂 <b>Next topics</b> (max 5, top = next)\n✍️ = added by you\n\n${lines.join("\n\n") || "(empty: the planner will fill it tonight)"}`, rows, mid);
}

async function topicAction(env, a, b, mid) {
  if (a === "add") {
    await pending.set(env, { action: "add_topic" });
    return say(env, "➕ Send the topic as:\n<code>Title | what to cover (place, era, 5-6 everyday things)</code>\nor just a title. /cancel to stop.");
  }
  if (a === "replan") { await dispatch(env, "bot_action", { action: "replan" }); return say(env, "🔄 Re-planning all 5 topics with the current playbook… ~1-2 min.", [[["🏠 Menu", "m:main"]]], mid); }
  const q = await readJson(env, "data/topic_queue.json", []);
  const i = parseInt(b, 10);
  if (a === "del") q.data.splice(i, 1);
  if (a === "up" && i > 0) [q.data[i - 1], q.data[i]] = [q.data[i], q.data[i - 1]];
  await writeJson(env, "data/topic_queue.json", q.data, q.sha, `bot: topic ${a}`);
  return topicsMenu(env, mid, a === "del" ? "🗑 Removed. The planner refills to 5 after the next video." : "⬆️ Moved up.");
}

async function playbookMenu(env, mid, note) {
  const pb = (await readJson(env, "data/playbook.json", {})).data;
  const body = Object.entries(CATS).map(([k, name]) => `<b>${name}</b>\n${(pb[k] || []).map((r, i) => `  ${i + 1}. ${esc(r)}`).join("\n") || "  —"}`).join("\n\n");
  return say(env,
    `${note ? note + "\n\n" : ""}🧠 <b>Playbook v${pb.version || 0}</b> · learned from ${pb.videos_analyzed || 0} videos\n${esc(pb.notes || "")}\n\n${body}`,
    [[["➕ Add rule", "p:add"], ["🗑 Remove rule", "p:del"]], [["♻️ Reset playbook", "p:reset"]], back()], mid);
}

async function playbookAction(env, a, b, d, mid) {
  if (a === "add") return say(env, "Which category?", [...Object.entries(CATS).map(([k, n]) => [[n, `p:addk:${k}`]]), back("m:pb")], mid);
  if (a === "addk") { await pending.set(env, { action: "add_rule", key: b }); return say(env, `➕ Send the new rule for <b>${CATS[b]}</b>. /cancel to stop.`); }
  if (a === "reset") return say(env, "Reset the playbook to empty? The system forgets all lessons.", [[["✅ Yes, reset", "p:resetok"], ["❌ No", "m:pb"]]], mid);
  const pb = await readJson(env, "data/playbook.json", {});
  if (a === "resetok") {
    for (const k of Object.keys(CATS)) pb.data[k] = [];
    pb.data.notes = "Reset by owner.";
    await writeJson(env, "data/playbook.json", pb.data, pb.sha, "bot: reset playbook");
    return playbookMenu(env, mid, "♻️ Playbook reset.");
  }
  if (a === "del") {
    const rows = [];
    for (const [k, n] of Object.entries(CATS)) (pb.data[k] || []).forEach((r, i) => rows.push([[`🗑 ${n.split(" ")[0]} ${i + 1}: ${r.slice(0, 40)}`, `p:dk:${k}.${i}`]]));
    return say(env, rows.length ? "Tap a rule to remove it:" : "No rules to remove.", [...rows, back("m:pb")], mid);
  }
  if (a === "dk") {
    const [k, i] = b.split(".");
    (pb.data[k] || []).splice(parseInt(i, 10), 1);
    await writeJson(env, "data/playbook.json", pb.data, pb.sha, "bot: remove rule");
    return playbookMenu(env, mid, "🗑 Rule removed.");
  }
}

async function settingsMenu(env, mid, note) {
  const st = { chapters: 18, paused: false, ...(await readJson(env, "data/settings.json", {})).data };
  return say(env,
    `${note ? note + "\n\n" : ""}⚙️ <b>Settings</b>\n\n📏 Chapters per video: <b>${st.chapters}</b> (≈${Math.round(st.chapters * 11.5)} min)\n` +
    `🌙 Nightly run at 02:07 Tunisia: <b>${st.paused ? "⏸ paused" : "▶️ on"}</b>\n🎙 Voice: ${esc(st.voice || "en-US-AndrewMultilingualNeural")}\n\n` +
    "Keys & tokens (YouTube, AI, images) are stored as GitHub secrets: github.com → repo → Settings → Secrets → Actions.",
    [[["➖ chapters", "s:ch:-"], ["➕ chapters", "s:ch:+"], ["✍️ type number", "s:ch:type"]],
     [[st.paused ? "▶️ Resume nightly" : "⏸ Pause nightly", "s:pause:x"]], back()], mid);
}

async function saveSetting(env, key, value, mid) {
  const st = await readJson(env, "data/settings.json", {});
  st.data = { chapters: 18, paused: false, ...st.data, [key]: value };
  await writeJson(env, "data/settings.json", st.data, st.sha, `bot: ${key}`);
  return settingsMenu(env, mid, "✅ Saved.");
}

async function settingAction(env, a, b, mid) {
  const st = { chapters: 18, paused: false, ...(await readJson(env, "data/settings.json", {})).data };
  if (a === "ch" && b === "type") { await pending.set(env, { action: "set_chapters" }); return say(env, "Send the number of chapters (2-24)."); }
  if (a === "ch") return saveSetting(env, "chapters", Math.max(2, Math.min(24, st.chapters + (b === "+" ? 1 : -1))), mid);
  if (a === "pause") return saveSetting(env, "paused", !st.paused, mid);
}

async function runsMenu(env, mid) {
  const r = await gh(env, "/actions/runs?per_page=8");
  const icon = (x) => x.status !== "completed" ? "⏳" : x.conclusion === "success" ? "✅" : x.conclusion === "skipped" ? "⏭" : "❌";
  const lines = (r?.workflow_runs || []).map((x) => `${icon(x)} <a href="${x.html_url}">${esc(x.name)}</a> · ${x.created_at.slice(5, 16).replace("T", " ")} UTC`);
  return say(env, `🩺 <b>Recent runs</b>\n\n${lines.join("\n") || "none"}`, [[["🔄 Refresh", "m:runs"]], back()], mid);
}
