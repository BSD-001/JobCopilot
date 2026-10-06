"use strict";

const $ = (selector) => document.querySelector(selector);
const modes = { resume: "file", jd: "text" };
let activeJob = sessionStorage.getItem("jobcopilot-task");
let deleteTarget = null;
let pollTimer = null;
let routeVersion = 0;
let toastTimer = null;

const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
const lines = (items) => (Array.isArray(items) ? items : []);
const listHTML = (items) => items.length ? `<ul class="detail-list">${items.map((item) => `<li>${escapeHTML(item)}</li>`).join("")}</ul>` : '<p class="muted small">暂无内容，以原材料和实际情况为准。</p>';
const noticeHTML = (message, type = "") => `<div class="notice ${type}">${escapeHTML(message)}</div>`;
const cardHTML = (title, content, index = "", extra = "") => `<section class="card result-card ${extra}"><div class="section-heading"><h2>${title}</h2><span class="section-index">${index}</span></div>${content}</section>`;

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "请求失败，请稍后重试。");
  return data;
}

function toast(message) {
  clearTimeout(toastTimer);
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  toastTimer = setTimeout(() => { $("#toast").hidden = true; }, 3500);
}

function setMode(kind, mode) {
  modes[kind] = mode;
  $(`#${kind}-file-area`).hidden = mode !== "file";
  $(`#${kind}-text-area`).hidden = mode !== "text";
  document.querySelectorAll(`[data-input="${kind}"]`).forEach((button) => {
    const selected = button.dataset.mode === mode;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  $(`#${kind}-error`).textContent = "";
}

function updateFile(kind) {
  const file = $(`#${kind}-file`).files[0];
  const info = $(`#${kind}-file-info`);
  info.hidden = !file;
  info.querySelector("span").textContent = file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB` : "";
  $(`#${kind}-error`).textContent = "";
}

function validateForm() {
  let valid = true;
  $("#api-key-error").textContent = "";
  $("#submit-error").textContent = "";
  if (!$("#api-key").value.trim()) {
    $("#api-key-error").textContent = "请填写 DeepSeek API Key。";
    valid = false;
  }
  for (const kind of ["resume", "jd"]) {
    let message = "";
    const name = kind === "resume" ? "简历" : "岗位描述";
    if (modes[kind] === "text") {
      if (!$(`#${kind}-text`).value.trim()) message = `请粘贴${name}文字。`;
    } else {
      const file = $(`#${kind}-file`).files[0];
      if (!file) message = `请选择${name}文件。`;
      else if (!/\.(txt|md|pdf|docx)$/i.test(file.name)) message = "支持TXT、MD、PDF和DOCX文件。";
      else if (file.size > 200 * 1024 * 1024) message = "单个文件不能超过200MB。";
      else if (!file.size) message = "文件为空，请重新选择。";
    }
    $(`#${kind}-error`).textContent = message;
    valid = valid && !message;
  }
  if (!valid) {
    const error = document.querySelector(".field-error:not(:empty)");
    error?.scrollIntoView({ block: "center", behavior: "smooth" });
    if ($("#api-key-error").textContent) $("#api-key").focus();
  }
  return valid;
}

function updateTaskLink() {
  $("#active-task-link").hidden = !activeJob;
  if (activeJob) $("#active-task-link").href = `#/result/job/${activeJob}/analysis`;
  $("#submit-analysis").disabled = !!activeJob;
  $("#submit-analysis").textContent = activeJob ? "正在分析，请稍候" : "开始分析 →";
}

$("#analysis-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (activeJob || !validateForm()) return;
  const data = new FormData();
  data.set("api_key", $("#api-key").value.trim());
  data.set("allow_skill_boosting", String($("#skill-boost").checked));
  for (const kind of ["resume", "jd"]) {
    data.set(`${kind}_mode`, modes[kind]);
    if (modes[kind] === "file") data.set(`${kind}_file`, $(`#${kind}-file`).files[0]);
    else data.set(`${kind}_text`, $(`#${kind}-text`).value.trim());
  }
  $("#submit-analysis").disabled = true;
  try {
    const result = await request("/api/analyses", { method: "POST", body: data });
    activeJob = result.job_id;
    sessionStorage.setItem("jobcopilot-task", activeJob);
    updateTaskLink();
    location.hash = `#/result/job/${activeJob}/analysis`;
    pollJob(activeJob);
  } catch (error) {
    $("#submit-error").textContent = error.message;
    updateTaskLink();
  }
});

document.querySelectorAll("[data-input]").forEach((button) => button.addEventListener("click", () => setMode(button.dataset.input, button.dataset.mode)));
document.querySelectorAll("[data-remove]").forEach((button) => button.addEventListener("click", () => { $(`#${button.dataset.remove}-file`).value = ""; updateFile(button.dataset.remove); }));
$("#api-key").addEventListener("input", () => { $("#api-key-error").textContent = ""; });
for (const kind of ["resume", "jd"]) {
  $(`#${kind}-text`).addEventListener("input", () => { $(`#${kind}-error`).textContent = ""; });
  const input = $(`#${kind}-file`);
  const zone = input.closest(".dropzone");
  input.addEventListener("change", () => updateFile(kind));
  zone.addEventListener("dragover", (event) => { event.preventDefault(); zone.classList.add("dragging"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragging"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("dragging");
    const dropped = event.dataTransfer.files;
    if (!dropped.length) return;
    const transfer = new DataTransfer();
    transfer.items.add(dropped[0]);
    input.files = transfer.files;
    updateFile(kind);
  });
}
$("#toggle-key").addEventListener("click", () => {
  const show = $("#api-key").type === "password";
  $("#api-key").type = show ? "text" : "password";
  $("#toggle-key").textContent = show ? "隐藏" : "显示";
  $("#toggle-key").setAttribute("aria-label", show ? "隐藏API Key" : "显示API Key");
  $("#toggle-key").setAttribute("aria-pressed", String(show));
});

async function showHistory(version) {
  $("#history-content").innerHTML = '<p class="muted small">正在读取本地记录…</p>';
  try {
    const records = await request("/api/history");
    if (version !== routeVersion) return;
    if (!records.length) {
      $("#history-content").innerHTML = '<section class="card empty-state"><div class="empty-symbol" aria-hidden="true">◷</div><h2>你的第一份分析，从这里开始。</h2><p>完成分析后，报告会自动出现在这里。</p><a href="#/new" class="button primary">新建分析 →</a></section>';
      return;
    }
    $("#history-content").innerHTML = `<section class="card history-table-wrap"><table class="history-table"><thead><tr><th>编号</th><th>目标岗位</th><th>分析时间</th><th>操作</th></tr></thead><tbody>${records.map((record, index) => `<tr><td>${String(index + 1).padStart(2, "0")}</td><td>${escapeHTML(record.job_title)}</td><td>${escapeHTML(record.created_at)}</td><td><div class="row-actions"><a class="text-button" href="#/result/history/${record.record_id}/analysis">查看记录</a><button class="delete-button" data-delete="${record.record_id}" data-title="${escapeHTML(record.job_title)}" aria-label="删除${escapeHTML(record.job_title)}的分析记录">删除</button></div></td></tr>`).join("")}</tbody></table></section>`;
    document.querySelectorAll("[data-delete]").forEach((button) => button.addEventListener("click", () => {
      deleteTarget = button.dataset.delete;
      $("#delete-record-title").textContent = button.dataset.title;
      $("#delete-error").textContent = "";
      $("#delete-dialog").showModal();
    }));
  } catch (error) {
    if (version === routeVersion) $("#history-content").innerHTML = noticeHTML(error.message, "error");
  }
}

$("#confirm-delete").addEventListener("click", async () => {
  if (!deleteTarget) return;
  $("#confirm-delete").disabled = true;
  try {
    await request(`/api/history/${deleteTarget}`, { method: "DELETE" });
    $("#delete-dialog").close();
    toast("记录已永久删除。");
    await showHistory(routeVersion);
  } catch (error) { $("#delete-error").textContent = error.message; }
  finally { $("#confirm-delete").disabled = false; }
});
$("#delete-dialog").addEventListener("close", () => { deleteTarget = null; });

function renderResult(result, source, id, section) {
  const isPrepare = section === "prepare";
  const base = `#/result/${source}/${id}`;
  $("#result-eyebrow").textContent = isPrepare ? "PREPARATION / 学习与下载" : "ANALYSIS / 匹配与优化";
  $("#result-title").textContent = result.job_title || "你的求职分析";
  $("#result-subtitle").textContent = result.created_at ? `${result.created_at} · 已完成分析` : "基于你的简历与岗位要求整理";
  $("#result-back").href = isPrepare ? `${base}/analysis` : "#/history";
  $("#result-back").textContent = isPrepare ? "← 返回匹配分析" : "返回历史";
  $("#result-notice").innerHTML = lines(result.warnings).map((message) => noticeHTML(message, "warning")).join("");
  if (result.status === "running" || result.status === "queued") {
    $("#result-subtitle").textContent = "正在整理你的求职准备方案";
    $("#result-content").innerHTML = '<section class="card progress-card"><div class="progress-heading"><span class="spinner" aria-hidden="true"></span><h2>正在分析，请稍候</h2></div><p class="muted small">耗时取决于材料长度与模型响应。你可以查看历史，或留在这里等待。</p><p class="stage-text"></p></section>';
    $(".stage-text").textContent = result.stage || "准备分析";
    return;
  }
  if (result.status === "failed") {
    $("#result-subtitle").textContent = "分析未完成，原输入仍保留在新建分析页";
    $("#result-content").innerHTML = noticeHTML(result.error || "分析失败，请稍后重试。", "error") + '<a class="button primary" href="#/new">返回输入并重试 →</a>';
    return;
  }
  const analysis = result.analysis_data;
  if (!analysis || !Object.keys(analysis).length) {
    $("#result-content").innerHTML = isPrepare ? downloadsHTML(result, source, id) : noticeHTML("这是一份旧版历史记录，保留原完整报告和下载文件。") + cardHTML("完整分析报告", `<div class="legacy-report">${result.report_html || escapeHTML(result.report_text)}</div>`) + `<div class="result-actions"><a class="button primary" href="${base}/prepare">查看下载 →</a></div>`;
    return;
  }
  if (isPrepare) {
    const plan = analysis.learning_plan || {};
    const weeks = lines(plan.weeks).map((week) => `<article class="week"><span class="week-label">第 ${escapeHTML(week.week)} 周</span><div><h3>${escapeHTML(week.goal)}</h3>${listHTML(lines(week.tasks))}<p class="deliverable">交付成果 · ${escapeHTML(week.deliverable)}</p></div></article>`).join("");
    $("#result-content").innerHTML = cardHTML("30天学习计划", (weeks || '<p class="muted small">暂无学习计划。</p>') + (plan.summary ? `<p class="body-copy">${escapeHTML(plan.summary)}</p>` : ""), "01") + cardHTML("线上投递招呼语", `<p class="body-copy" id="greeting-text">${escapeHTML(analysis.hr_greeting)}</p><div class="result-actions"><span class="small muted">发送前，请核对岗位和个人经历。</span><button type="button" class="button secondary" id="copy-greeting">复制招呼语</button></div>`, "02") + downloadsHTML(result, source, id);
    $("#copy-greeting").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(analysis.hr_greeting || ""); toast("招呼语已复制。"); }
      catch { toast("复制失败，请选中文字手动复制。"); }
    });
    return;
  }
  const match = analysis.match || {};
  const score = Number.isFinite(Number(match.score)) ? Math.max(0, Math.min(100, Number(match.score))) : "—";
  const matchBody = `<div class="score-layout"><div><div class="score">${score}<span> / 100</span></div><p class="score-caption">岗位匹配参考评分</p></div><p class="score-reason">${escapeHTML(match.reason)}</p></div><div class="match-grid"><div><h3>匹配优势</h3>${listHTML(lines(match.matched_points))}</div><div><h3>待补齐差距</h3>${listHTML(lines(match.missing_points))}</div></div>`;
  const optimized = analysis.resume_optimization || {};
  const advice = lines(optimized.optimized_projects).map((project) => `<article class="optimized-item"><h3>${escapeHTML(project.title)}</h3><p class="body-copy">${escapeHTML(project.content)}</p></article>`).join("");
  const boosts = lines(analysis.tailored_resume?.skill_boosts);
  const skillBody = boosts.length ? `<div class="optimized-item"><h3>待补齐技能 · 投递前核对</h3>${listHTML(boosts.map((item) => `${item.skill}：${item.suggested_wording}`))}</div>` : "";
  const pending = lines(analysis.pending_items);
  const questions = lines(analysis.interview?.questions).map((item, index) => `<details class="question"><summary>${String(index + 1).padStart(2, "0")} · ${escapeHTML(item.question)}</summary><p class="body-copy">${escapeHTML(item.answer)}</p><p class="focus-label">考察重点 · ${escapeHTML(item.focus)}</p></details>`).join("");
  $("#result-content").innerHTML = cardHTML("岗位匹配分析", matchBody, "01") + cardHTML("简历优化建议", (advice || '<p class="muted small">暂无优化建议。</p>') + skillBody, "02") + (pending.length ? cardHTML("待补充的信息", '<p class="small muted">以下信息只列入报告，不写入下载简历。请按实际情况补齐。</p>' + listHTML(pending), "", "pending") : "") + cardHTML("面试题与参考回答", questions || '<p class="muted small">暂无面试题。</p>', "03") + `<div class="result-actions"><span class="small muted">下一步，安排学习计划并准备投递材料。</span><a class="button primary" href="${base}/prepare">查看学习计划与下载 →</a></div>`;
}

