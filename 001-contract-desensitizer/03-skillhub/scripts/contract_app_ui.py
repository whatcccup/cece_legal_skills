"""合同脱敏 / 还原 —— Web UI 模板层（纯标准库，无第三方依赖）。

把所有 HTML / CSS / JS 模板集中在这里，与 HTTP 处理逻辑（contract_app_server.py）
解耦，这样调整视觉设计时不必触碰服务端行为。

约定：
- 所有模板都是「纯字符串 + __TOKEN__ 占位」，使用 str.replace 注入，
  不使用 str.format / f-string —— 避免与 CSS/JS 里的大量花括号打架。
"""
from __future__ import annotations

import html as _html
import json
from typing import Any, Dict

APP_TITLE = "合同脱敏 / 还原"
APP_SUBTITLE = "Contract Redactor"
APP_VERSION = "1.1.0"

esc = _html.escape


# =============================================================== 图标 =========

BRAND_MARK = """<svg viewBox="0 0 24 24" width="21" height="21" fill="none" aria-hidden="true">
<path d="M12 2.4 4.7 5.2v5.4c0 4.7 3.05 9.05 7.3 10.9 4.25-1.85 7.3-6.2 7.3-10.9V5.2L12 2.4Z" fill="#fff" fill-opacity=".22"/>
<path d="M12 2.4 4.7 5.2v5.4c0 4.7 3.05 9.05 7.3 10.9 4.25-1.85 7.3-6.2 7.3-10.9V5.2L12 2.4Z" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>
<path d="m8.7 11.9 2.35 2.35 4.4-4.55" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<defs><linearGradient id="g" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
<stop stop-color="#3b5bff"/><stop offset="1" stop-color="#7a4dff"/></linearGradient></defs>
<rect width="32" height="32" rx="9" fill="url(#g)"/>
<path d="M16 5.5 8.6 8.4v6.1c0 5.2 3.4 10 7.4 12 4-2 7.4-6.8 7.4-12V8.4L16 5.5Z" fill="#fff" fill-opacity=".2"/>
<path d="M16 5.5 8.6 8.4v6.1c0 5.2 3.4 10 7.4 12 4-2 7.4-6.8 7.4-12V8.4L16 5.5Z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round" fill="none"/>
<path d="m12.2 15.9 2.6 2.6 5-5.2" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>"""

HERO_ART = """<svg class="hero-art" viewBox="0 0 360 210" fill="none" aria-hidden="true">
<defs>
<linearGradient id="ha-page" x1="0" y1="0" x2="0" y2="1">
<stop stop-color="#ffffff"/><stop offset="1" stop-color="#f4f6fd"/></linearGradient>
<linearGradient id="ha-acc" x1="0" y1="0" x2="1" y2="1">
<stop stop-color="#3b5bff"/><stop offset="1" stop-color="#7a4dff"/></linearGradient>
</defs>
<rect x="18" y="16" width="140" height="180" rx="14" fill="url(#ha-page)" stroke="#dfe4f2"/>
<rect x="36" y="38" width="72" height="9" rx="4.5" fill="#c9d2e6"/>
<rect x="36" y="60" width="104" height="7" rx="3.5" fill="#e4e9f5"/>
<rect x="36" y="76" width="88" height="7" rx="3.5" fill="#e4e9f5"/>
<rect x="36" y="100" width="60" height="12" rx="6" fill="#fcdada"/>
<rect x="100" y="100" width="40" height="12" rx="6" fill="#e4e9f5"/>
<rect x="36" y="126" width="104" height="7" rx="3.5" fill="#e4e9f5"/>
<rect x="36" y="142" width="44" height="12" rx="6" fill="#fde8c8"/>
<rect x="84" y="142" width="56" height="12" rx="6" fill="#e4e9f5"/>
<rect x="36" y="168" width="96" height="7" rx="3.5" fill="#e4e9f5"/>
<rect x="196" y="16" width="146" height="180" rx="14" fill="url(#ha-page)" stroke="#cfd8f7"/>
<rect x="214" y="38" width="72" height="9" rx="4.5" fill="#c9d2e6"/>
<rect x="214" y="60" width="110" height="7" rx="3.5" fill="#e4e9f5"/>
<rect x="214" y="76" width="92" height="7" rx="3.5" fill="#e4e9f5"/>
<rect x="214" y="100" width="62" height="12" rx="6" fill="#dbe3ff"/>
<rect x="280" y="100" width="40" height="12" rx="6" fill="#e4e9f5"/>
<rect x="214" y="126" width="110" height="7" rx="3.5" fill="#e4e9f5"/>
<rect x="214" y="142" width="46" height="12" rx="6" fill="#dbe3ff"/>
<rect x="264" y="142" width="56" height="12" rx="6" fill="#e4e9f5"/>
<rect x="214" y="168" width="98" height="7" rx="3.5" fill="#e4e9f5"/>
<circle cx="180" cy="106" r="20" fill="url(#ha-acc)"/>
<path d="M172 106h14m0 0-5.5-5.5M186 106l-5.5 5.5" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


# =============================================================== CSS ==========

CSS = r"""
:root{
  --bg:#eef1f8;
  --surface:#ffffff;
  --surface-2:#f7f9fd;
  --line:#e2e7f1;
  --line-soft:#eef1f7;
  --ink:#0d1626;
  --ink-2:#39465a;
  --sub:#6b7a90;
  --faint:#9aa7bb;
  --acc:#3355ff;
  --acc-d:#2441d8;
  --acc-2:#7a4dff;
  --acc-soft:#eef2ff;
  --acc-line:#c9d5ff;
  --ok:#0f9d58;
  --ok-soft:#eefaf2;
  --warn:#c47d0a;
  --warn-soft:#fff8e8;
  --danger:#d92d20;
  --danger-soft:#fef3f2;
  --hi:#e5484d;
  --md:#dd9207;
  --lo:#0d9bc0;
  --r:16px;
  --r-sm:11px;
  --sh-1:0 1px 2px rgba(15,26,50,.05), 0 2px 8px rgba(15,26,50,.04);
  --sh-2:0 8px 28px rgba(15,26,50,.09), 0 2px 6px rgba(15,26,50,.04);
  --sh-3:0 24px 60px rgba(15,26,50,.14);
  --ff:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,"Segoe UI",sans-serif;
  --fm:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;min-height:100vh;color:var(--ink);font-family:var(--ff);
  font-size:14.5px;line-height:1.72;background:var(--bg);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}
