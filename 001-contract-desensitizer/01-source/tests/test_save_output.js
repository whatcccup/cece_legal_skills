#!/usr/bin/env node
/*
 * 回归测试：复核页「确认并脱敏」之后的保存行为（前端 JS，浏览器里真实执行的那段）。
 *
 * 用户反馈「没有保存 mapping」，所以这里把 contract_app_ui.py 里那段 JS 原样切出来，
 * 在 Node 的沙箱里跑，断言：
 *   A. 未选文件夹（默认）→ 自动下载 docx + mapping.json 两个文件
 *   B. 已选文件夹 → 两个文件直接写进该文件夹，且不再触发浏览器下载
 *   C. 取消勾选 mapping → 只保存 docx 一个
 *   D. 写文件夹失败 → 自动退化为浏览器下载，不能丢文件
 *
 * 用法：node tests/test_save_output.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.dirname(__dirname);
const ui = fs.readFileSync(path.join(ROOT, "contract_app_ui.py"), "utf8");

const BEGIN = "// ============================================================ 输出保存";
const END = "function renderSaved";
const i0 = ui.indexOf(BEGIN);
const i1 = ui.indexOf(END);
if (i0 < 0 || i1 < 0 || i1 <= i0) {
  console.log("  [FAIL] 无法从 contract_app_ui.py 切出保存逻辑（标记是否被改名？）");
  process.exit(1);
}
const CODE = ui.slice(i0, i1);

const fails = [];
function check(name, cond, detail) {
  if (!cond) fails.push(name);
  console.log(`  [${cond ? "PASS" : "FAIL"}] ${name}${detail ? "  — " + detail : ""}`);
}

function makeEnv(opts) {
  opts = opts || {};
  const downloads = [];      // 触发浏览器下载的文件名/URL
  const written = [];        // 写进文件夹的文件名
  const listeners = [];      // 注册的事件
  const ctx = { downloads, written, listeners };

  const mkEl = (id) => ({
    id, style: {}, className: "", textContent: "", dataset: {},
    classList: { add() {}, remove() {} },
    checked: id === "optJson" ? opts.jsonChecked !== false : true,
    disabled: false, files: [], parentNode: null,
    setAttribute() {}, appendChild() {}, removeChild() {},
    addEventListener(t, f) { listeners.push({ id, t, f }); },
    querySelector() { return mkEl(); }, click() {},
  });
  const els = {};

  const sandbox = {
    console,
    setTimeout, clearTimeout, Promise, Set, Map, JSON, Math, String, Number,
    esc: (s) => String(s == null ? "" : s),
    fetch: async (url) => {
      if (opts.fetchFails && opts.fetchFails.indexOf(url) >= 0) return { ok: false, status: 500 };
      return { ok: true, status: 200, blob: async () => ({ size: 1234, _url: url }) };
    },
    document: {
      getElementById: (id) => (els[id] = els[id] || mkEl(id)),
      createElement: (tag) => {
        const e = mkEl(tag);
        // 真实浏览器里 browserDownload 会 appendChild 再 click()；
        // 这里只在 click 时记一次，避免重复计数
        e.click = () => downloads.push({ url: e.href });
        return e;
      },
      body: { appendChild() {}, removeChild() {} },
    },
    window: opts.noFSA ? {} : { showDirectoryPicker: async () => mkEl("dir") },
  };
  sandbox.window.showDirectoryPicker = opts.noFSA ? undefined : async () => {
    if (opts.pickerCancels) throw new Error("AbortError");
    return mkDirHandle(opts, written);
  };
  ctx.sandbox = sandbox;
  ctx.els = els;
  ctx.mkDirHandle = mkDirHandle;
  return ctx;
}

function mkDirHandle(opts, written) {
  return {
    name: opts.folderName || "C01_测试材料",
    queryPermission: async () => "granted",
    requestPermission: async () => "granted",
    getFileHandle: async (name) => {
      if (opts.writeFails && opts.writeFails.indexOf(name) >= 0) throw new Error("NotAllowedError");
      return {
        createWritable: async () => ({
          write: async () => {},
          close: async () => { written.push(name); },
        }),
      };
    },
  };
}

async function loadEnv(opts) {
  const ctx = makeEnv(opts);
  vm.createContext(ctx.sandbox);
  vm.runInContext(CODE, ctx.sandbox, { filename: "review-save.js" });
  return ctx;
}

const RESULT = {
  output_url: "/download/SID/%E5%90%88%E5%90%8C_%E8%84%B1%E6%95%8F.docx",
  output_name: "合同_脱敏.docx",
  mapping_url: "/download/SID/%E5%90%88%E5%90%8C_%E8%84%B1%E6%95%8F.docx.mapping.json",
  mapping_name: "合同_脱敏.docx.mapping.json",
};

async function main() {
  console.log("== A. 默认：未选文件夹 → 两个文件都下载 ==");
  {
    const c = await loadEnv({});
    const sv = await c.sandbox.saveOutputs(RESULT);
    const names = c.downloads.map((d) => d.name || decodeURIComponent(String(d.url).split("/").pop()));
    check("自动下载 2 个文件", c.downloads.length === 2, `实际 ${c.downloads.length}`);
    check("包含 docx 与 mapping.json",
      names.some((n) => n.endsWith(".docx") && !n.endsWith(".json")) && names.some((n) => n.endsWith(".json")),
      names.join(" / "));
    check("返回结果标记为浏览器下载模式", sv && sv.folder === "" && sv.files.length === 2);
  }

  console.log("\n== B. 已选文件夹 → 直接写入，不再弹下载 ==");
  {
    const c = await loadEnv({ folderName: "C01" });
    // 模拟用户点了「选择保存文件夹」
    const pick = (c.listeners || []).find((x) => x.id === "pickDir" && x.t === "click");
    check("选择文件夹按钮已绑定", !!pick);
    await pick.f({});
    const sv = await c.sandbox.saveOutputs(RESULT);
    check("两个文件都写进文件夹", c.written.length === 2, c.written.join(" / "));
    check("不再触发浏览器下载", c.downloads.length === 0, `实际 ${c.downloads.length}`);
    check("结果里带文件夹名", sv.folder === "C01", sv.folder);
  }

  console.log("\n== C. 取消勾选 mapping → 只保存 docx ==");
  {
    const c = await loadEnv({ jsonChecked: false });
    await c.sandbox.saveOutputs(RESULT);
    const names = c.downloads.map((d) => d.name || decodeURIComponent(String(d.url).split("/").pop()));
    check("只下载 1 个文件", c.downloads.length === 1, names.join(" / "));
    check("下载的是 docx", names[0].endsWith(".docx") && !names[0].endsWith(".json"), names[0]);
  }

  console.log("\n== D. 写文件夹失败 → 退化为下载，不丢文件 ==");
  {
    const c = await loadEnv({ writeFails: ["合同_脱敏.docx.mapping.json"] });
    const pick = c.listeners.find((x) => x.id === "pickDir" && x.t === "click");
    await pick.f({});
    const sv = await c.sandbox.saveOutputs(RESULT);
    check("失败的那个已改为下载", c.downloads.length === 1,
      c.downloads.map((d) => d.name || d.url).join(" / "));
    check("成功的那个仍写进文件夹", c.written.length === 1, c.written.join(" / "));
    check("结果标记 degraded", sv.degraded === true);
  }

  console.log("\n== E. 浏览器不支持文件夹 API → 按钮禁用 + 仍能都下载 ==");
  {
    const c = await loadEnv({ noFSA: true });
    check("按钮被禁用", c.els["pickDir"].disabled === true);
    await c.sandbox.saveOutputs(RESULT);
    check("仍然下载两个文件", c.downloads.length === 2, `实际 ${c.downloads.length}`);
  }

  console.log("\n== F. 用户在选文件夹时取消 → 不影响后续下载 ==");
  {
    const c = await loadEnv({ pickerCancels: true });
    const pick = c.listeners.find((x) => x.id === "pickDir" && x.t === "click");
    await pick.f({});
    await c.sandbox.saveOutputs(RESULT);
    check("取消选择后仍下载 2 个文件", c.downloads.length === 2, `实际 ${c.downloads.length}`);
  }

  console.log();
  if (fails.length) {
    console.log(`✘ 失败 ${fails.length} 项：` + fails.join("；"));
    process.exit(1);
  }
  console.log("✔ 全部通过");
}

main().catch((e) => {
  console.error("测试脚本异常：", e);
  process.exit(1);
});