function downloadsHTML(result, source, id) {
  const prefix = source === "history" ? `/api/history/${id}` : `/api/analyses/${id}`;
  return `<section class="card"><div class="section-heading"><h2>准备好你的投递材料</h2></div><p class="muted small">报告与简历均按目标岗位命名。下载后请核对事实与格式。</p><div class="result-actions download-actions"><a class="button secondary" href="${prefix}/downloads/report">下载完整Markdown报告 ↓</a>${result.has_tailored_resume ? `<a class="button primary" href="${prefix}/downloads/resume">下载岗位定制简历 ↓</a>` : ""}</div>${result.has_tailored_resume ? "" : '<p class="small muted" style="margin-top:20px;margin-bottom:0">本次未生成定制简历。上传DOCX简历后可保留原模板生成定制版。</p>'}</section>`;
}

async function pollJob(id) {
  clearTimeout(pollTimer);
  try {
    const result = await request(`/api/analyses/${id}`);
    if (location.hash.startsWith(`#/result/job/${id}/`)) renderResult(result, "job", id, location.hash.endsWith("/prepare") ? "prepare" : "analysis");
    if (result.status === "completed" || result.status === "failed") {
      if (activeJob === id) { activeJob = null; sessionStorage.removeItem("jobcopilot-task"); updateTaskLink(); }
      if (!location.hash.startsWith(`#/result/job/${id}/`)) toast(result.status === "completed" ? "分析已完成，可在历史记录中查看。" : "分析失败，请返回新建分析页重试。");
      return;
    }
  } catch (error) {
    if (/不存在|重启/.test(error.message)) {
      activeJob = null;
      sessionStorage.removeItem("jobcopilot-task");
      updateTaskLink();
      if (location.hash.startsWith(`#/result/job/${id}/`)) $("#result-content").innerHTML = noticeHTML(error.message, "error") + '<a class="button secondary" href="#/new">返回新建分析</a>';
      return;
    }
    if (location.hash.startsWith(`#/result/job/${id}/`)) $("#result-notice").innerHTML = noticeHTML("暂时无法连接本地服务，正在重新连接…", "warning");
  }
  if (activeJob === id) pollTimer = setTimeout(() => pollJob(id), 2000);
}