body::before{
  content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;
  background:
    radial-gradient(920px 520px at 6% -10%, #dde5ff 0%, rgba(221,229,255,0) 62%),
    radial-gradient(780px 520px at 98% 2%, #e9dcff 0%, rgba(233,220,255,0) 58%),
    linear-gradient(180deg,#f4f6fc 0%, #e9edf7 100%);
}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
code{font-family:var(--fm);font-size:.86em;background:#f2f5fb;border:1px solid var(--line-soft);
  padding:1px 6px;border-radius:6px;color:var(--ink-2)}
.grow{flex:1}
.muted{color:var(--sub)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}

/* ------------------------------------------------------------- 顶栏 */
.topbar{position:sticky;top:0;z-index:60;
  background:rgba(255,255,255,.80);backdrop-filter:saturate(180%) blur(14px);
  -webkit-backdrop-filter:saturate(180%) blur(14px);
  border-bottom:1px solid rgba(226,231,241,.85)}
.topbar-in{max-width:1260px;margin:0 auto;padding:11px 26px;display:flex;align-items:center;gap:16px}
.brand{display:flex;align-items:center;gap:11px;color:var(--ink);text-decoration:none}
.brand:hover{text-decoration:none}
.brand .mark{width:37px;height:37px;border-radius:12px;display:grid;place-items:center;flex:none;
  background:linear-gradient(135deg,#3b5bff,#7a4dff);box-shadow:0 7px 18px rgba(59,91,255,.30)}
.brand-txt{display:flex;flex-direction:column;line-height:1.22}
.brand-txt b{font-size:15px;font-weight:650;letter-spacing:-.015em}
.brand-txt i{font-style:normal;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint)}
.topbar-mid{display:flex;align-items:center;gap:8px;min-width:0;overflow:hidden}
.topbar-act{margin-left:auto;display:flex;align-items:center;gap:9px}
.live{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--sub);
  background:#fff;border:1px solid var(--line);padding:5px 12px;border-radius:999px}
.live .pulse{width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 0 rgba(15,157,88,.5);
  animation:pulse 2.4s ease-out infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(15,157,88,.45)}70%{box-shadow:0 0 0 7px rgba(15,157,88,0)}100%{box-shadow:0 0 0 0 rgba(15,157,88,0)}}

/* ------------------------------------------------------------- 布局 */
.shell{max-width:1260px;margin:0 auto;padding:26px}
.page-head{display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:18px}
h1{font-size:24px;line-height:1.3;font-weight:680;letter-spacing:-.022em;margin:0 0 4px}
h2{font-size:15px;font-weight:640;letter-spacing:-.01em;margin:0 0 12px;display:flex;align-items:center;gap:9px}
h3{font-size:13px;font-weight:600;margin:0}
.step-n{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;font-size:12px;font-weight:700;
  background:var(--acc-soft);color:var(--acc);flex:none}
.meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:var(--sub);font-size:12.5px}
.pill{display:inline-flex;align-items:center;gap:6px;background:#fff;border:1px solid var(--line);
  color:var(--ink-2);border-radius:999px;padding:3px 11px;font-size:12px;max-width:420px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pill.ghost{background:var(--surface-2);color:var(--sub)}
.pill.acc{background:var(--acc-soft);border-color:var(--acc-line);color:var(--acc)}

.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
  padding:20px 22px;margin-bottom:18px;box-shadow:var(--sh-1)}
.card.flat{box-shadow:none;background:var(--surface-2)}
.card.tight{padding:14px 16px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:18px;align-items:start}
.grid > .col{min-width:0}
.stack > *:last-child{margin-bottom:0}

/* ------------------------------------------------------------- 英雄区 */
.hero{position:relative;overflow:hidden;border-radius:20px;padding:30px 34px;margin-bottom:20px;
  background:linear-gradient(120deg,#151d38 0%,#22306b 46%,#3a2a72 100%);
  color:#f6f8ff;box-shadow:var(--sh-2);display:flex;align-items:center;gap:24px}
.hero::after{content:"";position:absolute;right:-70px;top:-110px;width:330px;height:330px;border-radius:50%;
  background:radial-gradient(circle at 30% 30%,rgba(122,77,255,.62),rgba(122,77,255,0) 68%)}
.hero-copy{position:relative;z-index:1;flex:1;min-width:0}
.eyebrow{display:inline-flex;align-items:center;gap:7px;font-size:11.5px;letter-spacing:.06em;
  text-transform:uppercase;color:#b9c6ff;background:rgba(255,255,255,.10);
  border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:4px 12px;margin-bottom:14px}
.hero h1{font-size:27px;color:#fff;margin:0 0 10px}
.hero p{margin:0;color:#c3ccea;font-size:14px;max-width:640px}
.hero-art{position:relative;z-index:1;width:290px;flex:none;filter:drop-shadow(0 18px 30px rgba(0,0,0,.28))}

/* ------------------------------------------------------------- 按钮 */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;
  font-family:inherit;font-size:13.5px;font-weight:560;line-height:1;color:var(--ink-2);
  background:#fff;border:1px solid var(--line);border-radius:var(--r-sm);
  padding:11px 17px;cursor:pointer;white-space:nowrap;
  transition:transform .12s ease,border-color .15s ease,box-shadow .15s ease,background .15s ease,color .15s ease}
.btn:hover{border-color:#c8d3ea;color:var(--ink);box-shadow:var(--sh-1);text-decoration:none}
.btn:active{transform:translateY(1px)}
.btn.primary{background:linear-gradient(135deg,#3b5bff,#5a48f5);color:#fff;border-color:transparent;
  box-shadow:0 6px 18px rgba(59,91,255,.30)}
.btn.primary:hover{color:#fff;box-shadow:0 10px 26px rgba(59,91,255,.38);border-color:transparent}
.btn.ok{background:linear-gradient(135deg,#12a860,#0f9d58);color:#fff;border-color:transparent;
  box-shadow:0 6px 18px rgba(15,157,88,.26)}
.btn.ok:hover{color:#fff;border-color:transparent}
.btn.warn{background:#fff;color:var(--warn);border-color:#f0dcae}
.btn.warn:hover{background:var(--warn-soft);color:var(--warn)}
.btn.ghost{background:var(--surface-2)}
.btn.sm{padding:8px 13px;font-size:12.5px;border-radius:9px}
.btn.lg{padding:15px 30px;font-size:15px;border-radius:13px;font-weight:640}
.btn.block{width:100%}
.btn:disabled,.btn[disabled]{opacity:.5;cursor:not-allowed;box-shadow:none;transform:none}

/* ------------------------------------------------------------- 模式选择 */
.modes{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.mode{position:relative;border:1.5px solid var(--line);border-radius:14px;padding:18px 18px 16px;
  background:#fff;cursor:pointer;transition:border-color .16s,box-shadow .16s,transform .16s}
.mode:hover{border-color:#c2cff2;box-shadow:var(--sh-1)}
.mode .ic{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;font-size:19px;
  background:var(--surface-2);border:1px solid var(--line-soft);margin-bottom:11px}
.mode .name{font-size:15px;font-weight:650;margin-bottom:5px;display:flex;align-items:center;gap:8px}
.mode .desc{color:var(--sub);font-size:12.8px;line-height:1.68}
.mode.active{border-color:var(--acc);background:linear-gradient(180deg,#f7f9ff,#fff);
  box-shadow:0 0 0 4px rgba(51,85,255,.11),var(--sh-2)}
.mode.active .ic{background:var(--acc-soft);border-color:var(--acc-line)}
.mode.active::after{content:"✓";position:absolute;top:13px;right:14px;width:20px;height:20px;border-radius:50%;
  background:var(--acc);color:#fff;font-size:12px;font-weight:700;display:grid;place-items:center}

/* ------------------------------------------------------------- 上传区 */
.drop{position:relative;border:2px dashed #ccd6ea;border-radius:16px;background:var(--surface-2);
  padding:38px 24px;text-align:center;cursor:pointer;transition:.16s}
.drop:hover{border-color:var(--acc);background:var(--acc-soft)}
.drop.drag{border-color:var(--acc);background:var(--acc-soft);box-shadow:inset 0 0 0 4px rgba(51,85,255,.08)}
.drop input[type=file]{display:none}
.drop .ic{width:52px;height:52px;margin:0 auto 12px;border-radius:16px;display:grid;place-items:center;
  background:#fff;border:1px solid var(--line);box-shadow:var(--sh-1);font-size:23px}
.drop .t{font-size:15.5px;font-weight:620;margin:0 0 4px}
.drop .h{color:var(--sub);font-size:12.6px;margin:0}
.picked{display:flex;align-items:center;gap:10px;margin-top:14px;padding:11px 14px;border-radius:12px;
  background:var(--ok-soft);border:1px solid #c7ecd7;color:#116b3f;font-size:13px}
.picked .x{margin-left:auto;cursor:pointer;color:#5b8f74;font-size:15px;line-height:1}

/* ------------------------------------------------------------- 文本 / 列表 */
.olist{margin:0;padding:0;list-style:none;display:grid;gap:11px}
.olist li{display:flex;gap:10px;font-size:13px;color:var(--ink-2);line-height:1.7}
.olist .n{width:20px;height:20px;flex:none;border-radius:6px;background:var(--acc-soft);color:var(--acc);
  font-size:11.5px;font-weight:700;display:grid;place-items:center;margin-top:2px}
.tlist{margin:0;padding:0;list-style:none;display:grid;gap:8px}
.tlist li{position:relative;padding-left:18px;font-size:12.8px;color:var(--sub);line-height:1.68}
.tlist li::before{content:"";position:absolute;left:4px;top:9px;width:5px;height:5px;border-radius:50%;background:#bfcbe4}
.kv{display:grid;gap:9px}
.kv .row{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:12.8px}
.kv .row b{font-weight:600;color:var(--ink)}
.stat{font-size:12.5px;color:var(--sub)}
.stat b{color:var(--acc);font-weight:640}

/* ------------------------------------------------------------- 提示条 */
.alert{padding:12px 15px;border-radius:12px;font-size:13px;margin:0 0 14px;
  display:flex;gap:9px;align-items:flex-start;line-height:1.66}
.alert.ok{background:var(--ok-soft);color:#11603a;border:1px solid #c7ecd7}
.alert.warn{background:var(--warn-soft);color:#7a4d05;border:1px solid #f0dcae}
.alert.err{background:var(--danger-soft);color:#8f1d15;border:1px solid #f7d3cf}
.alert.info{background:var(--acc-soft);color:#233a9e;border:1px solid var(--acc-line)}
.alert .i{flex:none;font-size:14px;line-height:1.5}

/* ------------------------------------------------------------- 对比视图 */
.toolbar{position:sticky;top:59px;z-index:40;background:rgba(255,255,255,.94);
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border:1px solid var(--line);border-radius:var(--r);padding:13px 16px;margin-bottom:16px;box-shadow:var(--sh-1)}
.tb-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.tb-label{font-size:12.5px;color:var(--sub);font-weight:600}
.seg{display:inline-flex;background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:3px}
.seg-btn{border:0;background:transparent;font-family:inherit;font-size:12.8px;font-weight:560;color:var(--sub);
  padding:6px 14px;border-radius:8px;cursor:pointer;transition:.14s}
.seg-btn:hover{color:var(--ink)}
.seg-btn.on{background:#fff;color:var(--ink);box-shadow:var(--sh-1)}
.seg-btn.on[data-sev=high]{color:#fff;background:var(--hi);box-shadow:none}
.seg-btn.on[data-sev=medium]{color:#fff;background:var(--md);box-shadow:none}
.seg-btn.on[data-sev=low]{color:#fff;background:var(--lo);box-shadow:none}
.seg-btn.on[data-sev=all]{color:#fff;background:#3a4763;box-shadow:none}
.types-wrap{margin-top:12px;padding-top:12px;border-top:1px dashed var(--line);display:none}
.types-wrap.open{display:block}
.cat{display:flex;align-items:center;gap:9px;font-size:12px;color:var(--faint);font-weight:600;
  letter-spacing:.04em;text-transform:uppercase;margin:14px 0 8px}
.cat::after{content:"";flex:1;height:1px;background:var(--line-soft)}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);border-radius:999px;
  padding:5px 13px;font-size:12.8px;cursor:pointer;user-select:none;background:#fff;
  color:var(--ink-2);transition:.14s}
.chip:hover{border-color:#c8d3ea;box-shadow:var(--sh-1)}
.chip .dot{width:8px;height:8px;border-radius:50%;flex:none}
.chip .cnt{font-family:var(--fm);font-size:11px;color:var(--faint)}
.chip input{display:none}
.chip.on[data-sev=high]{border-color:#f5b5b7;background:#fff5f5;color:#a3272b}
.chip.on[data-sev=medium]{border-color:#f0dcae;background:#fffaef;color:#7d5607}
.chip.on[data-sev=low]{border-color:#b6e2ef;background:#f1fbfe;color:#0a6a83}
.chip.off{opacity:.42;background:var(--surface-2)}
.chip.off .cnt{text-decoration:line-through}

.compare{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
.pane{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
  box-shadow:var(--sh-1);overflow:hidden;display:flex;flex-direction:column}
.pane-head{display:flex;align-items:center;gap:9px;padding:12px 16px;font-size:12.5px;font-weight:600;
  color:var(--sub);background:var(--surface-2);border-bottom:1px solid var(--line-soft);
  position:sticky;top:0;z-index:2}
.pane-head .sw{width:9px;height:9px;border-radius:3px;background:#c9d2e6}
.pane-head .sw.alt{background:linear-gradient(135deg,#3b5bff,#7a4dff)}
.pane-body{padding:16px 18px;height:calc(100vh - 320px);min-height:340px;overflow:auto;
  white-space:pre-wrap;word-break:break-word;font-size:13.2px;line-height:1.95;scroll-behavior:auto}
.pane-body::-webkit-scrollbar{width:11px}
.pane-body::-webkit-scrollbar-thumb{background:#ccd5e6;border-radius:8px;border:3px solid #fff}
.pane-body::-webkit-scrollbar-thumb:hover{background:#b3c0d8}
.doc .blk{margin-top:13px}
.doc .blk:first-child{margin-top:0}
.doc .loc{display:inline-flex;align-items:center;gap:7px;font-size:11.5px;font-weight:600;color:var(--acc);
  background:var(--acc-soft);border:1px solid var(--acc-line);border-radius:7px;
  padding:2px 9px;margin:0 7px 0 0;vertical-align:1px;white-space:nowrap}
.doc .para{display:block}
mark{padding:1px 3px;border-radius:4px;color:var(--ink);cursor:pointer;box-decoration-break:clone;
  -webkit-box-decoration-break:clone;transition:filter .12s}
mark:hover{filter:brightness(.94)}
mark.high{background:#ffd4d6;box-shadow:inset 0 -2px 0 #f2a1a5}
mark.medium{background:#ffe9b8;box-shadow:inset 0 -2px 0 #ecc76e}
mark.low{background:#c6ecf7;box-shadow:inset 0 -2px 0 #8fd4e6}
mark.ph{background:linear-gradient(135deg,#dbe3ff,#e6dcff);border:1px dashed #a9b8f5;color:#2f3f9e;
  font-family:var(--fm);font-size:.9em}
.off{background:#f1f4f9;color:#a3aec2;text-decoration:line-through;border-radius:4px;padding:1px 3px;cursor:pointer}
.off:hover{background:#e8edf6}
.empty{padding:56px 20px;text-align:center;color:var(--sub);font-size:13.5px}
.empty .big{font-size:34px;margin-bottom:10px}

/* ------------------------------------------------------------- 底部操作条 */
.actionbar{position:sticky;bottom:0;z-index:45;margin-top:18px;
  background:rgba(255,255,255,.94);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border:1px solid var(--line);border-radius:var(--r);padding:14px 18px;box-shadow:0 -6px 24px rgba(15,26,50,.07)}
.ab-row{display:flex;align-items:center;gap:11px;flex-wrap:wrap}
.out-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:11px;padding-top:11px;
  border-top:1px dashed var(--line)}
.chk{display:inline-flex;align-items:center;gap:8px;font-size:12.6px;color:var(--sub);cursor:pointer;
  user-select:none;-webkit-user-select:none;padding:7px 11px;border:1px solid var(--line);
  border-radius:10px;background:#fff;transition:border-color .15s,background .15s}
.chk:hover{border-color:#c8d3ea}
.chk input{width:15px;height:15px;accent-color:var(--acc);cursor:pointer;margin:0}
.chk b{color:var(--ink);font-weight:620}
.chk.locked{background:var(--surface-2);color:var(--faint);cursor:default}
.folder{display:inline-flex;align-items:center;gap:6px;font-size:12.3px;color:var(--faint);line-height:1.5}
.folder.on{color:#0f9d58}
.folder code{background:var(--surface-2);border:1px solid var(--line-soft);border-radius:6px;
  padding:1px 6px;font-size:11.8px;color:var(--ink);font-family:var(--mono,ui-monospace,SFMono-Regular,Menlo,monospace)}
.result{margin-top:12px}
.result:empty{display:none}
.result .saved{display:flex;flex-direction:column;gap:5px;margin-top:8px}
.result .saved .ln{font-size:12.6px;color:var(--sub);line-height:1.6}
.result .saved .ln b{color:var(--ink);font-weight:620}

/* ------------------------------------------------------------- 页脚 */
.foot{max-width:1260px;margin:0 auto;padding:8px 26px 34px;display:flex;gap:10px;flex-wrap:wrap;
  align-items:center;color:var(--faint);font-size:11.8px}
.foot b{color:var(--sub);font-weight:600}

/* ------------------------------------------------------------- 启动/退出屏 */
.splash{min-height:100vh;display:grid;place-items:center;padding:24px}
.splash .box{width:min(460px,92vw);text-align:center;background:#fff;border:1px solid var(--line);
  border-radius:22px;padding:42px 36px;box-shadow:var(--sh-3)}
.splash .mark{width:62px;height:62px;border-radius:19px;margin:0 auto 18px;display:grid;place-items:center;
  background:linear-gradient(135deg,#3b5bff,#7a4dff);box-shadow:0 14px 30px rgba(59,91,255,.32)}
.splash h1{font-size:20px;margin:0 0 6px}
.splash p{margin:6px 0;color:var(--sub);font-size:13px}
.ring{width:46px;height:46px;margin:22px auto 4px;border-radius:50%;
  border:3px solid #e6ebf6;border-top-color:var(--acc);animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.track{height:6px;background:#eef1f8;border-radius:999px;overflow:hidden;margin:18px 0 0}
.track .fill{height:100%;width:34%;border-radius:999px;background:linear-gradient(90deg,#3b5bff,#7a4dff);
  animation:slide 1.5s ease-in-out infinite}
@keyframes slide{0%{transform:translateX(-110%)}100%{transform:translateX(320%)}}
.splash .tip{margin-top:16px;color:var(--faint);font-size:11.8px}
.bye{min-height:100vh;display:grid;place-items:center;text-align:center;color:var(--sub)}
.bye h1{color:var(--ink)}

/* ------------------------------------------------------------- 响应式 */
@media(max-width:1040px){
  .grid{grid-template-columns:1fr}
  .hero-art{display:none}
  .compare{grid-template-columns:1fr}
  .pane-body{height:auto;max-height:52vh}
}
@media(max-width:720px){
  .shell{padding:16px}
  .topbar-in{padding:10px 16px}
  .modes{grid-template-columns:1fr}
  .hero{padding:24px}
  .hero h1{font-size:22px}
  .foot{padding:8px 16px 26px}
}
"""


# =============================================================== 页面骨架 =====

HTML_HEAD = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>__TITLE__</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
__CSS__
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-in">
    <a class="brand" href="/" title="回到首页">
      <span class="mark">__MARK__</span>
      <span class="brand-txt"><b>合同脱敏 / 还原</b><i>__SUBTITLE__</i></span>
    </a>
    <div class="topbar-mid">__MID__</div>
    <div class="topbar-act">
      <span class="live"><span class="pulse"></span>离线运行中</span>
      <button class="btn sm ghost" onclick="quitApp()" title="停止本地服务">退出</button>
    </div>
  </div>
</header>
<main class="shell">
__BODY__
</main>
<footer class="foot">
  <span>🔒 <b>完全离线</b>：所有解析与改写均在本机完成，文件不外传</span>
  <span>·</span>
  <span>合同脱敏 / 还原 <b>v__VERSION__</b></span>
</footer>
<script>
async function quitApp(){
  if(!confirm('退出后本地服务会停止，需要重新双击应用才能再次使用。确定退出？')) return;
  try{ await fetch('/api/shutdown',{method:'POST'}); }catch(e){}
  document.body.innerHTML='<div class="bye"><h1>已退出</h1><p>本地服务已停止，可以关闭此窗口。</p></div>';
}
</script>
</body>
</html>
"""


def html_doc(title: str, body: str, mid: str = "") -> bytes:
    s = (HTML_HEAD
         .replace("__TITLE__", esc(title))
         .replace("__CSS__", CSS)
         .replace("__MARK__", BRAND_MARK)
         .replace("__SUBTITLE__", APP_SUBTITLE)
         .replace("__MID__", mid)
         .replace("__BODY__", body)
         .replace("__VERSION__", APP_VERSION))
    return s.encode("utf-8")


# =============================================================== 启动页 =======

LOADING_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>正在启动 · 合同脱敏 / 还原</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
__CSS__
</style></head>
<body>
<div class="splash">
  <div class="box">
    <div class="mark">__MARK__</div>
    <h1>正在启动本地服务</h1>
    <p id="status">正在准备运行环境…</p>
    <div class="ring"></div>
    <div class="track"><div class="fill"></div></div>
    <p class="tip">完全离线运行 · 文件不离开本机</p>
  </div>
</div>
<script>
var msgs=['正在准备运行环境…','正在启动本地 Python 服务…','正在加载脱敏规则…','正在初始化会话目录…','即将进入主页面…'];
var el=document.getElementById('status'),i=0;
var t=setInterval(function(){ i=Math.min(i+1,msgs.length-1); el.textContent=msgs[i]; },700);
async function tick(){
  for(var n=0;n<240;n++){
    try{
      var r=await fetch('/health',{cache:'no-store'});
      if(r.ok){ clearInterval(t); el.textContent='服务已就绪，正在进入…'; setTimeout(function(){location.href='/';},350); return; }
    }catch(e){}
    await new Promise(function(z){setTimeout(z,400)});
  }
  el.textContent='⚠ 服务未就绪，请查看启动器日志';
}
tick();
</script>
</body></html>
"""


def loading_doc() -> bytes:
    return (LOADING_HTML
            .replace("__CSS__", CSS)
            .replace("__MARK__", BRAND_MARK)
            .encode("utf-8"))


# =============================================================== 上传首页 =====

UPLOAD_BODY = r"""
<section class="hero">
  <div class="hero-copy">
    <span class="eyebrow">本地离线 · 无需联网</span>
    <h1>合同脱敏 / 还原</h1>
    <p>上传 Word / PDF / 文本合同，自动识别身份证号、手机号、姓名、地址、金额等敏感信息，一键替换为<b>可逆占位符</b>；需要时再把占位符精确还原回原文，批注与修订全部保留。</p>
  </div>
  __HERO_ART__
</section>

<form id="upload-form">
  <div class="grid">
    <div class="col stack">

      <div class="card">
        <h2><span class="step-n">1</span>选择操作模式</h2>
        <div class="modes" id="mode-picker">
          <div class="mode active" data-mode="redact">
            <div class="ic">🔒</div>
            <div class="name">脱敏模式</div>
            <div class="desc">上传<strong>原始</strong>合同 → 自动进入左右对比页 → 确认后输出 <code>合同_脱敏.docx</code> 与映射文件。</div>
          </div>
          <div class="mode" data-mode="restore">
            <div class="ic">🔓</div>
            <div class="name">还原模式</div>
            <div class="desc">上传<strong>已脱敏</strong>的合同，自动在文档内部寻找映射材料并回填原文，输出 <code>合同_还原.docx</code>。</div>
          </div>
        </div>
      </div>

      <div class="card">
        <h2><span class="step-n">2</span>上传合同文件</h2>
        <div class="drop" id="drop">
          <div class="ic">📄</div>
          <p class="t">把文件拖到这里，或点击选择</p>
          <p class="h">支持 .docx / .pdf / .txt · 单个文件不超过 100 MB</p>
          <input type="file" name="file" id="file-input" accept=".docx,.pdf,.txt,.md">
        </div>
        <div id="filename"></div>
        <input type="hidden" name="mode" id="mode-input" value="redact">
      </div>

      <div class="card">
        <div class="ab-row">
          <button class="btn primary lg" type="submit" id="submit-btn" disabled>下一步</button>
          <span class="stat" id="hint">请先选择文件</span>
        </div>
        <div id="result" class="result"></div>
      </div>

    </div>

    <div class="col stack">
      <div class="card">
        <h2>🔎 会识别什么</h2>
        <ul class="tlist">
          <li>身份证号、港澳台居民证件、护照号</li>
          <li>手机号、固定电话、邮箱</li>
          <li>自然人姓名、职务+姓名</li>
          <li>公司 / 机构名称、统一社会信用代码</li>
          <li>住址、通信地址、送达地址</li>
          <li>银行账号、开户行</li>
          <li>合同金额、价款、违约金（大写与小写）</li>
          <li>合同编号、日期、期限</li>
        </ul>
        <div class="alert info" style="margin:14px 0 0">
          <span class="i">ℹ️</span>
          <span>识别采用「格式规则 + 国标校验位」双重判定，身份证、统一社会信用代码、银行卡号会做校验位验算，尽量降低误报。</span>
        </div>
      </div>

      <div class="card">
        <h2>🛡 安全边界</h2>
        <ul class="tlist">
          <li>不需要任何网络连接，<b>不调用大模型与云端接口</b></li>
          <li>只监听 <code>127.0.0.1</code>，外部设备无法访问</li>
          <li>处理结果落盘在本地会话目录，可随时清理</li>
          <li>还原只改写正文文字，不动批注 / 修订 / 样式</li>
        </ul>
      </div>

      <div class="card">
        <h2>🧭 使用流程</h2>
        <ol class="olist">
          <li><span class="n">1</span><span>选择模式并上传合同</span></li>
          <li><span class="n">2</span><span>在左右对比页核对识别结果，按类型 / 严重度筛选，可单独取消某处</span></li>
          <li><span class="n">3</span><span>点击确认，生成脱敏文件与映射材料</span></li>
          <li><span class="n">4</span><span>需要原文时上传脱敏稿，一键还原</span></li>
        </ol>
      </div>
    </div>
  </div>
</form>

<script>
var drop=document.getElementById('drop'),
    fileInput=document.getElementById('file-input'),
    filenameEl=document.getElementById('filename'),
    submitBtn=document.getElementById('submit-btn'),
    modeInput=document.getElementById('mode-input'),
    hint=document.getElementById('hint'),
    resultEl=document.getElementById('result');

var LABEL={redact:'进入左右对比 →',restore:'上传并还原 →'};

function syncBtn(){
  var has=fileInput.files && fileInput.files.length;
  submitBtn.disabled=!has;
  submitBtn.textContent=LABEL[modeInput.value]||'下一步';
  hint.textContent = has ? '已就绪，点击开始处理' : '请先选择文件';
}

Array.prototype.forEach.call(document.querySelectorAll('#mode-picker .mode'),function(el){
  el.addEventListener('click',function(){
    Array.prototype.forEach.call(document.querySelectorAll('#mode-picker .mode'),function(x){x.classList.remove('active');});
    el.classList.add('active');
    modeInput.value=el.getAttribute('data-mode');
    syncBtn();
  });
});

function showFile(f){
  if(!f) return;
  filenameEl.innerHTML='<div class="picked"><span>📎</span><span>'+f.name.replace(/[<>&]/g,'')+' · '+(f.size/1048576).toFixed(2)+' MB</span><span class="x" id="clearFile">✕</span></div>';
  var c=document.getElementById('clearFile');
  if(c) c.addEventListener('click',function(){ fileInput.value=''; filenameEl.innerHTML=''; syncBtn(); });
  syncBtn();
}
fileInput.addEventListener('change',function(){ showFile(fileInput.files[0]); });
drop.addEventListener('click',function(){ fileInput.click(); });
drop.addEventListener('dragover',function(e){ e.preventDefault(); drop.classList.add('drag'); });
drop.addEventListener('dragleave',function(){ drop.classList.remove('drag'); });
drop.addEventListener('drop',function(e){
  e.preventDefault(); drop.classList.remove('drag');
  if(e.dataTransfer.files && e.dataTransfer.files.length){ fileInput.files=e.dataTransfer.files; showFile(e.dataTransfer.files[0]); }
});

document.getElementById('upload-form').addEventListener('submit',async function(ev){
  ev.preventDefault();
  var f=fileInput.files[0];
  if(!f){ return; }
  submitBtn.disabled=true;
  submitBtn.textContent='上传与识别中…';
  resultEl.innerHTML='<div class="alert info"><span class="i">⏳</span><span>正在上传并识别敏感信息，文件较大时请稍候…</span></div>';
  try{
    var fd=new FormData();
    fd.append('file',f);
    fd.append('mode',modeInput.value);
    var r=await fetch('/api/upload',{method:'POST',body:fd});
    var j=await r.json();
    if(!j.ok){ throw new Error(j.error||'上传失败'); }
    resultEl.innerHTML='<div class="alert ok"><span class="i">✓</span><span>识别完成，正在进入下一步…</span></div>';
    var dest = (j.mode==='restore') ? j.redirect : ('/review?sid='+j.sid);
    location.href=dest;
  }catch(e){
    resultEl.innerHTML='<div class="alert err"><span class="i">✗</span><span>'+String(e.message||e).replace(/[<>&]/g,'')+'</span></div>';
    submitBtn.disabled=false;
    syncBtn();
  }
});
syncBtn();
</script>
"""


def build_upload_page() -> bytes:
    return html_doc(APP_TITLE, UPLOAD_BODY.replace("__HERO_ART__", HERO_ART))


# =============================================================== 工作台 =======

WORKSPACE_BODY = r"""
<div class="page-head">
  <div>
    <h1>__HEAD_TITLE__</h1>
    <div class="meta">
      <span class="pill">📄 __FILENAME__</span>
      <span class="pill ghost">__SUMMARY__</span>
      <span class="pill ghost">Session __SID__</span>
    </div>
  </div>
</div>

__HINT__

<div class="card">
  <h2>请选择要执行的操作</h2>
  <div class="modes" id="mode-picker">
    <div class="mode __REDACT_ACTIVE__" data-mode="redact">
      <div class="ic">🔒</div>
      <div class="name">脱敏</div>
      <div class="desc">识别敏感信息并生成可逆占位符，输出 <code>合同_脱敏.docx</code>；映射材料会同步写进文档内部，<b>无须额外保管文件</b>。</div>
    </div>
    <div class="mode __RESTORE_ACTIVE__" data-mode="restore">
      <div class="ic">🔓</div>
      <div class="name">还原</div>
      <div class="desc">把脱敏稿里的占位符回填为原文，输出 <code>合同_还原.docx</code>；批注 / 审阅 / 修订等原有元素完全保留。</div>
    </div>
  </div>
</div>

<div class="card" id="redact-panel" style="display:none">
  <h2>脱敏设置</h2>
  <div class="meta" style="margin-bottom:14px">
    <span class="pill acc">共识别 __TYPE_COUNT__ 类 / __OCC_COUNT__ 处候选项</span>
  </div>
  <p class="stat" style="margin:0 0 16px">默认全部类型均已启用；在对比页可逐个类型、逐个位置取消，也可按严重度筛选。</p>
  <a class="btn primary lg" href="/review?sid=__SID__">进入左右对比页 →</a>
</div>

<div class="card" id="restore-panel" style="display:none">
  <h2>还原</h2>
  __RESTORE_STATUS__
  <div id="restore-msg" class="result"></div>
  __RESTORE_ACTION__
  <div id="restore-manual" style="margin-top:16px__MANUAL_HIDE__">
    <label class="field" style="display:block;font-size:12.8px;color:var(--sub);margin-bottom:6px">没有找到映射材料？手动选择一个 mapping.json：</label>
    <input type="file" id="manual-mapping" accept=".json">
    <div style="margin-top:12px">
      <button class="btn primary" type="button" onclick="uploadAndRestore()">上传映射并还原</button>
    </div>
  </div>
</div>

<script>
var SID='__SID__', FILE='__FILENAME__';
function goMode(m){
  Array.prototype.forEach.call(document.querySelectorAll('#mode-picker .mode'),function(el){
    el.classList.toggle('active', el.getAttribute('data-mode')===m);
  });
  document.getElementById('redact-panel').style.display = m==='redact' ? '' : 'none';
  document.getElementById('restore-panel').style.display = m==='restore' ? '' : 'none';
}
Array.prototype.forEach.call(document.querySelectorAll('#mode-picker .mode'),function(el){
  el.addEventListener('click',function(){ goMode(el.getAttribute('data-mode')); });
});

function okBox(url,name,extra){
  return '<div class="alert ok"><span class="i">✓</span><span>还原完成，共替换 '+extra+' 处。'+
         '<a class="btn ok sm" style="margin-left:10px" href="'+url+'">下载 '+name+'</a></span></div>';
}
async function runRestore(){
  var out=document.getElementById('restore-msg');
  out.innerHTML='<div class="alert info"><span class="i">⏳</span><span>正在还原正文文字…</span></div>';
  try{
    var r=await fetch('/api/restore/'+SID,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mapping:null})});
    var j=await r.json();
    if(j.ok){
      var warn=(j.missing&&j.missing.length)?('<div class="alert warn" style="margin-top:10px"><span class="i">⚠</span><span>有 '+j.missing.length+' 个占位符未在文档中找到，可能已被手工修改。</span></div>'):'';
      out.innerHTML=okBox(j.output_url,j.output_name,j.applied)+warn;
    }else{
      out.innerHTML='<div class="alert err"><span class="i">✗</span><span>还原失败：'+(j.error||'未知错误')+'</span></div>';
    }
  }catch(e){ out.innerHTML='<div class="alert err"><span class="i">✗</span><span>请求失败：'+String(e)+'</span></div>'; }
}
async function uploadAndRestore(){
  var file=document.getElementById('manual-mapping').files[0];
  if(!file){ alert('请先选择一个 mapping.json'); return; }
  var out=document.getElementById('restore-msg');
  out.innerHTML='<div class="alert info"><span class="i">⏳</span><span>正在上传映射并还原…</span></div>';
  try{
    var fd=new FormData(); fd.append('mapping',file);
    var r=await fetch('/api/restore/'+SID,{method:'POST',body:fd});
    var j=await r.json();
    if(j.ok){ out.innerHTML=okBox(j.output_url,j.output_name,j.applied); }
    else{ out.innerHTML='<div class="alert err"><span class="i">✗</span><span>还原失败：'+(j.error||'未知错误')+'</span></div>'; }
  }catch(e){ out.innerHTML='<div class="alert err"><span class="i">✗</span><span>请求失败：'+String(e)+'</span></div>'; }
}
goMode('__INIT_MODE__');
</script>
"""


def build_workspace_body(sid: str, info: Dict[str, Any]) -> bytes:
    name = esc(info.get("filename", ""))
    mode = info.get("mode")
    is_redacted = bool(info.get("looks_redacted") or info.get("is_redacted"))
    mapping = info.get("mapping_path")
    has_embedded = bool(info.get("has_embedded_mapping")) or mapping == "embedded"
    counts = info.get("counts") or {"types": 0, "occurrences": 0}

    if mode == "restore":
        summary = "还原模式 · 已跳过识别"
        head_title = "还原合同"
    else:
        summary = f"{counts.get('types', 0)} 类 / {counts.get('occurrences', 0)} 处候选项"
        head_title = "选择操作"

    hint = ""
    if is_redacted:
        hint = ('<div class="alert warn"><span class="i">⚠</span>'
                '<span>文档中检测到 <code>[类型#N]</code> 形态的占位符，看起来已经脱敏过。'
                '如果你要拿回原文，请选择 <b>还原</b>。</span></div>')

    if not mapping:
        restore_status = ('<div class="alert warn"><span class="i">⚠</span>'
                          '<span>没有在文档内部或同目录找到映射材料，需要你手动提供 mapping.json。</span></div>')
        restore_action = ""
        manual_hide = ""
    elif has_embedded:
        restore_status = ('<div class="alert ok"><span class="i">✓</span>'
                          '<span>已在文档内部（customXml）找到映射材料，可直接还原，无需外部文件。</span></div>')
        restore_action = ('<button class="btn primary lg" type="button" onclick="runRestore()">'
                          '✓ 直接执行还原</button>')
        manual_hide = ";display:none"
    else:
        restore_status = ('<div class="alert ok"><span class="i">✓</span>'
                          '<span>已找到映射文件：<code>' + esc(str(mapping).split("/")[-1]) + '</code></span></div>')
        restore_action = ('<button class="btn primary lg" type="button" onclick="runRestore()">'
                          '✓ 使用已找到的映射执行还原</button>')
        manual_hide = ";display:none"

    init_mode = "restore" if mode == "restore" else "redact"

    body = (WORKSPACE_BODY
            .replace("__HEAD_TITLE__", head_title)
            .replace("__FILENAME__", name)
            .replace("__SUMMARY__", summary)
            .replace("__SID__", esc(sid))
            .replace("__HINT__", hint)
            .replace("__TYPE_COUNT__", str(counts.get("types", 0)))
            .replace("__OCC_COUNT__", str(counts.get("occurrences", 0)))
            .replace("__RESTORE_STATUS__", restore_status)
            .replace("__RESTORE_ACTION__", restore_action)
            .replace("__MANUAL_HIDE__", manual_hide)
            .replace("__REDACT_ACTIVE__", "active" if init_mode == "redact" else "")
            .replace("__RESTORE_ACTIVE__", "active" if init_mode == "restore" else "")
            .replace("__INIT_MODE__", init_mode))
    return html_doc("选择操作 · " + info.get("filename", ""), body,
                    mid='<span class="pill">' + name + '</span>')


# =============================================================== 对比页 =======

REVIEW_BODY = r"""
<div class="page-head">
  <div>
    <h1>脱敏前 / 脱敏后 · 左右对比</h1>
    <div class="meta">
      <span class="pill">📄 __FILENAME__</span>
      <span class="pill ghost">__TYPES__ 类 · __OCC__ 处候选项</span>
      <span class="pill ghost">Session __SID__</span>
    </div>
  </div>
</div>

<div class="toolbar">
  <div class="tb-row">
    <span class="tb-label">严重度</span>
    <div class="seg" id="sev">
      <button type="button" class="seg-btn on" data-sev="all">全部</button>
      <button type="button" class="seg-btn" data-sev="high">高</button>
      <button type="button" class="seg-btn" data-sev="medium">中</button>
      <button type="button" class="seg-btn" data-sev="low">低</button>
    </div>
    <span class="grow"></span>
    <button type="button" class="btn sm ghost" id="toggleTypes">筛选类型 ▾</button>
    <button type="button" class="btn sm ghost" id="selAll">全选</button>
    <button type="button" class="btn sm ghost" id="selNone">清空</button>
    <button type="button" class="btn sm ghost" id="resetMarks">恢复全部位置</button>
  </div>
  <div class="types-wrap" id="typesWrap"><div id="types"></div></div>
</div>

<div class="compare">
  <div class="pane">
    <div class="pane-head"><span class="sw"></span>原文 · 彩色高亮 = 会被替换；点击高亮可取消该处</div>
    <div class="pane-body doc" id="left"></div>
  </div>
  <div class="pane">
    <div class="pane-head"><span class="sw alt"></span>脱敏后 · 占位符预览（随勾选实时变化）</div>
    <div class="pane-body doc" id="right"></div>
  </div>
</div>

<div class="actionbar">
  <div class="ab-row">
    <button class="btn primary lg" type="button" id="go">确认并执行脱敏</button>
    <button class="btn ghost" type="button" onclick="history.back()">返回</button>
    <span class="grow"></span>
    <span class="stat" id="stat"></span>
  </div>
  <div class="out-row">
    <label class="chk locked" title="脱敏文件为必选项"><input type="checkbox" id="optDoc" checked disabled><span>脱敏文件 <b>*.docx</b></span></label>
    <label class="chk" id="jsonWrap" title="取消勾选后只输出脱敏稿；映射材料仍嵌在文档内部，可随时还原，但请自行留意保管。"><input type="checkbox" id="optJson" checked><span>映射文件 <b>*.mapping.json</b>（还原用，建议保留）</span></label>
    <button type="button" class="btn sm ghost" id="pickDir" title="选择一个文件夹后，两个文件会直接存进去，不再弹出下载框；建议选择「上传合同所在的文件夹」">选择保存文件夹…</button>
    <span class="folder" id="dirState">未选择 → 下载到浏览器默认下载目录（建议选原合同所在文件夹）</span>
  </div>
  <div id="result" class="result"></div>
</div>

<script>
var DATA = __DATA__;
var enabled = new Set(DATA.types.map(function(t){return t.id;}));
var sev = 'all';
var itemEnabled = new Map();
DATA.blocks.forEach(function(b,bi){ (b.marks||[]).forEach(function(m,mi){ itemEnabled.set(bi+':'+mi,true); }); });

function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }

function renderTypes(){
  var box=document.getElementById('types'); box.innerHTML='';
  var cats={};
  DATA.types.forEach(function(t){ (cats[t.cat]=cats[t.cat]||[]).push(t); });
  var rank={high:0,medium:1,low:2};
  var visible=0;
  Object.keys(cats).forEach(function(cat){
    var list=cats[cat].filter(function(t){ return sev==='all'||t.sev===sev; });
    if(!list.length) return;
    var d=document.createElement('div'); d.className='cat'; d.textContent=cat; box.appendChild(d);
    var wrap=document.createElement('div'); wrap.className='chips';
    list.slice().sort(function(a,b){ return rank[a.sev]-rank[b.sev]; }).forEach(function(t){
      var on = enabled.has(t.id);
      var c=document.createElement('label');
      c.className='chip'+(on?' on':' off');
      c.setAttribute('data-sev',t.sev);
      c.innerHTML='<input type="checkbox" '+(on?'checked':'')+'>'+
        '<span class="dot" style="background:'+({high:'#e5484d',medium:'#dd9207',low:'#0d9bc0'}[t.sev]||'#94a3b8')+'"></span>'+
        esc(t.label)+' <span class="cnt">'+t.count+'</span>';
      c.querySelector('input').addEventListener('change',function(ev){
        if(ev.target.checked) enabled.add(t.id); else enabled.delete(t.id);
        render();
      });
      wrap.appendChild(c);
      visible++;
    });
    box.appendChild(wrap);
  });
  document.getElementById('toggleTypes').textContent='筛选类型 ▾ '+visible;
}

function render(){
  Array.prototype.forEach.call(document.querySelectorAll('.seg-btn'),function(b){
    b.classList.toggle('on', b.getAttribute('data-sev')===sev);
  });
  renderTypes();
  var left=[],right=[],n=0,lastLoc=null;
  DATA.blocks.forEach(function(b,bi){
    var ms0=b.marks||[];
    var plain=(b.text||'').replace(/\s+/g,' ').trim();
    if(!plain && !ms0.length) return;                 /* 跳过空段落，减少噪音 */
    var loc=b.loc||('段落 '+(bi+1));
    var head=(loc!==lastLoc)?('<span class="loc">'+esc(loc)+'</span>'):'';
    lastLoc=loc;
    var ms=ms0.slice().sort(function(a,c){return a.s-c.s;});
    var pos=0,L='',R='';
    ms.forEach(function(m,mi){
      m.bk=bi; m.mi=mi;
      var ls=m.s-b.start, le=m.e-b.start;
      if(ls<pos||ls<0) return;
      L+=esc(b.text.slice(pos,ls)); R+=esc(b.text.slice(pos,ls));
      if(enabled.has(m.t)&&itemEnabled.get(bi+':'+mi)){
        n++;
        L+='<mark class="'+m.sev+'" data-bk="'+bi+'" data-mi="'+mi+'" title="点击取消该处">'+esc(b.text.slice(ls,le))+'</mark>';
        R+='<mark class="ph sev-'+m.sev+'" title="'+esc(m.label)+'">'+esc(m.placeholder||m.masked)+'</mark>';
      }else{
        L+='<span class="off" data-bk="'+bi+'" data-mi="'+mi+'" title="点击恢复该处">'+esc(b.text.slice(ls,le))+'</span>';
        R+=esc(b.text.slice(ls,le));
      }
      pos=le;
    });
    L+=esc(b.text.slice(pos)); R+=esc(b.text.slice(pos));
    left.push('<div class="blk">'+head+(L||'&nbsp;')+'</div>');
    right.push('<div class="blk">'+head+(R||'&nbsp;')+'</div>');
  });
  var lEl=document.getElementById('left'), rEl=document.getElementById('right');
  if(!DATA.blocks.length){
    lEl.innerHTML='<div class="empty"><div class="big">🎉</div>没有识别到需要脱敏的敏感信息</div>';
    rEl.innerHTML='<div class="empty"><div class="big">✨</div>文档保持原样即可</div>';
  }else{
    lEl.innerHTML=left.join('');
    rEl.innerHTML=right.join('');
  }
  Array.prototype.forEach.call(document.querySelectorAll('mark[data-bk]'),function(el){
    el.addEventListener('click',function(){
      itemEnabled.set(el.getAttribute('data-bk')+':'+el.getAttribute('data-mi'),false); render();
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll('span.off[data-bk]'),function(el){
    el.addEventListener('click',function(){
      itemEnabled.set(el.getAttribute('data-bk')+':'+el.getAttribute('data-mi'),true); render();
    });
  });
  document.getElementById('stat').innerHTML='将替换 <b>'+n+'</b> 处 · 生效类型 <b>'+enabled.size+'</b> 类';
}

/* 左右同步滚动 */
(function(){
  var l=document.getElementById('left'), r=document.getElementById('right'), lock=false;
  function link(a,b){
    a.addEventListener('scroll',function(){
      if(lock) return; lock=true; b.scrollTop=a.scrollTop; b.scrollLeft=a.scrollLeft;
      setTimeout(function(){lock=false;},30);
    });
  }
  link(l,r); link(r,l);
})();

Array.prototype.forEach.call(document.querySelectorAll('.seg-btn'),function(b){
  b.addEventListener('click',function(){ sev=b.getAttribute('data-sev'); render(); });
});
document.getElementById('toggleTypes').addEventListener('click',function(){
  document.getElementById('typesWrap').classList.toggle('open');
});
document.getElementById('selAll').addEventListener('click',function(){
  enabled=new Set(DATA.types.map(function(t){return t.id;})); render();
});
document.getElementById('selNone').addEventListener('click',function(){
  enabled=new Set(); render();
});
document.getElementById('resetMarks').addEventListener('click',function(){
  DATA.blocks.forEach(function(b,bi){ (b.marks||[]).forEach(function(m,mi){ itemEnabled.set(bi+':'+mi,true); }); });
  render();
});

// ============================================================ 输出保存 =======
// 目标：确认后「脱敏 docx + mapping.json」两个文件一起落地，默认两个都要，
//       不要让用户在下载哪几个文件上做选择题。
// 手段：① 用户若选过文件夹 → 用 File System Access API 直接写入该文件夹
//          （127.0.0.1 属安全上下文，Chrome/Edge 可用；不再弹下载框）
//       ② 否则 → 依次触发两个文件的浏览器下载（兜底，任何浏览器都可）
var dirHandle = null;
var pickBtn = document.getElementById('pickDir');
var dirStateEl = document.getElementById('dirState');
var FSA_OK = !!(window && window.showDirectoryPicker);

if(!FSA_OK){
  pickBtn.disabled = true;
  pickBtn.textContent = '当前浏览器不支持选文件夹';
  pickBtn.title = '将直接下载到浏览器默认下载目录';
}

pickBtn.addEventListener('click', async function(){
  if(!FSA_OK) return;
  try{
    var h = await window.showDirectoryPicker({id:'contract-redactor-out', mode:'readwrite', startIn:'downloads'});
    if(await h.queryPermission({mode:'readwrite'}) !== 'granted'){
      if(await h.requestPermission({mode:'readwrite'}) !== 'granted') return;
    }
    dirHandle = h;
    dirStateEl.className = 'folder on';
    dirStateEl.innerHTML = '已选择文件夹：<code>' + esc(h.name) + '</code>（两个文件都会存到这里）';
    pickBtn.textContent = '更换文件夹…';
  }catch(e){ /* 用户取消选择，保持原状 */ }
});

function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }

function browserDownload(url){
  var a = document.createElement('a');
  a.href = url; a.download = ''; a.rel = 'noopener'; a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(function(){ if(a.parentNode) a.parentNode.removeChild(a); }, 2000);
}

async function writeToFolder(url, name){
  var resp = await fetch(url);
  if(!resp.ok) throw new Error('HTTP ' + resp.status);
  var blob = await resp.blob();
  var fh = await dirHandle.getFileHandle(name, {create:true});
  var w = await fh.createWritable();
  await w.write(blob);
  await w.close();
  return blob.size;
}

// 保存产物。默认勾选 = 脱敏 docx + mapping.json 两个都存
async function saveOutputs(j){
  var jobs = [{url:j.output_url, name:j.output_name}];
  if(document.getElementById('optJson').checked && j.mapping_url){
    jobs.push({url:j.mapping_url, name:j.mapping_name || 'mapping.json'});
  }

  if(dirHandle){
    var saved = [], failed = [];
    for(var i=0;i<jobs.length;i++){
      try{
        var sz = await writeToFolder(jobs[i].url, jobs[i].name);
        saved.push({name:jobs[i].name, size:sz, how:'folder'});
      }catch(e){
        failed.push(jobs[i]);
      }
    }
    for(var k=0;k<failed.length;k++){       // 写盘失败 → 退化成浏览器下载
      browserDownload(failed[k].url);
      saved.push({name:failed[k].name, size:0, how:'browser'});
      await sleep(400);
    }
    return {folder:dirHandle.name, files:saved, degraded:failed.length > 0};
  }

  // 未选文件夹：两个文件都下载到浏览器默认下载目录
  var out = [];
  for(var n=0;n<jobs.length;n++){
    browserDownload(jobs[n].url);
    out.push({name:jobs[n].name, size:0, how:'browser'});
    if(n < jobs.length - 1) await sleep(500);
  }
  return {folder:'', files:out, degraded:false};
}

function renderSaved(sv, j){
  var lines = sv.files.map(function(f){
    var kb = f.size ? '（' + Math.max(1, Math.round(f.size/1024)) + ' KB）' : '';
    return '<div class="ln">• <b>' + esc(f.name) + '</b>' + kb + '</div>';
  }).join('');
  var head;
  if(sv.folder){
    head = '已自动保存到文件夹 <code style="background:var(--surface-2);border:1px solid var(--line-soft);border-radius:6px;padding:1px 6px">' + esc(sv.folder) + '</code>';
    if(sv.degraded) head += '（部分文件写入失败，已改为下载）';
  }else{
    head = '已自动下载到浏览器默认下载目录（首次可能弹出「是否允许多个文件下载」，选择允许即可）';
  }
  return '<div class="saved">' +
    '<div class="ln">' + head + '</div>' + lines +
    '<div class="ln" style="color:var(--faint)">提示：mapping.json 已同时嵌入脱敏稿内部，日后直接上传脱敏稿即可一键还原。</div>' +
    '</div>';
}

document.getElementById('go').addEventListener('click',async function(){
  var btn=document.getElementById('go'), out=document.getElementById('result');
  if(enabled.size===0){ out.innerHTML='<div class="alert warn"><span class="i">⚠</span><span>还没有选择任何类型，请至少勾选一类。</span></div>'; return; }
  var enabledItems=[];
  DATA.blocks.forEach(function(b,bi){
    (b.marks||[]).forEach(function(m,mi){
      // 用绝对偏移（m.s/m.e）而不是实体内部序号：序号每个实体都从 0 重来，会串号
      if(enabled.has(m.t)&&itemEnabled.get(bi+':'+mi)){ enabledItems.push({type:m.t,offset:[m.s,m.e]}); }
    });
  });
  btn.disabled=true;
  out.innerHTML='<div class="alert info"><span class="i">⏳</span><span>正在生成脱敏文件并写入映射材料…</span></div>';
  try{
    // 与上传时的识别参数保持一致：否则服务端重扫得到的偏移会与这里的位置白名单对不上
    var sel={enabled_types:Array.from(enabled),
             min_confidence:(DATA.min_confidence||0.5),
             min_severity:(DATA.min_severity||'low'),
             items:enabledItems};
    var r=await fetch('/api/apply/__SID__',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(sel)});
    var j=await r.json();
    if(j.ok){
      out.innerHTML='<div class="alert info"><span class="i">⏳</span><span>脱敏完成，正在保存文件…</span></div>';
      var sv=await saveOutputs(j);
      out.innerHTML='<div class="alert ok"><span class="i">✓</span><span>脱敏完成：替换 '+j.applied+' 处，跳过 '+j.skipped+' 处。'+
        renderSaved(sv,j)+
        '<div style="margin-top:9px">'+
          '<a class="btn ok sm" href="'+j.output_url+'" download>另存 '+esc(j.output_name)+'</a>'+
          (j.mapping_url?('<a class="btn sm" style="margin-left:8px" href="'+j.mapping_url+'" download>另存 '+esc(j.mapping_name||'mapping.json')+'</a>'):'')+
        '</div>'+
        (j.warnings?('<div class="stat" style="margin-top:8px">'+esc(j.warnings)+'</div>'):'')+
        '</span></div>';
    }else{
      out.innerHTML='<div class="alert err"><span class="i">✗</span><span>脱敏失败：'+esc(j.error||'未知错误')+'</span></div>';
    }
  }catch(e){
    out.innerHTML='<div class="alert err"><span class="i">✗</span><span>请求失败：'+esc(String(e))+'</span></div>';
  }
  btn.disabled=false;
});

render();
</script>
"""


def build_review_page(sid: str, info: Dict[str, Any]) -> bytes:
    payload = info.get("review_payload") or {}
    report = info.get("report") or {}
    types_n = len(report.get("items") or [])
    occ_n = (report.get("summary") or {}).get("occurrences", 0)
    name = info.get("filename", "")
    data_json = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")

    body = (REVIEW_BODY
            .replace("__FILENAME__", esc(name))
            .replace("__TYPES__", str(types_n))
            .replace("__OCC__", str(occ_n))
            .replace("__SID__", esc(sid))
            .replace("__DATA__", data_json))
    return html_doc("左右对比 · " + name, body,
                    mid='<span class="pill">' + esc(name) + '</span>')


# =============================================================== 失效页 =======

def build_expired_page() -> bytes:
    body = """
<div class="empty" style="padding:90px 20px">
  <div class="big">🕓</div>
  <h1 style="margin-bottom:8px">会话已失效</h1>
  <p class="muted">可能是服务重启过，之前的会话记录已清空。请重新上传文件。</p>
  <p style="margin-top:20px"><a class="btn primary lg" href="/">回到首页重新上传</a></p>
</div>
"""
    return html_doc("会话已失效", body)