async function route() {
  const version = ++routeVersion;
  const parts = (location.hash || "#/home").replace(/^#\/?/, "").split("/");
  const page = parts[0];
  const home = page === "home" || !["new", "history", "result"].includes(page);
  $("#home-view").hidden = !home;
  $("#workspace").hidden = home;
  for (const view of ["new", "history", "result"]) $(`#${view}-view`).hidden = page !== view;
  document.querySelectorAll("[data-nav]").forEach((link) => {
    const selected = link.dataset.nav === (page === "result" ? (parts[1] === "history" ? "history" : "new") : page);
    link.classList.toggle("active", selected);
    if (selected) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
  updateTaskLink();
  window.scrollTo({ top: 0 });
  if (page === "history") await showHistory(version);
  if (page === "result") {
    const [source, id, section = "analysis"] = parts.slice(1);
    if (!["history", "job"].includes(source) || !id || !/^[a-zA-Z0-9-]+$/.test(id)) { location.hash = "#/new"; return; }
    $("#result-content").innerHTML = '<p class="muted small">正在读取分析结果…</p>';
    try {
      const result = await request(source === "history" ? `/api/history/${id}` : `/api/analyses/${id}`);
      if (version !== routeVersion) return;
      renderResult(result, source, id, section);
    } catch (error) {
      if (version === routeVersion) {
        $("#result-title").textContent = "无法读取这次分析";
        $("#result-subtitle").textContent = "";
        $("#result-notice").innerHTML = "";
        $("#result-back").href = "#/history";
        $("#result-back").textContent = "返回历史";
        $("#result-content").innerHTML = noticeHTML(error.message, "error");
      }
    }
  }
}

window.addEventListener("hashchange", route);
route();
if (activeJob) pollJob(activeJob);
