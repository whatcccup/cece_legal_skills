#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 contract_sensitive_detector.py
 合同敏感信息「候选项」识别器 —— 完全离线版
================================================================================

定位
------
本文件是「合同脱敏方案」的第 1 阶段：**识别**（Detection）。
它只负责把 Word / PDF 合同里的敏感信息"找出来、定位好、打上分"，
**不负责**改写原文档（改写是第 2 阶段 Apply 的职责）。

输入：.docx / .pdf（带文本层）/ .txt / .md
输出：JSON 清单、CSV 清单、标注文本、人工复核 HTML、脱敏预览文本

离线保证
--------
* 不调用任何大模型、云端 API、网络服务、第三方识别接口；
* 仅依赖本地规则：正则 + 上下文关键词 + 国标校验位算法（GB 11643 / GB 32100 / Luhn）；
* 默认开启 `--enforce-offline`（可用 `--allow-network` 关闭），该开关会直接
  禁用 socket，任何联网尝试都会立即抛错，从机制上杜绝"偷偷外传"。

识别思路（四层漏斗，逐层收窄）
------------------------------
  L0 解析层  : docx 保留段落/表格/页眉页脚归属；pdf 保留页码 + 词级坐标（供后续涂黑）
  L1 归一化层: 全角→半角、去零宽字符，**保留 norm→raw 的下标映射**，定位不错位
  L2 召回层  : 正则 / 上下文规则产出候选（宁可多召回，允许一定误报）
  L3 判别层  : 校验位验真、占位符剔除、白名单剔除、上下文加权、跨类型重叠消解、置信度重排

依赖
----
    pip install python-docx pdfplumber pypdf
（均为纯本地解析库；pdfplumber 缺失时自动降级到 pypdf，仅丢失 PDF 坐标）

用法
----
    python contract_sensitive_detector.py 合同.docx
    python contract_sensitive_detector.py *.pdf --out-dir reports --format json,html
    python contract_sensitive_detector.py c.docx --min-confidence 0.7 --min-severity medium
    python contract_sensitive_detector.py c.docx --allowlist allowlist.txt --config cfg.json
    python contract_sensitive_detector.py --selftest

作者：合同脱敏方案 / v1.0
================================================================================
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

__version__ = "1.0.0"
ENGINE_NAME = "offline-rule-detector"

# ==============================================================================
# 0. 元数据类型定义
# ==============================================================================

SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}
SEVERITY_LABEL = {"high": "高", "medium": "中", "low": "低"}


@dataclass(frozen=True)
class TypeMeta:
    """某一类敏感信息的元信息与默认脱敏策略。"""

    type_id: str
    label: str            # 中文名
    category: str         # 归类
    severity: str         # high / medium / low
    keep_head: int = 0    # 脱敏时保留前 N 位
    keep_tail: int = 0    # 脱敏时保留后 N 位
    mask_char: str = "*"
    replacement: Optional[str] = None  # 非空则整体替换为该串
    mask_fn: Optional[Callable[[str], str]] = None
    priority: int = 0     # 重叠消解优先级，越大越优先
    enabled: bool = True  # 是否默认启用（可在规则清单 Markdown 中调整）


def _mask_email(v: str) -> str:
    if "@" not in v:
        return v[0] + "*" * max(len(v) - 1, 1)
    local, domain = v.rsplit("@", 1)
    keep = local[0] if local else ""
    return f"{keep}{'*' * max(len(local) - 1, 3)}@{domain}"


# 常见复姓（脱敏姓名时保留 2 字）
COMPOUND_SURNAMES = {
    "欧阳", "太史", "端木", "上官", "司马", "东方", "独孤", "南宫", "万俟", "闻人",
    "夏侯", "诸葛", "尉迟", "公羊", "赫连", "澹台", "皇甫", "宗政", "濮阳", "公冶",
    "太叔", "申屠", "公孙", "慕容", "仲孙", "钟离", "长孙", "宇文", "司徒", "鲜于",
    "司空", "闾丘", "子车", "亓官", "司寇", "巫马", "公西", "颛孙", "壤驷", "公良",
    "漆雕", "乐正", "宰父", "谷梁", "拓跋", "夹谷", "轩辕", "令狐", "段干", "百里",
    "呼延", "东郭", "南门", "羊舌", "微生", "梁丘", "左丘", "西门", "第五",
}

# 常见单姓（用于姓名候选项的姓氏校验，覆盖《百家姓》前 300 余位）
SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章"
    "云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常"
    "乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞"
    "熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍"
    "虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁"
    "荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫"
    "宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙"
    "池乔阴鬱胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍卻璩桑桂濮牛寿通边扈燕冀郏浦尚农"
    "温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东"
    "欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红"
    "游竺权逯盖益桓公岳帅缑亢况后有琴梁丘左丘东门商牟佘佴伯赏南宫墨哈谯笪年爱阳佟言福"
)

# 姓名右边界：命中这些字/标点才认为姓名到此为止，避免把「张三丰有限公司」切成「张三是本」
NAME_BOUNDARY = set("，。；、：？！（）()[]「」『』《》〈〉“”‘’ \t\r\n·-—_/\\\u3000")
NAME_TAIL_WORDS = ("先生", "女士", "小姐", "同志", "老师", "教授", "医生", "律师", "的", "等", "与", "和", "及")

# 组织机构名：强后缀（可独立判定）/ 弱后缀（需更高门槛）
ORG_SUFFIX_STRONG = (
    "股份有限公司", "有限责任公司", "有限公司", "集团有限公司", "（有限合伙）", "(有限合伙)",
    "有限合伙", "股份合作公司", "集团公司", "总公司", "分公司", "子公司",
    "律师事务所", "会计师事务所", "税务师事务所", "研究院", "设计院", "勘察院",
    "大学", "学院", "医院", "银行", "信用社", "合作社", "基金会", "商会", "行业协会",
    "支行", "分行", "营业部",
)
ORG_SUFFIX_WEAK = ("事务所", "中心", "研究院", "实验室", "集团", "协会", "学会", "管委会", "办事处", "工作室")

# 组织机构名白名单：这些"看起来像机构"的词在合同里是代词/通用表述，不该脱敏
ORG_STOPWORDS = {
    "甲方", "乙方", "丙方", "丁方", "戊方", "双方", "各方", "单方", "对方", "第三方",
    "本公司", "贵公司", "该公司", "子公司", "母公司", "总公司", "借款人", "出租人",
    "承租人", "出卖人", "买受人", "发包人", "承包人", "委托人", "受托人", "保证人",
    "债权人", "债务人", "甲方公司", "乙方公司", "开户银行", "收款银行", "付款银行",
    "开户行", "银行账号", "仲裁委员会", "人民法院",
}

# 常见占位符 / 示例值
PLACEHOLDER_PATTERNS = [
    re.compile(r"^(\d)\1{5,}$"),                      # 000000 / 11111111
    re.compile(r"^(?:1234567890|0123456789)"),         # 顺子
    re.compile(r"^[Xx×＊*·．.]{3,}$"),                  # XXX / ***
    re.compile(r"^[某甲乙丙丁]{1,3}(?:某|方|公司)*$"),   # 某某 / 甲方
]


# 服务热线（400 / 800 号段）。这类号码本身可能只由 0/8 组成（如 800 800 8888），
# 会被 is_placeholder 的「数字种类 ≤ 2」规则误杀，所以单独放行。
HOTLINE_RE = re.compile(r"^(?:400|800)[\s\-—–－]?\d{3}[\s\-—–－]?\d{4}$")


def is_placeholder(value: str) -> bool:
    v = value.strip()
    if not v:
        return True
    digits = re.sub(r"\D", "", v)
    if len(digits) >= 6:
        if len(set(digits)) <= 2:                      # 只由 1~2 种数字组成
            return True
        if digits in ("1234567890", "0123456789", "123456789", "012345678"):
            return True
    for p in PLACEHOLDER_PATTERNS:
        if p.match(v):
            return True
    if re.fullmatch(r"[*xX×#]{4,}", v):
        return True
    return False


# ------------------------------------------------------------------------------
# 敏感信息类型注册表
# ------------------------------------------------------------------------------

def _mask_person(v: str) -> str:
    """姓名：保留姓氏（复姓保留 2 字），其余替换 **。"""
    head = 2 if v[:2] in COMPOUND_SURNAMES else 1
    return v[:head] + "*" * max(len(v) - head, 1)


def _mask_amount(v: str) -> str:
    """金额：按规则清单替换为 ¥******.**元。"""
    return "¥******.**元"


def _mask_hk_id(v: str) -> str:
    """香港身份证 A123456(7)：保留首字母与括号内校验位，中间 6 位掩码。"""
    m = re.match(r"^([A-Z]{1,2})(\d{6})(?:[(（](\d)[)）])?$", v.strip().upper())
    if not m:
        return v[0] + "*" * max(len(v) - 1, 1)
    tail = f"({m.group(3)})" if m.group(3) else ""
    return f"{m.group(1)}******{tail}"


def _mask_landline(v: str) -> str:
    """固定电话：保留区号与末 4 位，中间掩码。

    支持区号与号码之间、号码内部分组之间的空格/横线：
        0755-86329871  → 0755-****9871
        010-8666 2188  → 010-****2188
        010 8666 2188  → 010-****2188
        400-800-8888   → 400-***-8888
    """
    s = v.strip()
    # 服务热线：400/800 号段
    hot = re.match(r"^(400|800)\s*[-—–]?\s*(.*)$", s)
    if hot and re.sub(r"\D", "", s) and len(re.sub(r"\D", "", s)) >= 7:
        rest = re.sub(r"\D", "", hot.group(2))
        if len(rest) <= 4:
            return f"{hot.group(1)}-" + "*" * len(rest)
        return f"{hot.group(1)}-" + "*" * (len(rest) - 4) + rest[-4:]
    m = re.match(r"^\(?\s*(0\d{2,3})\s*\)?\s*[-—–]?\s*(.*)$", s)
    if not m:
        digits = re.sub(r"\D", "", s)
        if len(digits) <= 4:
            return "*" * len(digits)
        return digits[0] + "*" * max(len(digits) - 5, 1) + digits[-4:]
    area, rest = m.group(1), re.sub(r"\D", "", m.group(2))
    if len(rest) <= 4:
        return f"{area}-" + "*" * len(rest)
    return f"{area}-" + "*" * (len(rest) - 4) + rest[-4:]


_ADDR_ADMIN_RE = re.compile(
    r"^\s*[\u4e00-\u9fff]{1,8}?(?:省|自治区)?"
    r"[\u4e00-\u9fff]{1,10}?(?:市|自治州|地区|盟)"
    r"[\u4e00-\u9fff]{1,15}?(?:区|县|旗|市)"
)


def _mask_address(v: str) -> str:
    """地址：保留行政区划（省/市/区县），掩掉街道门牌。"""
    m = _ADDR_ADMIN_RE.match(v)
    head = m.group(0) if m else v[:6]
    rest = len(v) - len(head)
    if rest <= 0:
        return v
    return head + "*" * rest


def _mask_ipv4(v: str) -> str:
    """IP：保留第一段，其余掩码。192.*.*.*"""
    parts = v.split(".")
    if len(parts) == 4:
        return parts[0] + ".*.*.*"
    return "*" * len(v)


def _mask_mac(v: str) -> str:
    """MAC：保留前 2 位，其余掩码。AA:*:*:*:*:*"""
    parts = re.split(r"[:\-]", v)
    if len(parts) == 6:
        sep = ":" if ":" in v else "-"
        return parts[0] + sep + "*".center(2, "*") + (sep + "*".center(2, "*")) * 4
    return "*" * len(v)


def _mask_secret(_v: str) -> str:
    """密钥/凭据：完全阻断，不留任何痕迹。"""
    return "[已脱敏]"


def _mask_id_head(v: str) -> str:
    """护照：保留首字母，其余掩码。E********"""
    return v[0] + "*" * max(len(v) - 1, 1)


TYPE_META: Dict[str, TypeMeta] = {
    # ---- 身份标识 ----
    "ID_CARD": TypeMeta("ID_CARD", "身份证号", "身份标识", "high", 6, 4, priority=100),
    "ID_CARD_15": TypeMeta("ID_CARD_15", "身份证号(15位老证)", "身份标识", "high", 6, 4, priority=98),
    "PASSPORT": TypeMeta("PASSPORT", "护照号", "身份标识", "medium", 0, 0, mask_fn=_mask_id_head, priority=80),
    "HK_ID_CARD": TypeMeta("HK_ID_CARD", "香港身份证", "身份标识", "high", 0, 0, mask_fn=_mask_hk_id, priority=90),
    "HK_MO_TW_PERMIT": TypeMeta("HK_MO_TW_PERMIT", "港澳台通行证", "身份标识", "medium", 2, 2, priority=78),
    "PERSON_NAME": TypeMeta("PERSON_NAME", "自然人姓名", "身份标识", "high", 0, 0, mask_fn=_mask_person, priority=70),
    # ---- 联系方式 ----
    "PHONE_MOBILE": TypeMeta("PHONE_MOBILE", "手机号码", "联系方式", "high", 3, 4, priority=95),
    "PHONE_LANDLINE": TypeMeta("PHONE_LANDLINE", "固定电话", "联系方式", "medium", 0, 0, mask_fn=_mask_landline, priority=60),
    "EMAIL": TypeMeta("EMAIL", "电子邮箱", "联系方式", "high", 0, 0, mask_fn=_mask_email, priority=92),
    "ADDRESS": TypeMeta("ADDRESS", "住址/通信地址", "联系方式", "high", 0, 0, mask_fn=_mask_address, priority=68),
    "POSTCODE": TypeMeta("POSTCODE", "邮政编码", "联系方式", "low", 0, 0, priority=40),
    "SOCIAL_ACCOUNT": TypeMeta("SOCIAL_ACCOUNT", "即时通讯账号(微信/QQ)", "联系方式", "low", 1, 2, priority=35),
    # ---- 金融账户 ----
    "BANK_CARD": TypeMeta("BANK_CARD", "银行卡号", "金融账户", "high", 4, 4, priority=96),
    "BANK_ACCOUNT": TypeMeta("BANK_ACCOUNT", "银行账号/对公账号", "金融账户", "high", 4, 4, priority=72),
    # ---- 组织主体 ----
    "ORG_NAME": TypeMeta("ORG_NAME", "组织机构名称", "组织主体", "medium", 2, 4, priority=66),
    "USCC": TypeMeta("USCC", "统一社会信用代码", "组织主体", "medium", 2, 2, priority=94),
    "TAX_ID": TypeMeta("TAX_ID", "税务登记号/纳税人识别号", "组织主体", "medium", 4, 4, priority=74),
    "LICENSE_NO": TypeMeta("LICENSE_NO", "营业执照编号(注册号)", "组织主体", "medium", 3, 3, priority=73),
    # ---- 商业信息 ----
    "AMOUNT": TypeMeta("AMOUNT", "合同金额", "商业信息", "medium", 0, 0, mask_fn=_mask_amount, priority=50),
    "CONTRACT_NO": TypeMeta("CONTRACT_NO", "合同/发票/订单编号", "商业信息", "medium", 2, 2, priority=52),
    "DATE": TypeMeta("DATE", "日期", "商业信息", "low", 4, 0, priority=30),
    "PLATE": TypeMeta("PLATE", "车牌号", "其他", "low", 1, 2, priority=28),
    # ---- 法律信息 ----
    "CASE_NO": TypeMeta("CASE_NO", "案件号/公文字号", "法律信息", "medium", 2, 2, priority=54),
    # ---- 凭据（block 级）----
    "SECRET": TypeMeta("SECRET", "密钥/凭据", "凭据信息", "high", 0, 0, mask_fn=_mask_secret, priority=99),
    # ---- 网络信息（默认关闭，可在规则清单中开启）----
    "IPV4": TypeMeta("IPV4", "IP 地址", "网络信息", "low", 0, 0, mask_fn=_mask_ipv4, priority=26, enabled=False),
    "MAC_ADDRESS": TypeMeta("MAC_ADDRESS", "MAC 物理地址", "网络信息", "low", 0, 0, mask_fn=_mask_mac, priority=25, enabled=False),
    # ---- 其他 ----
    "URL": TypeMeta("URL", "网址链接", "其他", "low", 0, 0, priority=24),
}


def mask_value(value: str, type_id: str) -> str:
    """按类型策略生成脱敏预览串。"""
    meta = TYPE_META.get(type_id)
    if meta is None:
        return "*" * 6
    if meta.mask_fn:
        return meta.mask_fn(value)
    if meta.replacement:
        return meta.replacement
    n = len(value)
    h, t = meta.keep_head, meta.keep_tail
    if h + t >= n or n <= 2:
        return meta.mask_char * max(min(n, 8), 4)
    return value[:h] + meta.mask_char * (n - h - t) + (value[n - t:] if t else "")


# ==============================================================================
# 1. 校验位算法（全部本地实现，符合国家标准）
# ==============================================================================

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK_CHARS = "10X98765432"


def id_card_check(value: str) -> Optional[bool]:
    """18 位身份证校验（GB 11643-1999，ISO 7064:1983 MOD 11-2）。
    返回 True/False；None 表示不是 18 位身份证号。"""
    v = value.strip().upper()
    if not re.fullmatch(r"\d{17}[\dX]", v):
        return None
    total = sum(int(v[i]) * _ID_WEIGHTS[i] for i in range(17))
    return _ID_CHECK_CHARS[total % 11] == v[17]


def id_card_calc_check_digit(first17: str) -> str:
    total = sum(int(first17[i]) * _ID_WEIGHTS[i] for i in range(17))
    return _ID_CHECK_CHARS[total % 11]


_USCC_CHARSET = "0123456789ABCDEFGHJKLMNPQRTUWXY"  # 31 个字符，剔除 I O S V Z
_USCC_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)
_USCC_FIRST_OK = set("123456789ANY")  # 登记管理部门代码合法取值


def uscc_check(value: str) -> Optional[bool]:
    """统一社会信用代码校验（GB 32100-2015）。None 表示长度/字符集不合法。"""
    v = value.strip().upper()
    if len(v) != 18 or any(c not in _USCC_CHARSET for c in v):
        return None
    total = sum(_USCC_CHARSET.index(c) * _USCC_WEIGHTS[i] for i, c in enumerate(v[:17]))
    r = 31 - (total % 31)
    return _USCC_CHARSET[r if r < 31 else 0] == v[17]


def uscc_calc_check_digit(first17: str) -> str:
    """计算统一社会信用代码第 18 位校验码（造测试数据用）。"""
    total = sum(_USCC_CHARSET.index(c) * _USCC_WEIGHTS[i] for i, c in enumerate(first17[:17].upper()))
    r = 31 - (total % 31)
    return _USCC_CHARSET[r if r < 31 else 0]


def uscc_dept_code_ok(value: str) -> bool:
    return bool(value) and value[0].upper() in _USCC_FIRST_OK


def luhn_check(value: str) -> bool:
    """Luhn 算法（ISO/IEC 7812-1），用于银行卡号。"""
    digits = re.sub(r"\D", "", value)
    if not (12 <= len(digits) <= 19) or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def digits_of(value: str) -> str:
    return re.sub(r"\D", "", value)


# ==============================================================================
# 2. 文本归一化（保持下标映射，确保定位精准）
# ==============================================================================

_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u200e", "\u200f", "\ufeff", "\u00ad", "\u2060"}
_DASHES = {"\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212", "\uff0d", "\u30fc"}


class NormalizedText:
    """归一化文本：norm 串与 raw 串通过 index_map 一一对应（长度一致的下标映射）。"""

    __slots__ = ("raw", "norm", "_idx")

    def __init__(self, raw: str):
        chars: List[str] = []
        idx: List[int] = []
        for i, ch in enumerate(raw):
            if ch in _ZERO_WIDTH:
                continue
            o = ord(ch)
            if 0xFF01 <= o <= 0xFF5E:          # 全角 ASCII → 半角
                ch = chr(o - 0xFEE0)
            elif ch == "\u3000":
                ch = " "
            elif ch in _DASHES:
                ch = "-"
            elif ch in ("\t", "\r"):
                ch = " "
            chars.append(ch)
            idx.append(i)
        self.raw = raw
        self.norm = "".join(chars)
        self._idx = idx

    def to_raw(self, pos: int) -> int:
        """归一化下标 → 原文下标（pos 可为 len(norm)，返回 len(raw)）。"""
        if pos < 0:
            pos = 0
        if pos >= len(self._idx):
            return len(self.raw)
        return self._idx[pos]

    def to_raw_span(self, start: int, end: int) -> Tuple[int, int]:
        """归一化区间 → 原文区间（右开）。"""
        if start >= len(self._idx):
            return (len(self.raw), len(self.raw))
        raw_start = self._idx[start]
        raw_end = self._idx[end - 1] + 1 if end - 1 < len(self._idx) else len(self.raw)
        return (raw_start, raw_end)

    def raw_slice(self, start: int, end: int) -> str:
        a, b = self.to_raw_span(start, end)
        return self.raw[a:b]

    def __len__(self) -> int:
        return len(self.norm)


# ==============================================================================
# 3. 解析层：docx / pdf / txt
# ==============================================================================

@dataclass
class WordBox:
    start: int          # 块内偏移
    end: int
    x0: float
    top: float
    x1: float
    bottom: float


@dataclass
class Block:
    text: str
    block_type: str = "paragraph"   # paragraph / table_cell / textbox / header / footer
    location: str = ""
    page: Optional[int] = None
    word_boxes: List[WordBox] = field(default_factory=list)

    def bbox_for_range(self, start: int, end: int) -> Optional[Tuple[float, float, float, float]]:
        """把块内字符区间合并成一个矩形（PDF 涂黑用）。"""
        if not self.word_boxes:
            return None
        boxes = [w for w in self.word_boxes if w.end > start and w.start < end]
        if not boxes:
            return None
        return (
            min(w.x0 for w in boxes), min(w.top for w in boxes),
            max(w.x1 for w in boxes), max(w.bottom for w in boxes),
        )


@dataclass
class Document:
    source: str
    file_type: str
    blocks: List[Block]
    sha256: str = ""
    warnings: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- DOCX ---------

_DOCX_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_para_text(p) -> str:
    """段落全文：w:t 顺序拼接；tab→空格、br/cr→换行。"""
    out: List[str] = []
    for node in p.iter():
        tag = node.tag
        if tag == _DOCX_W + "t":
            out.append(node.text or "")
        elif tag == _DOCX_W + "tab":
            out.append(" ")
        elif tag in (_DOCX_W + "br", _DOCX_W + "cr"):
            out.append("\n")
    return "".join(out)


def docx_para_targets(doct) -> List[Tuple[str, str, Any]]:
    """按与 extract_docx 完全一致的顺序，枚举 (block_type, location, 段落元素)。
    改写阶段（contract_redactor）依赖此顺序保证 block_index 对齐。"""
    W = _DOCX_W

    def classify(p) -> str:
        kind, tbl_depth = "paragraph", 0
        for anc in p.iterancestors():
            if anc.tag == W + "tbl":
                tbl_depth += 1
            elif anc.tag == W + "txbxContent":
                kind = "textbox"
        if tbl_depth:
            kind = "table_cell"
        return kind

    targets: List[Tuple[str, str, Any]] = []
    counters = {"paragraph": 0, "table_cell": 0, "textbox": 0}
    for p in doct.element.body.iter(W + "p"):
        if not docx_para_text(p).strip():
            continue
        kind = classify(p)
        counters[kind] = counters.get(kind, 0) + 1
        if kind == "table_cell":
            loc = f"正文表格第 {counters['table_cell']} 个单元格段落"
        elif kind == "textbox":
            loc = f"正文文本框第 {counters['textbox']} 段"
        else:
            loc = f"正文第 {counters['paragraph']} 段"
        targets.append((kind, loc, p))

    try:
        for si, section in enumerate(doct.sections, 1):
            for kind, part in (("header", section.header), ("footer", section.footer)):
                for hi, p in enumerate(part._element.iter(W + "p"), 1):
                    if not docx_para_text(p).strip():
                        continue
                    loc = f"第 {si} 节{'页眉' if kind == 'header' else '页脚'}第 {hi} 段"
                    targets.append((kind, loc, p))
    except Exception:
        pass
    return targets


def extract_docx(path: str, include_headers: bool = True) -> Document:
    try:
        from docx import Document as DocxDocument  # type: ignore
    except ImportError:  # pragma: no cover
        raise RuntimeError("读取 .docx 需要 python-docx，请先执行： pip install python-docx")

    doct = DocxDocument(path)
    blocks: List[Block] = []
    doc_warnings: List[str] = []

    for kind, loc, p in docx_para_targets(doct):
        text = docx_para_text(p)
        blocks.append(Block(text=text, block_type=kind, location=loc))

    if not blocks:
        raise RuntimeError("文档中没有可提取的文字（可能是空文档或图片型文件）")
    return Document(source=path, file_type="docx", blocks=blocks, sha256=_sha256(path),
                    warnings=doc_warnings)


# ----------------------------------------------------------------- PDF ---------

def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF) or (0x3000 <= o <= 0x303F)


def _build_from_pdfplumber(page, page_no: int) -> Optional[Block]:
    words = page.extract_words(x_tolerance=1.5, y_tolerance=3, keep_blank_chars=False,
                               use_text_flow=False)
    if not words:
        return None
    words = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))

    lines: List[List[dict]] = []
    cur: List[dict] = []
    cur_top: Optional[float] = None
    for w in words:
        if cur_top is None or abs(w["top"] - cur_top) <= 3.0:
            cur.append(w)
            cur_top = w["top"] if cur_top is None else cur_top
        else:
            lines.append(cur)
            cur, cur_top = [w], w["top"]
    if cur:
        lines.append(cur)

    parts: List[str] = []
    boxes: List[WordBox] = []
    pos = 0
    for li, line in enumerate(lines):
        if li:
            parts.append("\n")
            pos += 1
        for wi, w in enumerate(line):
            if wi:
                prev = parts[-1] if parts else ""
                nxt = w["text"]
                sep = "" if (prev and _is_cjk(prev[-1])) or (nxt and _is_cjk(nxt[0])) else " "
                if sep:
                    parts.append(sep)
                    pos += 1
            parts.append(w["text"])
            boxes.append(WordBox(pos, pos + len(w["text"]), w["x0"], w["top"], w["x1"], w["bottom"]))
            pos += len(w["text"])
    return Block(text="".join(parts), block_type="page", location=f"第 {page_no} 页",
                 page=page_no, word_boxes=boxes)


def extract_pdf(path: str) -> Document:
    warnings: List[str] = []
    blocks: List[Block] = []

    try:
        import pdfplumber  # type: ignore
    except ImportError:
        pdfplumber = None  # type: ignore

    if pdfplumber is not None:
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages, 1):
                    try:
                        blk = _build_from_pdfplumber(page, i)
                    except Exception as exc:  # 单页失败不拖垮整体
                        warnings.append(f"第 {i} 页解析异常：{exc}")
                        blk = None
                    if blk and blk.text.strip():
                        blocks.append(blk)
                total = len(pdf.pages)
        except Exception as exc:
            raise RuntimeError(f"PDF 解析失败：{exc}")
    else:
        try:
            import pypdf  # type: ignore
        except ImportError:
            raise RuntimeError("读取 PDF 需要 pdfplumber 或 pypdf： pip install pdfplumber pypdf")
        try:
            reader = pypdf.PdfReader(path)
        except Exception as exc:
            raise RuntimeError(f"PDF 解析失败（可能已加密或损坏）：{exc}")
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:
                raise RuntimeError("PDF 已加密，请先解密或提供可提取文本的版本")
        warnings.append("未安装 pdfplumber，已降级为 pypdf：PDF 坐标信息不可用（不影响识别）")
        total = len(reader.pages)
        for i, page in enumerate(reader.pages, 1):
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                blocks.append(Block(text=t, block_type="page", location=f"第 {i} 页", page=i))

    if not blocks or len("".join(b.text for b in blocks).strip()) < 10:
        warnings.append("未提取到有效文本层：该 PDF 很可能是扫描件/图片型，需要 OCR 后才能识别")
    return Document(source=path, file_type="pdf", blocks=blocks, sha256=_sha256(path),
                    warnings=warnings)


# ----------------------------------------------------------------- TXT ---------

def extract_text_file(path: str) -> Document:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    blocks = [Block(text=line, block_type="line", location=f"第 {i} 行")
              for i, line in enumerate(raw.splitlines(), 1) if line.strip()]
    if not blocks:
        blocks = [Block(text=raw, block_type="line", location="全文")]
    return Document(source=path, file_type="txt", blocks=blocks, sha256=_sha256(path))


def load_document(path: str, include_headers: bool = True) -> Document:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return extract_docx(path, include_headers)
    if ext == ".doc":
        raise RuntimeError("不支持旧版二进制 .doc，请先另存为 .docx 或导出 PDF（本工具不联网转换）")
    if ext == ".pdf":
        return extract_pdf(path)
    if ext in (".txt", ".md", ".markdown"):
        return extract_text_file(path)
    raise RuntimeError(f"不支持的文件类型：{ext}（支持 .docx / .pdf / .txt / .md）")


# ==============================================================================
# 4. 检测层
# ==============================================================================

@dataclass
class RawMatch:
    type_id: str
    start: int              # 归一化全文下标
    end: int
    confidence: float
    reasons: List[str] = field(default_factory=list)
    value: str = ""         # 归一化后的值
    attrs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanContext:
    nt: NormalizedText
    text: str               # == nt.norm

    def before(self, start: int, n: int = 40) -> str:
        return self.text[max(0, start - n):start]

    def after(self, end: int, n: int = 40) -> str:
        return self.text[end:end + n]

    def window(self, start: int, end: int, n: int = 40) -> str:
        return self.text[max(0, start - n):start] + " " + self.text[end:end + n]

    def has_kw(self, start: int, end: int, keywords: Sequence[str], window: int = 30) -> Optional[str]:
        ctx = self.before(start, window) + "|" + self.after(end, window)
        for kw in keywords:
            if kw in ctx:
                return kw
        return None


# ------------------------------------------------------------------------------
# 4.1 通用正则检测器
# ------------------------------------------------------------------------------

@dataclass
class RegexSpec:
    type_id: str
    pattern: str
    conf_ok: float
    conf_weak: float = 0.4
    flags: int = 0
    validator: Optional[Callable[[str], Optional[bool]]] = None
    ok_reason: str = "校验位通过"
    weak_reason: str = "校验位未通过"
    keywords: Sequence[str] = ()
    kw_boost: float = 0.12
    require_keyword: bool = False
    anti_keywords: Sequence[str] = ()
    group: int = 0
    strip_chars: str = ""
    max_per_doc: Optional[int] = None
    context_chars: int = 30  # 关键词搜索窗口大小


class RegexDetector:
    def __init__(self, spec: RegexSpec):
        self.spec = spec
        self.regex = re.compile(spec.pattern, spec.flags)

    def run(self, ctx: ScanContext) -> List[RawMatch]:
        out: List[RawMatch] = []
        for m in self.regex.finditer(ctx.text):
            g = m.group(self.spec.group)
            if not g:
                continue
            s, e = m.span(self.spec.group)
            value = g.strip().strip(self.spec.strip_chars) if self.spec.strip_chars else g.strip()
            if not value:
                continue
            # 修正剥离前后缀后的区间
            lead = len(g) - len(g.lstrip())
            s += lead
            e = s + len(value)

            conf = self.spec.conf_ok
            reasons: List[str] = [f"匹配 {TYPE_META[self.spec.type_id].label} 模式"]

            if self.spec.validator is not None:
                verdict = self.spec.validator(value)
                if verdict is True:
                    conf = self.spec.conf_ok
                    reasons.append(self.spec.ok_reason)
                elif verdict is False:
                    conf = self.spec.conf_weak
                    reasons.append(self.spec.weak_reason)
                else:
                    conf = self.spec.conf_weak
                    reasons.append("格式不完整")
            else:
                reasons.append("格式匹配")

            kw = ctx.has_kw(s, e, self.spec.keywords, window=self.spec.context_chars) if self.spec.keywords else None
            if kw:
                conf += self.spec.kw_boost
                reasons.append(f"上下文含关键词「{kw}」")
            elif self.spec.require_keyword:
                continue

            if self.spec.anti_keywords:
                bad = ctx.has_kw(s, e, self.spec.anti_keywords, window=12)
                if bad:
                    conf -= 0.25
                    reasons.append(f"疑似非敏感上下文「{bad}」")

            conf = max(0.0, min(conf, 0.99))
            out.append(RawMatch(self.spec.type_id, s, e, conf, reasons, value))
            if self.spec.max_per_doc and len(out) >= self.spec.max_per_doc:
                break
        return out


# ------------------------------------------------------------------------------
# 4.2 姓名检测器（上下文标签 + 姓氏表 + 右边界校验）
# ------------------------------------------------------------------------------

NAME_LABELS = (
    "甲方", "乙方", "丙方", "丁方", "戊方", "法定代表人", "法人代表", "法人", "负责人",
    "联系人", "授权代表", "签约代表", "经办人", "承办人", "签字", "签名", "署名", "姓名",
    "受托人", "委托人", "代理人", "当事人", "开户名", "户名", "账户名", "收款人", "付款人",
    "借款人", "出借人", "保证人", "抵押人", "质权人", "员工", "劳动者", "乙方代表", "甲方代表",
    "项目负责人", "技术负责人", "项目经理", "设计师", "工程师", "顾问", "证人", "申请人",
    # 角色类（表格行：角色 + 姓名）
    "产品负责人", "业务负责人", "商务负责人", "财务负责人", "内容负责人", "运营负责人",
    "客户负责人", "客户经理", "法务负责人", "法务合规", "艺人商务", "舆情值班",
    # 表格列头
    "角色", "人员", "代表",
    # 表单字段
    "主持人", "主播", "艺人", "代言人", "嘉宾", "对接人", "接口人", "资源方",
)
# 重要：正则的 | 是**有序**匹配；长标签必须在前面，否则短标签先匹配掉
NAME_LABELS = tuple(sorted(NAME_LABELS, key=len, reverse=True))

# 常见非人名 2~4 字词（虽然首字可能是常见姓氏，但本身不是人名）
# 收录「商务 / 商业 / 权利 / 解除 / 权限 / 双确认 / 方式签署」之类
NAME_STOPWORDS = frozenset({
    "商务", "商业", "权利", "义务", "解除", "终止", "权限", "确认", "签署", "签订",
    "生效", "失效", "变更", "转让", "授权", "委托", "代理", "保证", "抵押", "质押",
    "违约", "赔偿", "损失", "费用", "价款", "金额", "付款", "收款", "结算",
    "开始", "结束", "截止", "起算", "计算", "通知", "送达", "披露", "保密",
    "书面", "口头", "电子", "网络", "线上", "线下", "现场", "当面",
    "甲方", "乙方", "丙方", "双方", "各方", "对方", "第三方", "本人",
    "公司", "企业", "单位", "部门", "小组", "团队", "中心",
    "合同", "协议", "附件", "附录", "清单", "确认单", "变更单",
    "双确认", "方式签署", "商业合作", "合法权益", "商业秘密", "个人信息",
    "不可抗力", "适用法律", "争议解决", "仲裁条款",
    "艺人商务", "舆情值班", "法务合规",
    "中国大陆", "中华人民共和国",
})
# 当事方标签（甲方/乙方…）后面经常跟的是「甲方应于…」「甲方项目经理：」，
# 因此这类标签必须紧跟冒号或括号，否则不作为人名引导词。
_PARTY_LABELS = ("甲方", "乙方", "丙方", "丁方", "戊方")
_OTHER_LABELS = tuple(x for x in NAME_LABELS if x not in _PARTY_LABELS)

_PAREN = r"(?:\s*[（(【][^)）】]{0,12}[）)】])?"
_NAME_LABEL_RE = re.compile(
    "(?:"
    + "|".join(_PARTY_LABELS) + r")\s*" + _PAREN + r"\s*[：:＝=][ \t]*"      # 当事方：必须有冒号
    + "|"
    + "(?:" + "|".join(_OTHER_LABELS) + r")\s*" + _PAREN + r"\s*[：:＝=]?[ \t]*"  # 其余：冒号可选
)
_NAME_RUN_RE = re.compile(r"[\u4e00-\u9fff]{2,8}(?:·[\u4e00-\u9fff]{1,6})*")

# 职务/角色词：这些词即使首字是常见姓氏，也不能当人名
ROLE_WORDS = (
    "经理", "总监", "主管", "主任", "秘书", "助理", "专员", "代表", "工程师", "设计师",
    "顾问", "律师", "会计", "出纳", "监理", "施工", "项目", "负责", "联系", "经办",
    "承办", "签字", "签名", "署名", "姓名", "当事", "受托", "委托", "代理", "保证",
    "抵押", "质权", "员工", "劳动", "证人", "申请", "顾问", "甲方", "乙方", "丙方",
    "双方", "公司", "单位", "部门", "小组", "团队", "中心", "科室", "应于", "应在",
    "应当", "应向", "应为", "已将", "将于", "并于", "需于", "应自", "应就",
)
_NAME_CUE_RE = re.compile(r"身份证|证件号|联系电话|手机号|电话|邮箱|住址|联系方式|先生|女士|工号|员工|护照|项目|产品|商务|内容|法务|财务|运营|客户|艺人|代言|对接|联系|渠道|邮箱|项目群|企业微信|项目负责人|产品负责人|业务负责人|商务负责人|内容负责人|法务负责人|艺人商务|舆情值班")


class PersonNameDetector:
    type_id = "PERSON_NAME"

    def __init__(self, min_confidence_without_surname: float = 0.45):
        self.min_conf_no_surname = min_confidence_without_surname

    def run(self, ctx: ScanContext) -> List[RawMatch]:
        out: List[RawMatch] = []
        text = ctx.text
        for m in _NAME_LABEL_RE.finditer(text):
            label = m.group(0).strip()
            if not label:
                continue
            strict = bool(re.search(r"[：:＝=]", label))
            pos = m.end()
            run = _NAME_RUN_RE.match(text, pos)
            if not run:
                continue
            run_txt = run.group(0)
            cue = bool(_NAME_CUE_RE.search(text[pos:pos + 40]))
            for L in (4, 3, 2):
                if L > len(run_txt):
                    continue
                name = run_txt[:L]
                rest = run_txt[L:]
                if rest and rest[0] not in NAME_BOUNDARY and not any(rest.startswith(w) for w in NAME_TAIL_WORDS):
                    continue
                # 职务/角色词不是人名，且不应再往短截（避免「项目经理」→「项目」）
                if name in NAME_LABELS or name in ORG_STOPWORDS or any(w in name for w in ROLE_WORDS):
                    break
                # 常见非人名词（商务/权利/解除 等），即便首字是常见姓氏也不算人名
                if name in NAME_STOPWORDS:
                    break
                surname_hit = name[0] in SURNAMES or name[:2] in COMPOUND_SURNAMES
                if not surname_hit:
                    break  # 姓氏不命中就别再短截了，通常是机构名或普通词
                conf = 0.78
                if not strict:
                    conf -= 0.08
                reasons = [f"标签「{label}」后出现中文人名", "姓氏命中常见姓氏表"]
                if cue and re.search(r"身份证|证件号|手机号|联系电话|住址|联系方式", text[pos + L:pos + L + 30]):
                    conf += 0.1
                    reasons.append("后续紧跟证件/联系方式")
                if not strict and not cue:
                    # 无冒号引导、又无证件/联系方式佐证 → 大概率是普通行文，降级处理
                    conf = min(conf, self.min_conf_no_surname)
                    reasons.append("无冒号引导且缺少佐证，降级")
                out.append(RawMatch("PERSON_NAME", pos, pos + L, min(conf, 0.97), reasons, name,
                                    {"label": label, "surname_hit": surname_hit, "strict": strict}))
                break
        return out


# ------------------------------------------------------------------------------
# 4.3 地址检测器（标签引导 + 行政区划分量校验）
# ------------------------------------------------------------------------------

ADDR_LABELS = ("通讯地址", "通信地址", "联系地址", "详细地址", "送达地址", "注册地址", "住所地",
               "住所", "住址", "地址", "经营场所", "所在地", "注册地", "办公地址", "邮寄地址")
# 标签后可以是 冒号 / 等号 / 换行 / 紧接（合同表格常把标签和地址分两行）
ADDR_LABEL_RE = re.compile("(?:" + "|".join(ADDR_LABELS) + r")\s*(?:[：:＝=]|\n)\s*")
ADDR_STOP = "，。；、,;；\n\t（）()【】[]：:"
# 地址后面常紧跟下一个字段名，遇到就截断，避免把整行吞进来
ADDR_NEXT_FIELD = ("邮编", "邮政编码", "电话", "手机", "邮箱", "电子邮箱", "传真",
                   "联系人", "开户", "账号", "帐号", "税号", "网址", "法定代表人")
ADDR_COMPONENTS = ("省", "自治区", "市", "区", "县", "旗", "镇", "乡", "村", "路", "街", "道",
                   "巷", "弄", "号", "栋", "幢", "楼", "单元", "室", "层", "号楼", "大院", "园区")


class AddressDetector:
    type_id = "ADDRESS"

    def run(self, ctx: ScanContext) -> List[RawMatch]:
        out: List[RawMatch] = []
        text = ctx.text
        for m in ADDR_LABEL_RE.finditer(text):
            start = m.end()
            end = start
            while end < len(text):
                if text[end] in ADDR_STOP:
                    break
                if end > start + 4 and any(text.startswith(k, end) for k in ADDR_NEXT_FIELD):
                    break
                end += 1
            value = text[start:end].strip()
            if len(value) < 6:
                continue
            # 纯数字/纯 ASCII（如「服务器地址：192.168.10.24」）不是住址
            if not re.search(r"[\u4e00-\u9fff]", value):
                continue
            comps = sum(1 for c in ADDR_COMPONENTS if c in value)
            conf = 0.55 + 0.1 * min(comps, 3)
            reasons = [f"地址标签「{m.group(0).strip()}」引导", f"含 {comps} 个行政区划/门牌要素"]
            if re.search(r"\d", value):
                conf += 0.08
                reasons.append("含门牌数字")
            out.append(RawMatch("ADDRESS", start, end, min(conf, 0.95), reasons, value,
                                {"components": comps}))

        # 无标签的显式行政区划串（省/市/区 + 路/街/号）
        bare = re.compile(
            r"[\u4e00-\u9fff]{2,7}(?:省|自治区)"
            r"[\u4e00-\u9fff]{2,10}(?:市|自治州|地区|盟)"
            r"[\u4e00-\u9fff]{2,20}?"
            r"(?:[\u4e00-\u9fff]{1,12}(?:区|县|市|旗))?"
            r"[\u4e00-\u9fff0-9]{2,30}?(?:路|街|道|巷|弄|大道|园区|工业区)"
            r"[\u4e00-\u9fff0-9\-]{0,20}?(?:号|栋|幢|号楼|室|层)"
        )
        for m in bare.finditer(text):
            value = m.group(0)
            conf = 0.6 + 0.05 * sum(1 for c in ADDR_COMPONENTS if c in value)
            out.append(RawMatch("ADDRESS", m.start(), m.end(), min(conf, 0.92),
                                ["显式行政区划+门牌结构"], value))
        return out


# ------------------------------------------------------------------------------
# 4.4 组织机构名检测器
# ------------------------------------------------------------------------------

ORG_BODY_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9（）()·&.\-'\"]")
# 左边界字：向左扩张时，遇到这些字就在此处切断（避免把「本合同由XX公司」整段吞进来）
ORG_LEFT_BOUNDARY = set("由与和或给被把以并为在及至向从对等第是为向：:，,。;；、（）[]{}<>《》\"' \t\n")
# 机构名前残留的指代词/量词（按 2 字一组，便于一次性剔除「本人」「该公」「号院」等错误前缀）
ORG_LEAD_PRONOUNS = ("本人", "该公司", "该司", "该行", "该店", "该厂", "该社", "该院", "该中心",
                     "其本", "我方", "你方", "对方", "本行", "本院", "本店", "本厂", "本社", "本中心",
                     "号院", "号楼", "号室", "号层", "号店", "号厂", "号楼", "号区")
ORG_SUFFIX_RE = re.compile(
    "|".join(re.escape(s) for s in sorted(set(ORG_SUFFIX_STRONG) | set(ORG_SUFFIX_WEAK),
                                          key=len, reverse=True))
)
_STRONG_SET = set(ORG_SUFFIX_STRONG)


def _expand_org_left(text: str, end: int) -> Tuple[int, str]:
    """以「后缀结束位置」为锚点向左扩张出完整机构名。"""
    start = end
    while start > 0 and ORG_BODY_RE.match(text[start - 1]):
        start -= 1
    cut = start
    for i in range(start, end):
        if text[i] in ORG_LEFT_BOUNDARY:
            cut = i + 1
    start = max(cut, start)
    return start, text[start:end].strip(" ·-&\"'")


class OrgNameDetector:
    type_id = "ORG_NAME"

    def run(self, ctx: ScanContext) -> List[RawMatch]:
        out: List[RawMatch] = []
        seen: Dict[Tuple[int, int], bool] = {}
        text = ctx.text
        for m in ORG_SUFFIX_RE.finditer(text):
            suffix = m.group(0)
            start, value = _expand_org_left(text, m.end())
            if len(value) < 5 or value in ORG_STOPWORDS:
                continue
            # 去掉左侧残留的虚词（如「的」「与」）
            while value and value[0] in ORG_LEFT_BOUNDARY:
                start += 1
                value = value[1:]
            # 去掉指代词/量词前缀（本人、号院 等）
            for p in ORG_LEAD_PRONOUNS:
                if value.startswith(p) and len(value) - len(p) >= 4:
                    start += len(p)
                    value = value[len(p):]
                    break
            # 去掉「数字 + 号」前缀（门牌号不是机构名的一部分：88 号曜境中心 → 曜境中心）
            m2 = re.match(r"^\d+\s*号", value)
            if m2 and len(value) - m2.end() >= 4:
                start += m2.end()
                value = value[m2.end():]
            # 去掉单独前缀「号」（门牌量词）：号曜境中心 → 曜境中心
            if value.startswith("号") and len(value) > 4 and not value[1].isdigit():
                start += 1
                value = value[1:]
            # 去掉单字前缀「本/该/其/某」+机构名（本人工作室 → 工作室）
            if value and value[0] in "本该其某贵":
                # 仅当去掉后剩余仍是合理机构名才剥
                if len(value) > 4:
                    start += 1
                    value = value[1:]
            if len(value) < 5 or value in ORG_STOPWORDS:
                continue
            if not value.endswith(suffix):
                continue
            key = (start, m.end())
            if key in seen:
                continue
            seen[key] = True
            conf = 0.88 if suffix in _STRONG_SET else 0.58
            reasons = [f"含组织机构后缀「{suffix}」"]
            if ctx.has_kw(start, m.end(), ("甲方", "乙方", "丙方", "供方", "需方", "卖方", "买方", "签约", "受托方", "委托方")):
                conf += 0.06
                reasons.append("位于合同主体上下文")
            out.append(RawMatch("ORG_NAME", start, m.end(), min(conf, 0.95), reasons, value,
                                {"suffix": suffix}))
        return out


# ------------------------------------------------------------------------------
# 4.5 检测器装配
# ------------------------------------------------------------------------------

def build_detectors(custom_specs: Sequence[RegexSpec] = ()) -> List[Any]:
    specs: List[RegexSpec] = [
        # ---------------- 身份证 ----------------
        RegexSpec(
            "ID_CARD",
            r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)",
            conf_ok=0.96, conf_weak=0.42, validator=id_card_check,
            ok_reason="GB 11643 校验位正确", weak_reason="校验位错误，疑似误识别/编造号",
            keywords=("身份证", "证件号", "身份证明", "证件号码", "公民身份"),
        ),
        RegexSpec(
            "ID_CARD_15",
            r"(?<!\d)[1-9]\d{7}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}(?!\d)",
            conf_ok=0.8, conf_weak=0.8, keywords=("身份证", "证件号", "老身份证"),
        ),
        # ---------------- 统一社会信用代码 ----------------
        # 说明：真实合同（尤其是样例/测试合同、扫描件、人工录入件）里经常出现
        # 「校验码算错」的统一社会信用代码。旧配置 conf_weak=0.3 会被 min_confidence
        # 直接滤掉，导致「统一社会信用代码：91xxxxxxxx」整行漏检。
        # 现改为：结构命中的基准分压到门槛以下（0.45），但一旦上下文出现
        # 「统一社会信用代码 / 信用代码 / 营业执照」等强标签，就提升到 0.75 以上被召回，
        # 既保证带标签的一定识别出来，又不会把无标签的 18 位随机串当成信用代码。
        RegexSpec(
            "USCC",
            r"(?<![0-9A-Za-z])[0-9ABCDEFGHJKLMNPQRTUWXY]{2}\d{6}[0-9ABCDEFGHJKLMNPQRTUWXY]{10}(?![0-9A-Za-z])",
            conf_ok=0.94, conf_weak=0.45, validator=uscc_check,
            ok_reason="GB 32100 校验码正确",
            weak_reason="校验码错误（疑似测试数据/录入有误），但符合统一社会信用代码结构",
            keywords=("统一社会信用代码", "信用代码", "统一代码", "营业执照"),
            kw_boost=0.32,
        ),
        # ---------------- 银行卡 / 账号 ----------------
        RegexSpec(
            "BANK_CARD",
            r"(?<![\d-])(?:\d{4}[ -]?){3}\d{4}(?:[ -]?\d{3})?(?!\d)",
            conf_ok=0.93, conf_weak=0.22, validator=luhn_check,
            ok_reason="Luhn 校验通过", weak_reason="Luhn 校验未通过",
            keywords=("银行卡", "卡号", "借记卡", "信用卡", "开户行", "收款账户"),
        ),
        RegexSpec(
            "BANK_CARD",
            r"(?<![\d-])\d{16,19}(?!\d)",
            conf_ok=0.9, conf_weak=0.2, validator=luhn_check,
            ok_reason="Luhn 校验通过", weak_reason="Luhn 校验未通过（可能是账号或普通数字）",
            keywords=("银行卡", "卡号", "卡号:", "储蓄卡"),
        ),
        RegexSpec(
            "BANK_ACCOUNT",
            r"(?<![\d.,])\d{9,25}(?![\d.])",
            conf_ok=0.55, conf_weak=0.35,
            keywords=("账号", "帐号", "账户", "开户", "汇款", "收款", "转账", "银行", "对公"),
            kw_boost=0.3, require_keyword=True,
            anti_keywords=("金额", "人民币", "¥", "￥", "价款", "元"),
        ),
        # ---------------- 手机 / 座机 ----------------
        RegexSpec(
            "PHONE_MOBILE",
            r"(?<!\d)1[3-9]\d{9}(?!\d)",
            conf_ok=0.88, conf_weak=0.88,
            keywords=("手机", "电话", "联系", "联系方式", "联系电话", "移动电话", "号码"),
        ),
        RegexSpec(
            "PHONE_LANDLINE",
            # 兼容四种常见写法：
            #   0755-86329871 / 0755 86329871       号码连写（7~8 位）
            #   010-8666 2188 / 010-8666-2188       号码分段（3~4 + 4 位）
            #   010 8666 2188                       区号后空格
            #   400-800-8888 / 800-800-8888         服务热线
            r"(?<!\d)"
            r"(?:"
            r"\(?0\d{2,3}\)?\s?[- ]?\s?\d{3,4}[- ]\d{4}"      # 分段号码（必须有分隔符）
            r"|\(?0\d{2,3}\)?\s?[- ]?\s?\d{7,8}(?:[- ]\d{1,6})?"  # 连写号码（可带分机）
            r"|(?:400|800)[- ]?\d{3}[- ]?\d{4}"
            r")"
            r"(?!\d)",
            conf_ok=0.55, conf_weak=0.55,
            strip_chars=" \t",
            keywords=("电话", "座机", "传真", "联系", "Tel", "总机", "客服"),
            kw_boost=0.3,
        ),
        # ---------------- 邮箱 / 邮编 ----------------
        RegexSpec(
            "EMAIL",
            r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{2,}\.[A-Za-z]{2,24}",
            conf_ok=0.9, conf_weak=0.9, strip_chars=".,;:，。；：)）",
        ),
        RegexSpec(
            "POSTCODE",
            r"(?<!\d)[1-9]\d{5}(?!\d)",
            conf_ok=0.45, conf_weak=0.45,
            keywords=("邮编", "邮政编码", "邮码", "Zip"), kw_boost=0.3, require_keyword=True,
        ),
        # ---------------- 护照 / 通行证 ----------------
        RegexSpec(
            "PASSPORT",
            r"(?<![A-Z0-9])[EW][A-Z0-9]{8}(?![A-Z0-9])",
            conf_ok=0.65, conf_weak=0.65, keywords=("护照", "passport", "PASSPORT"), kw_boost=0.2,
        ),
        RegexSpec(
            "HK_MO_TW_PERMIT",
            r"(?<![A-Z0-9])[HM]\d{10}(?![A-Z0-9])",
            conf_ok=0.6, conf_weak=0.6, keywords=("通行证", "港澳", "来往内地"), kw_boost=0.2,
        ),
        # ---------------- 纳税人识别号（非统一社会信用代码的老税号）----------------
        RegexSpec(
            "TAX_ID",
            r"(?<![0-9A-Z])[A-Z0-9]{15}(?![0-9A-Z])",
            conf_ok=0.7, conf_weak=0.7,
            keywords=("纳税人识别号", "税号", "税务登记", "国税", "地税"),
            kw_boost=0.2, require_keyword=True,
        ),
        # ---------------- 金额 ----------------
        RegexSpec(
            "AMOUNT",
            r"(?:人民币|RMB|CNY|¥|￥)?\s?\d[\d,，]*(?:\.\d{1,2})?\s?(?:万元|亿元|元|圆)(?:整)?",
            conf_ok=0.68, conf_weak=0.68,
        ),
        RegexSpec(
            "AMOUNT",
            r"(?:人民币)?\s?[壹贰叁肆伍陆柒捌玖拾佰仟万亿零角分]{3,}[元圆]?[整正]?",
            conf_ok=0.72, conf_weak=0.72,
        ),
        # 表格中只放数字的金额（无单位）—— 必须带千分位（4 位以下裸数字风险太高）
        # 关键词窗口 120 字；附带 anti_keywords 排除身份证/统一代码/年份前缀等
        RegexSpec(
            "AMOUNT",
            r"(?<![0-9.,])(?:[0-9]{1,3}(?:,\d{3})+(?:\.\d+)?)(?![0-9])",
            conf_ok=0.45, conf_weak=0.45,
            keywords=("金额", "价款", "总价", "款项", "费用", "付款", "支付",
                      "结算", "预算", "应收", "应付", "报酬", "对价",
                      "工时费", "金额（元）", "尾款", "比例", "付款节点",
                      "付款条件", "含税", "报价", "刊例", "CPM", "CPC",
                      "KOL", "媒体", "刊例价", "刊例费", "投放", "采购",
                      "服务费", "代言费", "出场费"),
            kw_boost=0.25, require_keyword=True,
            context_chars=120,
            anti_keywords=("统一社会信用代码", "证件号码", "身份证", "证件号",
                           "纳税人识别号", "银行账号", "账号", "合同编号",
                           "协议编号", "工单号", "发票号码"),
        ),
        # ---------------- 日期 ----------------
        RegexSpec(
            "DATE",
            r"(?:19|20)\d{2}\s?[年\-/.]\s?\d{1,2}\s?[月\-/.]\s?\d{1,2}\s?日?",
            conf_ok=0.62, conf_weak=0.62,
        ),
        RegexSpec(
            "DATE",
            r"(?:19|20)\d{2}\s?年\s?\d{1,2}\s?月(?:\s?\d{1,2}\s?日)?",
            conf_ok=0.62, conf_weak=0.62,
        ),
        # ---------------- 车牌 ----------------
        RegexSpec(
            "PLATE",
            r"(?<![A-Z0-9])[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领]"
            r"[A-HJ-NP-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂学警港澳领]?(?![A-Z0-9])",
            conf_ok=0.5, conf_weak=0.5, keywords=("车牌", "车辆", "号牌"), kw_boost=0.25,
        ),
        # ---------------- 微信 / QQ ----------------
        RegexSpec(
            "SOCIAL_ACCOUNT",
            r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9_\-]{5,19}(?![A-Za-z0-9])",
            conf_ok=0.35, conf_weak=0.35,
            keywords=("微信", "wechat", "WeChat", "微信号"), kw_boost=0.35, require_keyword=True,
        ),
        RegexSpec(
            "SOCIAL_ACCOUNT",
            r"(?<!\d)\d{5,12}(?!\d)",
            conf_ok=0.32, conf_weak=0.32,
            keywords=("QQ", "qq", "Q Q"), kw_boost=0.35, require_keyword=True,
        ),
        # ---------------- IP / URL ----------------
        RegexSpec(
            "IPV4",
            r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(?![\d.])",
            conf_ok=0.6, conf_weak=0.6,
        ),
        RegexSpec(
            "URL",
            r"https?://[^\s<>\"'，。；）)】\]]{4,200}|www\.[^\s<>\"'，。；）)】\]]{4,200}",
            conf_ok=0.6, conf_weak=0.6, strip_chars=".,;:，。；：)）】]",
        ),
        # ---------------- 香港 / 港澳台身份证 ----------------
        RegexSpec(
            "HK_ID_CARD",
            r"(?<![A-Z0-9])[A-Z]{1,2}\d{6}(?:[（(]\d[)）])?(?![0-9A-Za-z])",
            conf_ok=0.78, conf_weak=0.78,
            validator=lambda v: True if re.search(r"[（(]\d[)）]$", v) else None,
            ok_reason="含括号校验位", weak_reason="无括号校验位，疑似其他编号",
            keywords=("香港身份证", "香港居民", "港方", "HKID", "hkid"), kw_boost=0.15,
        ),
        # ---------------- 16 位税务登记证号 ----------------
        RegexSpec(
            "TAX_ID",
            r"(?<![0-9A-Za-z])\d{16}(?![0-9A-Za-z])",
            conf_ok=0.75, conf_weak=0.75,
            keywords=("税务登记", "税号", "国税", "地税", "纳税人"), kw_boost=0.2,
            require_keyword=True,
        ),
        # ---------------- 营业执照编号 / 注册号（15 位）----------------
        RegexSpec(
            "LICENSE_NO",
            r"(?<![\dA-Za-z])\d{15}(?![\dA-Za-z])",
            conf_ok=0.75, conf_weak=0.75,
            keywords=("营业执照", "注册号", "执照编号"), kw_boost=0.2, require_keyword=True,
            anti_keywords=("身份证", "金额", "人民币", "账号", "卡号"),
        ),
        # ---------------- 案件号 / 公文字号 ----------------
        RegexSpec(
            "CASE_NO",
            r"[（(]\s*(?:19|20)\d{2}\s*[)）][\u4e00-\u9fff]{1,10}?\d{1,8}号",
            conf_ok=0.85, conf_weak=0.85,
        ),
        RegexSpec(
            "CASE_NO",
            r"[\u4e00-\u9fff]{2,14}[〔[]\s*(?:19|20)\d{2}\s*[〕]]\s*\d{1,6}号",
            conf_ok=0.85, conf_weak=0.85,
        ),
        # ---------------- 合同 / 发票 / 订单编号 ----------------
        RegexSpec(
            "CONTRACT_NO",
            r"[A-Za-z][0-9A-Za-z\-—/]{4,28}[0-9A-Za-z]",
            conf_ok=0.72, conf_weak=0.72, strip_chars="-—/",
            keywords=("合同编号", "协议编号", "合同号", "订单号", "发票号码", "发票号",
                      "工单号", "单号", "编号"),
            kw_boost=0.15, require_keyword=True,
            anti_keywords=("邮箱", "@", "网址", "http", "www"),
        ),
        # ---------------- 密钥 / 凭据（block 级）----------------
        RegexSpec(
            "SECRET",
            r"(?:sk|pk|rk)-[A-Za-z0-9_\-]{16,}",
            conf_ok=0.9, conf_weak=0.9,
        ),
        RegexSpec(
            "SECRET",
            r"(?:AKIA|ASIA)[0-9A-Z]{16}",
            conf_ok=0.9, conf_weak=0.9,
        ),
        RegexSpec(
            "SECRET",
            r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}",
            conf_ok=0.9, conf_weak=0.9,
        ),
        RegexSpec(
            "SECRET",
            r"xox[baprs]-[A-Za-z0-9\-]{10,}",
            conf_ok=0.9, conf_weak=0.9,
        ),
        RegexSpec(
            "SECRET",
            r"-----BEGIN [A-Z ]{0,30}PRIVATE KEY-----",
            conf_ok=0.95, conf_weak=0.95,
        ),
        RegexSpec(
            "SECRET",
            r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}",
            conf_ok=0.9, conf_weak=0.9,
        ),
        RegexSpec(
            "SECRET",
            r"[A-Za-z0-9_\-/+=.]{8,}",
            conf_ok=0.7, conf_weak=0.7, group=0,
            keywords=("密码", "口令", "密钥", "secret", "SECRET", "token", "TOKEN",
                      "api_key", "apikey", "API key", "access_key", "AccessKey",
                      "authorization", "Authorization", "cookie", "session", "凭据"),
            kw_boost=0.2, require_keyword=True,
            anti_keywords=("编号", "地址", "电话", "手机", "日期"),
        ),
        # ---------------- MAC 地址（默认未启用）----------------
        RegexSpec(
            "MAC_ADDRESS",
            r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:])",
            conf_ok=0.88, conf_weak=0.88,
        ),
    ]
    specs.extend(custom_specs)
    detectors: List[Any] = [RegexDetector(s) for s in specs]
    detectors.append(PersonNameDetector())
    detectors.append(AddressDetector())
    detectors.append(OrgNameDetector())
    return detectors


# ==============================================================================
# 5. 引擎：召回 → 判别 → 消解 → 汇总
# ==============================================================================

@dataclass
class Occurrence:
    page: Optional[int]
    location: str
    block_type: str
    start: int              # 原文全文偏移
    end: int
    context: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    block_index: int = -1        # 归属块序号（改写阶段用）
    local_start: int = 0         # 块内偏移（改写阶段用）
    local_end: int = 0
    text: str = ""               # 该次出现的**真实字面文本**（可能与该实体的代表值不同）


@dataclass
class Candidate:
    cid: int
    type_id: str
    label: str
    category: str
    severity: str
    value: str
    masked: str
    confidence: float
    reasons: List[str]
    occurrences: List[Occurrence] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.occurrences)


@dataclass
class Settings:
    min_confidence: float = 0.5
    min_severity: str = "low"
    disabled: set = field(default_factory=set)
    enabled_only: Optional[set] = None
    allowlist: set = field(default_factory=set)
    extra_specs: List[RegexSpec] = field(default_factory=list)
    context_chars: int = 30
    propagate_names: bool = True   # 已确认人名在全文的其它出现处一并标记（提升表格/落款召回）
    force_enabled: set = field(default_factory=set)  # 强制启用（默认关闭的类型）


def _norm_key(value: str) -> str:
    """归一化比对键：全角转半角、去空格与分隔符、英文转大写。

    先做 NFKC 归一化，这样「９１１１０１０８ＭＡ…」与「91110108MA…」会被视为同一实体，
    不会因为录入时用了全角字符而拿到两个不同的编号。
    """
    v = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"[\s\-—_()（）]", "", v).upper()


def _resolve_overlaps(matches: List[RawMatch]) -> List[RawMatch]:
    """重叠消解：按（优先级×置信度、长度）贪心保留互不重叠的候选项。"""
    def score(m: RawMatch) -> Tuple[float, int]:
        meta = TYPE_META.get(m.type_id)
        prio = meta.priority if meta else 10
        return (prio * 100 + m.confidence * 100, m.end - m.start)

    ordered = sorted(matches, key=score, reverse=True)
    kept: List[RawMatch] = []
    for m in ordered:
        if any(not (m.end <= k.start or m.start >= k.end) for k in kept):
            continue
        kept.append(m)
    return kept


# ==============================================================================
# 5.5 实体归并 & 占位符编号
# ------------------------------------------------------------------------------
# 目标：**同一个人 / 同一个企业（含简称）在整篇合同里必须共用同一个编号**。
#       张三在第 1 段和第 30 段都要写成 [自然人姓名#1]；
#       北京星海智能科技有限公司 与其简称「星海智能」都要写成 [组织机构名称#1]。
#
# 为什么重要：如果每出现一次就换一个编号，一篇合同会冒出几十个「人1、人2……人37」，
#            审核人无法判断「人7 到底是不是刚才的人1」，脱敏稿就失去可读性。
#
# 实现要点：
#   1. 编号只跟「实体」绑定，与出现次数无关；
#   2. 编号按该实体在**文档中首次出现的位置**顺序分配（与调用方迭代顺序无关），
#      因此 detector / 改写器 / 复核页三处算出来的编号必然一致；
#   3. 组织机构的全称与简称做归并，简称来源见 `_propagate_org_aliases`。
# ==============================================================================

# 行政区划前缀（剥离后得到机构「字号」，用于把简称并到全称）
ORG_REGION_PREFIXES: Tuple[str, ...] = (
    "中华人民共和国", "中国", "中华", "全国",
    "北京", "上海", "天津", "重庆",
    "广东", "广西", "深圳", "广州", "珠海", "东莞", "佛山", "中山", "惠州",
    "江苏", "南京", "苏州", "无锡", "常州", "南通", "徐州", "扬州", "昆山",
    "浙江", "杭州", "宁波", "温州", "嘉兴", "绍兴", "金华", "台州", "义乌",
    "山东", "济南", "青岛", "烟台", "潍坊", "临沂",
    "福建", "福州", "厦门", "泉州", "漳州",
    "湖南", "长沙", "湖北", "武汉", "河南", "郑州", "洛阳",
    "河北", "石家庄", "唐山", "四川", "成都", "绵阳",
    "陕西", "西安", "安徽", "合肥", "江西", "南昌",
    "山西", "太原", "辽宁", "沈阳", "大连", "吉林", "长春",
    "黑龙江", "哈尔滨", "云南", "昆明", "贵州", "贵阳", "南宁",
    "海南", "海口", "甘肃", "兰州", "青海", "西宁",
    "宁夏", "银川", "新疆", "乌鲁木齐", "内蒙古", "呼和浩特", "西藏", "拉萨",
)

# 机构名通用后缀（强/弱后缀 + 泛化的「公司」），用于剥离出字号
ORG_GENERIC_SUFFIXES: Tuple[str, ...] = tuple(sorted(
    set(ORG_SUFFIX_STRONG) | set(ORG_SUFFIX_WEAK) | {"公司"},
    key=len, reverse=True,
))

# 剥离机构名前后缀时保留的最小字号长度（避免「中国银行」被剥成「中国」这类泛化词）
ORG_CORE_MIN = 3


# 剥离后不具区分度的「空壳」名字（不能拿来判断两家机构是否同一主体）
ORG_MEANINGLESS = set(ORG_GENERIC_SUFFIXES) | set(ORG_REGION_PREFIXES)

# 前缀按长度倒序匹配，保证「中华人民共和国」先于「中国」被剥掉
ORG_REGION_PREFIXES_SORTED: Tuple[str, ...] = tuple(
    sorted(ORG_REGION_PREFIXES, key=len, reverse=True)
)


def _strip_org_variants(name: str) -> List[str]:
    """一次剥离能得到的所有结果：去一个行政区划前缀 / 去一个机构后缀。

    前缀排在前面，`org_core` 取第一个即「先剥行政区划、再剥机构类型」，
    最符合中文机构「行政区划 + 字号 + 类型」的构词顺序。
    每种剥离只尝试**最长**的那个匹配词，避免把「上海分公司」切成「上海分」。
    """
    out: List[str] = []
    for p in ORG_REGION_PREFIXES_SORTED:
        if name.startswith(p):
            if len(name) - len(p) >= ORG_CORE_MIN:
                out.append(name[len(p):])
            break
    for suf in ORG_GENERIC_SUFFIXES:
        if name.endswith(suf):
            if len(name) - len(suf) >= ORG_CORE_MIN:
                out.append(name[: -len(suf)])
            break
    return out


def org_core(name: str) -> str:
    """取机构「字号」的规范形式（反复剥离行政区划前缀与机构类型后缀）。

    北京星海智能科技有限公司 → 星海智能科技
    中国工商银行股份有限公司   → 工商银行
    中国银行                   → 中国银行
    上海分公司                 → 上海分公司（剥成「分公司」没有区分度，故保留）
    """
    s = name
    for _ in range(3):
        v = [x for x in _strip_org_variants(s) if x not in ORG_MEANINGLESS]
        if not v:
            break
        s = v[0]
    return s


def org_core_variants(name: str, max_depth: int = 3) -> set:
    """返回机构名在**不同剥离顺序**下可能得到的全部「字号」。

    不同顺序结果不同，例如：
        中国工商银行              → 先剥前缀得「工商银行」
        中国工商银行股份有限公司    → 先剥后缀得「中国工商银行」，再剥前缀仍是「工商银行」
    因此判断两家机构是否同指一体时，比较的是「变体集合有没有交集」，
    这样与剥离顺序无关，结果更稳定。
    """
    out = {name}
    frontier = [name]
    for _ in range(max_depth):
        nxt: List[str] = []
        for s in frontier:
            for v in _strip_org_variants(s):
                if v not in out:
                    out.add(v)
                    nxt.append(v)
        frontier = nxt
        if not frontier:
            break
    return {v for v in out if len(v) >= ORG_CORE_MIN and v not in ORG_MEANINGLESS}


def _org_same_entity(a: str, b: str) -> bool:
    """判断两个机构名是否指向同一主体（全称 vs 简称）。"""
    va, vb = org_core_variants(a), org_core_variants(b)
    if not va or not vb:
        return False
    for x in va:
        for y in vb:
            if x == y:
                return True
            short, long_ = (x, y) if len(x) <= len(y) else (y, x)
            # 只认「字号前缀」关系（星海智能 ⊂ 星海智能科技），
            # 不用「任意子串」，避免把「工商」误并到别的机构上。
            if len(long_) >= 4 and long_.startswith(short):
                return True
    return False


def build_entity_number_map(
    items: Iterable[Dict[str, Any]],
) -> Dict[Tuple[str, str], int]:
    """为每个「实体」分配固定编号。

    :param items: detector 报告里的 per-entity 条目（需含 type / value / occurrences）
    :return: ``{(type_id, _norm_key(value)): 编号}``

    同一个实体的不同写法（全称/简称）都会指向同一个编号。
    编号按实体首次出现位置，在各自类型内独立从 1 开始。
    """
    entries: List[Tuple[int, str, str]] = []
    for it in items or ():
        t = it.get("type") or ""
        key = _norm_key(it.get("value") or "")
        if not t or not key:
            continue
        starts = []
        for o in (it.get("occurrences") or ()):
            off = o.get("offset")
            if off:
                starts.append(off[0])
        entries.append((min(starts) if starts else 0, t, key))
    if not entries:
        return {}

    keys: List[Tuple[str, str]] = list(dict.fromkeys((t, k) for _, t, k in entries))
    first_pos: Dict[Tuple[str, str], int] = {}
    for p, t, k in sorted(entries, key=lambda x: x[0]):
        first_pos.setdefault((t, k), p)

    parent: Dict[Tuple[str, str], Tuple[str, str]] = {k: k for k in keys}

    def find(x: Tuple[str, str]) -> Tuple[str, str]:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a: Tuple[str, str], b: Tuple[str, str]) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # 根取「首次出现更早」的一个，保证结果稳定
        if first_pos.get(ra, 0) > first_pos.get(rb, 0):
            ra, rb = rb, ra
        parent[rb] = ra

    # 组织机构：全称 / 简称归并
    org_keys = [k for k in keys if k[0] == "ORG_NAME"]
    for i in range(len(org_keys)):
        for j in range(i + 1, len(org_keys)):
            if _org_same_entity(org_keys[i][1], org_keys[j][1]):
                union(org_keys[i], org_keys[j])

    # 编号：同一实体取「最早出现位置」，在类型内按位置排序后从 1 递增
    root_first: Dict[Tuple[str, str], int] = {}
    for k in keys:
        r = find(k)
        p = first_pos.get(k, 0)
        if r not in root_first or p < root_first[r]:
            root_first[r] = p

    by_type: Dict[str, List[Tuple[int, Tuple[str, str]]]] = {}
    for r, p in root_first.items():
        by_type.setdefault(r[0], []).append((p, r))
    numbers: Dict[Tuple[str, str], int] = {}
    for t, lst in by_type.items():
        lst.sort(key=lambda x: x[0])
        for idx, (_p, root) in enumerate(lst, 1):
            numbers[(t, root)] = idx

    return {k: numbers[(k[0], find(k))] for k in keys}


class EntityNumberer:
    """实体 → 编号 的统一入口（detector / 改写器 / 复核页三处共用）。

    只要三处都拿同一份 detector 报告来构造，编号就一定一致。
    """

    def __init__(self, items: Optional[Iterable[Dict[str, Any]]] = None):
        self._map: Dict[Tuple[str, str], int] = build_entity_number_map(items or ())
        self._next: Dict[str, int] = {}
        for (t, _k), n in self._map.items():
            if n > self._next.get(t, 0):
                self._next[t] = n

    def number(self, type_id: str, value: str) -> int:
        """取得（必要时分配）某实体在本类型内的编号。"""
        key = (type_id, _norm_key(value))
        n = self._map.get(key)
        if n is None:
            # 兜底：正常不会走到这里（报告里必有该实体），
            # 万一漏了也保证「同名同号、异名异号」。
            n = self._next.get(type_id, 0) + 1
            self._next[type_id] = n
            self._map[key] = n
        return n

    def placeholder(self, type_id: str, value: str, label: str) -> str:
        return placeholder_text(label, self.number(type_id, value))

    def entities(self) -> List[Dict[str, Any]]:
        """按 (类型, 编号) 汇总，便于写入 mapping 供人核对。"""
        out = [
            {"type": t, "key": k, "number": n}
            for (t, k), n in self._map.items()
        ]
        out.sort(key=lambda x: (x["type"], x["number"]))
        return out


def placeholder_text(label: str, number: int) -> str:
    """占位符的字面形式：``[组织机构名称#1]``。

    全工程只有这一处定义格式，detector / 改写器 / 还原器必须保持一致。
    """
    return f"[{label}#{number}]"


PLACEHOLDER_RE = re.compile(r"\[([^\[\]#\s]{1,20})#(\d{1,6})\]")


def parse_placeholder(value: str) -> Optional[Tuple[str, int]]:
    """解析占位符，返回 (label, number)；不是占位符则返回 None。"""
    m = PLACEHOLDER_RE.fullmatch((value or "").strip())
    if not m:
        return None
    return m.group(1), int(m.group(2))


class DetectorEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.detectors = build_detectors(settings.extra_specs)
        enable = set(TYPE_META) | set(getattr(s, "type_id", "") for s in settings.extra_specs)
        force = settings.force_enabled

        def _on(t: str) -> bool:
            meta = TYPE_META.get(t)
            return (meta.enabled if meta else True) or t in force

        self.active_types = {
            t for t in enable
            if t not in settings.disabled
            and (settings.enabled_only is None or t in settings.enabled_only)
            and _on(t)
        }
        # 自定义类型可能不在 TYPE_META 中，补一个默认元信息
        for s in settings.extra_specs:
            if s.type_id not in TYPE_META:
                TYPE_META[s.type_id] = TypeMeta(s.type_id, getattr(s, "label", s.type_id),
                                                "自定义", getattr(s, "severity", "medium"),
                                                2, 2, priority=50)

    # ------------------------------------------------------------------ 扫描 --
    def scan_document(self, doc: Document) -> List[Candidate]:
        blocks = doc.blocks
        # 拼全文 + 记录块区间
        parts: List[str] = []
        spans: List[Tuple[int, int, Block]] = []
        starts: List[int] = []
        pos = 0
        for b in blocks:
            t = b.text.rstrip("\n")
            parts.append(t)
            spans.append((pos, pos + len(t), b))
            starts.append(pos)
            pos += len(t) + 1
        full_raw = "\n".join(parts)

        nt = NormalizedText(full_raw)
        ctx = ScanContext(nt, nt.norm)

        raw_matches: List[RawMatch] = []
        for det in self.detectors:
            if getattr(det, "type_id", getattr(getattr(det, "spec", None), "type_id", "")) not in self.active_types:
                continue
            try:
                raw_matches.extend(det.run(ctx))
            except Exception as exc:  # 单个检测器异常不影响整体
                sys.stderr.write(f"[warn] 检测器 {type(det).__name__} 异常：{exc}\n")

        if self.settings.propagate_names:
            raw_matches.extend(self._propagate_names(raw_matches, ctx))
            if "ORG_NAME" in self.active_types:
                raw_matches.extend(self._propagate_org_aliases(raw_matches, ctx))

        return self._postprocess(raw_matches, nt, blocks, starts, spans, full_raw)

    @staticmethod
    def _propagate_org_aliases(matches: List[RawMatch],
                               ctx: ScanContext) -> List[RawMatch]:
        """组织机构简称对齐。

        合同首部常写「北京星海智能科技有限公司（以下简称"星海智能"）」，
        正文则一律使用简称。若只识别全称，简称就会漏检/或被当成别的主体，
        导致同一家公司在脱敏稿里拿到不同编号。

        这里为「已确认的机构全称」补充两类简称命中：
          1. 紧跟全称之后的显式定义 ``（以下简称"X"）``；
          2. 由全称推算的「字号」（去掉行政区划与通用后缀），如 星海智能、星海智能科技公司。
        命中只作为候选加入，最终编号由 build_entity_number_map 归并到全称。
        """
        text = ctx.text
        orgs = [m for m in matches if m.type_id == "ORG_NAME" and len(m.value) >= 5]
        if not orgs:
            return []

        blockers = list(matches)
        seen: set = set()
        extra: List[RawMatch] = []

        def _covered(s: int, e: int) -> bool:
            return any(m.start <= s and e <= m.end for m in blockers)

        for om in orgs:
            alts: List[Tuple[str, float, str]] = []
            # 1) 显式简称定义（限定在全称之后的 40 字窗口内）
            tail = text[om.end: om.end + 40]
            for dm in re.finditer(
                r"[（(]\s*(?:以下|下)?\s*(?:简称|称)\s*[:：]?\s*[「“\"'‘]?"
                r"([\u4e00-\u9fffA-Za-z0-9]{2,20})\s*[」”\"'’]?\s*[)）]",
                tail,
            ):
                alts.append((dm.group(1), 0.9, "显式简称定义"))
            # 2) 字号 / 字号+公司
            core = org_core(_norm_key(om.value))
            if len(core) >= 4:
                alts.append((core, 0.72, "字号"))
                alts.append((core + "公司", 0.7, "字号+公司"))
            elif len(core) >= 2:
                alts.append((core, 0.66, "字号"))

            full_key = _norm_key(om.value)
            for alt, conf, why in alts:
                if not alt or _norm_key(alt) == full_key:
                    continue
                start = 0
                while True:
                    i = text.find(alt, start)
                    if i < 0:
                        break
                    start = i + 1
                    e = i + len(alt)
                    # 边界：只对「字母/数字」做邻接检查（避免切出半个英文词）。
                    # 中文词间没有空格，不能再要求邻字不是汉字，否则
                    # 「向星海智能提交报告」这类正常行文会被误杀。
                    if i > 0 and re.match(r"[A-Za-z0-9]", text[i - 1]):
                        continue
                    if e < len(text) and re.match(r"[A-Za-z0-9]", text[e]):
                        continue
                    if (i, e) in seen or _covered(i, e):
                        continue
                    seen.add((i, e))
                    extra.append(RawMatch(
                        "ORG_NAME", i, e, conf,
                        [f"与「{om.value}」同指的{why}"], text[i:e],
                        {"alias_of": om.value},
                    ))
        return extra

    @staticmethod
    def _propagate_names(matches: List[RawMatch], ctx: ScanContext) -> List[RawMatch]:
        """人名没有可校验的固定模式，靠标签只能抓到带标签的那几处。
        对已高置信确认的人名，回扫全文把其它出现位置也标出来（常见于表格、落款、账号名）。"""
        confirmed = {m.value for m in matches
                     if m.type_id == "PERSON_NAME" and m.confidence >= 0.7 and 2 <= len(m.value) <= 4}
        extra: List[RawMatch] = []
        if not confirmed:
            return extra
        # 只有「可信的」既有匹配才占位；低分姓名候选不该挡住传播
        blockers = [m for m in matches
                    if not (m.type_id == "PERSON_NAME" and m.confidence < 0.6)]
        for name in confirmed:
            start = 0
            while True:
                i = ctx.text.find(name, start)
                if i < 0:
                    break
                start = i + 1
                end = i + len(name)
                if any(m.start <= i and end <= m.end for m in blockers):
                    continue
                extra.append(RawMatch("PERSON_NAME", i, end, 0.72,
                                      [f"与已确认人名「{name}」一致的另一处出现"], name,
                                      {"propagated": True}))
        return extra

    # -------------------------------------------------------------- 后处理 --
    def _postprocess(self, matches: List[RawMatch], nt: NormalizedText,
                     blocks: List[Block], starts: List[int],
                     spans: List[Tuple[int, int, Block]], full_raw: str) -> List[Candidate]:
        st = self.settings

        # 1) 类型过滤
        matches = [m for m in matches if m.type_id in self.active_types]

        # 2) 占位符 / 白名单过滤
        filtered: List[RawMatch] = []
        for m in matches:
            raw_value = nt.raw_slice(m.start, m.end)
            # 400 / 800 服务热线单独放行（如 800 800 8888 只含 0 和 8，会被误判成占位数据）
            if is_placeholder(raw_value) and not (
                    m.type_id == "PHONE_LANDLINE" and HOTLINE_RE.match(raw_value.strip())):
                continue
            if _norm_key(raw_value) in {_norm_key(a) for a in st.allowlist}:
                continue
            m.value = raw_value
            filtered.append(m)

        # 3) 置信度门槛
        filtered = [m for m in filtered if m.confidence >= st.min_confidence]

        # 4) 重叠消解
        filtered = _resolve_overlaps(filtered)

        # 5) 严重度过滤
        filtered = [
            m for m in filtered
            if SEVERITY_ORDER.get(TYPE_META.get(m.type_id, TypeMeta(m.type_id, "", "", "low")).severity, 1)
            >= SEVERITY_ORDER.get(st.min_severity, 1)
        ]

        # 6) 分组聚合
        groups: Dict[Tuple[str, str], Candidate] = {}
        order: List[Candidate] = []
        cid = 0
        for m in filtered:
            meta = TYPE_META[m.type_id]
            key = (m.type_id, _norm_key(m.value))
            cand = groups.get(key)
            if cand is None:
                cid += 1
                cand = Candidate(cid, m.type_id, meta.label, meta.category, meta.severity,
                                 m.value, mask_value(m.value, m.type_id),
                                 round(m.confidence, 3), list(dict.fromkeys(m.reasons)))
                groups[key] = cand
                order.append(cand)
            else:
                cand.confidence = round(max(cand.confidence, m.confidence), 3)
                for r in m.reasons:
                    if r not in cand.reasons:
                        cand.reasons.append(r)

            # 定位：归一化偏移 → 原文偏移 → 归属块
            rs, re_ = nt.to_raw_span(m.start, m.end)
            bi = bisect.bisect_right(starts, rs) - 1
            if bi < 0:
                bi = 0
            b_start, b_end, block = spans[bi]
            local_s = max(0, rs - b_start)
            local_e = min(len(block.text), max(local_s, re_ - b_start))
            left = full_raw[max(0, rs - st.context_chars):rs].replace("\n", " ")
            right = full_raw[re_:re_ + st.context_chars].replace("\n", " ")
            context = f"{left}【{m.value}】{right}"
            cand.occurrences.append(Occurrence(
                page=block.page, location=block.location, block_type=block.block_type,
                start=rs, end=re_, context=context, text=full_raw[rs:re_],
                bbox=block.bbox_for_range(local_s, local_e),
                block_index=bi, local_start=local_s, local_end=local_e,
            ))

        # 7) 姓名与身份证号互相增强（跨行也能认出「张三 / 身份证号：...」）
        id_spans = [m for m in filtered if m.type_id in ("ID_CARD", "ID_CARD_15")]
        if id_spans:
            for cand in order:
                if cand.type_id != "PERSON_NAME":
                    continue
                for occ in cand.occurrences:
                    if any(abs(o - occ.start) <= 60 for o in
                           [nt.to_raw_span(m.start, m.end)[0] for m in id_spans]):
                        cand.confidence = round(min(cand.confidence + 0.08, 0.99), 3)
                        if "邻近身份证号，佐证为自然人" not in cand.reasons:
                            cand.reasons.append("邻近身份证号，佐证为自然人")
                        break

        order.sort(key=lambda c: (-SEVERITY_ORDER.get(c.severity, 1), -c.confidence, -c.count, c.cid))
        for i, c in enumerate(order, 1):
            c.cid = i
        return order


# ==============================================================================
# 6. 输出层
# ==============================================================================

def build_report(doc: Document, candidates: List[Candidate], settings: Settings) -> Dict[str, Any]:
    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    total_occ = 0
    for c in candidates:
        by_type[c.type_id] = by_type.get(c.type_id, 0) + c.count
        by_severity[c.severity] = by_severity.get(c.severity, 0) + c.count
        total_occ += c.count
    return {
        "schema": "contract-sensitive-candidates/v1",
        "engine": {"name": ENGINE_NAME, "version": __version__, "mode": "offline"},
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            "path": os.path.abspath(doc.source),
            "name": os.path.basename(doc.source),
            "type": doc.file_type,
            "sha256": doc.sha256,
            "blocks": len(doc.blocks),
            "chars": len(doc.text),
        },
        "settings": {
            "min_confidence": settings.min_confidence,
            "min_severity": settings.min_severity,
            "disabled_types": sorted(settings.disabled),
        },
        "warnings": doc.warnings,
        "summary": {
            "candidate_types": len(candidates),
            "occurrences": total_occ,
            "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
            "by_severity": by_severity,
        },
        "items": [
            {
                "id": c.cid,
                "type": c.type_id,
                "label": c.label,
                "category": c.category,
                "severity": c.severity,
                "value": c.value,
                "masked": c.masked,
                "confidence": c.confidence,
                "count": c.count,
                "reasons": c.reasons,
                "occurrences": [
                    {
                        "page": o.page,
                        "location": o.location,
                        "block_type": o.block_type,
                        "offset": [o.start, o.end],
                        "block_index": o.block_index,
                        "local_offset": [o.local_start, o.local_end],
                        "bbox": list(o.bbox) if o.bbox else None,
                        "context": o.context,
                        # 真实字面文本：同一实体的不同写法（全称/简称、带空格/不带空格）
                        # 靠它才能精确还原，不能只用实体的代表值。
                        "text": o.text or "",
                    }
                    for o in c.occurrences
                ],
            }
            for c in candidates
        ],
    }


def write_json(report: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def write_csv(report: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "类型", "类型名称", "归类", "严重度", "原文值", "脱敏预览",
                    "置信度", "出现次数", "位置", "页码", "上下文", "判定依据"])
        for it in report["items"]:
            for i, o in enumerate(it["occurrences"], 1):
                w.writerow([
                    it["id"], it["type"], it["label"], it["category"],
                    SEVERITY_LABEL.get(it["severity"], it["severity"]),
                    it["value"], it["masked"], it["confidence"], it["count"],
                    o["location"], o["page"] or "", o["context"],
                    "；".join(it["reasons"]) if i == 1 else "",
                ])


def write_mapping(report: Dict[str, Any], path: str) -> Dict[str, Any]:
    """写入「脱敏 ↔ 原文」双向映射文件，供还原模式按字符占位符回填原文。

    输出 schema（contract-mapping/v1）：
        {
          "version": 1,
          "schema": "contract-mapping/v1",
          "engine": {...},
          "source": {path, sha256, type, ...},
          "generated_at": ...,
          "items": [
            {type, label, severity, category,
             original, placeholder, masked,
             page, block_index, block_location,
             start, end, bbox, confidence}
          ]
        }

    设计原则
    --------
    1. 每个 occurrence 一条记录（不是 per candidate 聚合），保证唯一可定位。
    2. placeholder 是 redactor 在「还原模式」下真正写入 docx 的字符串，
       形如 "[自然人姓名#1]"，与原文任何 token 都不会混淆，还原器找它替换即可。
    3. **同一个实体（同一个人/企业，含简称）的所有 occurrence 共用同一个 placeholder**，
       编号由 build_entity_number_map 统一分配，与改写器、复核页完全一致。
    4. masked 字段保留 detector 默认的格式掩码（如 "张**"），
       仅供人类阅读 + 对老版本 redactor 兼容。
    """
    numberer = EntityNumberer(report["items"])
    items: List[Dict[str, Any]] = []
    for it in report["items"]:
        placeholder_text_ = numberer.placeholder(it["type"], it["value"], it["label"])
        for o in it["occurrences"]:
            items.append({
                "type": it["type"],
                "label": it["label"],
                "severity": it["severity"],
                "category": it["category"],
                # 还原时写入文档的字面文本：取「该次出现的真实文本」，
                # 这样同一实体的不同写法（全称/简称）都能各自还原正确。
                "original": o.get("text") or it["value"],
                "entity_value": it["value"],
                "placeholder": placeholder_text_,
                "masked": it.get("masked") or it["value"],
                "page": o.get("page"),
                "block_index": o.get("block_index"),
                "block_location": o.get("location"),
                "start": o["offset"][0],
                "end": o["offset"][1],
                "bbox": o.get("bbox"),
                "confidence": it["confidence"],
            })

    # 实体级汇总：一眼看清「一共几种主体、各自用了哪个编号」
    label_by_type = {it["type"]: it["label"] for it in report["items"]}
    counts: Dict[Tuple[str, int], int] = {}
    for rec in items:
        parsed = parse_placeholder(rec["placeholder"])
        if parsed:
            counts[(rec["type"], parsed[1])] = counts.get((rec["type"], parsed[1]), 0) + 1
    entities = [
        {
            "type": t,
            "label": label_by_type.get(t, t),
            "number": n,
            "placeholder": placeholder_text(label_by_type.get(t, t), n),
            "occurrences": c,
        }
        for (t, n), c in sorted(counts.items(), key=lambda x: (x[0][0], x[0][1]))
    ]

    payload = {
        "version": 1,
        "schema": "contract-mapping/v1",
        "engine": report.get("engine", {"name": ENGINE_NAME, "version": __version__, "mode": "offline"}),
        "source": report.get("source", {}),
        "generated_at": report.get("generated_at"),
        "entities": entities,
        "items": items,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def build_annotated_text(doc: Document, candidates: List[Candidate], full_raw: str) -> str:
    marks: List[Tuple[int, int, str]] = []
    for c in candidates:
        for o in c.occurrences:
            marks.append((o.start, o.end, f"<<{c.type_id}#{c.cid}|{c.confidence}|{c.masked}>>"))
    marks.sort(key=lambda x: x[0], reverse=True)
    out = full_raw
    for s, e, tag in marks:
        out = out[:s] + tag + out[e:]
    return out


def build_masked_text(doc: Document, candidates: List[Candidate], full_raw: str) -> str:
    marks = [(o.start, o.end, c.masked) for c in candidates for o in c.occurrences]
    marks.sort(key=lambda x: x[0], reverse=True)
    out = full_raw
    for s, e, rep in marks:
        out = out[:s] + rep + out[e:]
    return out


_REVIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>合同脱敏复核 · __TITLE__</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--line:#e5e7eb;--txt:#1f2328;--sub:#6b7280;
--hi:#dc2626;--md:#d97706;--lo:#0284c7;--acc:#2563eb}
*{box-sizing:border-box}
body{margin:0;padding:20px;background:var(--bg);color:var(--txt);font:14px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1280px;margin:0 auto}
h1{font-size:19px;font-weight:500;margin:0 0 4px}
.meta{color:var(--sub);font-size:12px;margin-bottom:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:14px}
.bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.sevbtn{border:1px solid var(--line);background:#fff;border-radius:999px;padding:3px 14px;font-size:13px;cursor:pointer;color:var(--txt)}
.sevbtn.on{color:#fff}
.sevbtn.on[data-sev="all"]{background:#334155}
.sevbtn.on[data-sev="high"]{background:var(--hi)}
.sevbtn.on[data-sev="medium"]{background:var(--md)}
.sevbtn.on[data-sev="low"]{background:var(--lo)}
.cat{font-size:12px;color:var(--sub);margin:10px 0 6px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:999px;padding:3px 12px;font-size:13px;cursor:pointer;user-select:none;background:#fff}
.chip .dot{width:8px;height:8px;border-radius:50%}
.chip input{display:none}
.chip.on[data-sev="high"]{border-color:var(--hi);background:#fef2f2}
.chip.on[data-sev="medium"]{border-color:var(--md);background:#fffbeb}
.chip.on[data-sev="low"]{border-color:var(--lo);background:#f0f9ff}
.chip.off{opacity:.45}
.mini{font-size:12px;color:var(--acc);cursor:pointer}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.panel h3{margin:0 0 8px;font-size:13px;font-weight:500;color:var(--sub)}
.doc{white-space:pre-wrap;word-break:break-word;line-height:2;font-size:13px}
.loc{color:var(--acc);font-size:12px;margin:12px 0 2px;font-weight:500}
mark{padding:0 2px;border-radius:3px;color:#1f2328}
mark.high{background:#fecaca}
mark.medium{background:#fde68a}
mark.low{background:#bae6fd}
.off{border-bottom:1px dotted #bbb;color:#9ca3af}
button.primary{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:9px 22px;font-size:14px;cursor:pointer}
button.primary:disabled{background:#94a3b8;cursor:default}
#result{font-size:13px}
#result code{background:#f1f5f9;padding:1px 5px;border-radius:4px}
textarea{width:100%;height:120px;font:12px ui-monospace,Menlo,Consolas,monospace;margin-top:8px}
.warn{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;padding:8px 12px;border-radius:8px;margin-bottom:12px;font-size:13px}
@media(max-width:900px){.compare{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<h1>合同脱敏 · 人工复核与确认</h1>
<div class="meta">__META__</div>
<div id="warns"></div>
<div class="card">
  <div class="bar">
    <strong style="font-size:13px">按严重度筛选</strong>
    <span class="sevbtn on" data-sev="all">全部</span>
    <span class="sevbtn" data-sev="high">高</span>
    <span class="sevbtn" data-sev="medium">中</span>
    <span class="sevbtn" data-sev="low">低</span>
    <span style="flex:1"></span>
    <span class="mini" id="selAll">全选类型</span>
    <span class="mini" id="selNone">清空</span>
  </div>
  <div id="types"></div>
</div>
<div class="compare">
  <div class="panel"><h3>脱敏前（原文，高亮 = 将被脱敏，虚线 = 本次不处理）</h3><div id="left" class="doc"></div></div>
  <div class="panel"><h3>脱敏后（预览，随选择实时变化）</h3><div id="right" class="doc"></div></div>
</div>
<div class="card">
  <div class="bar">
    <button class="primary" id="go">确认并执行脱敏改写</button>
    <span id="stat" style="font-size:13px;color:var(--sub)"></span>
  </div>
  <div id="result"></div>
</div>
<div class="meta">本页由 contract_sensitive_detector.py 本地生成：无外部资源、无网络请求（服务模式仅监听 127.0.0.1）。</div>
<script>
const DATA = __PAYLOAD__;
const API = __API__;

let enabled = new Set(DATA.types.map(function(t){return t.id;}));
let sev = 'all';

function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function active(m){return enabled.has(m.t) && (sev==='all' || m.sev===sev);}

function renderTypes(){
  const box = document.getElementById('types'); box.innerHTML='';
  const cats = {};
  DATA.types.forEach(function(t){ (cats[t.cat] = cats[t.cat]||[]).push(t); });
  const rank = {high:0, medium:1, low:2};
  Object.keys(cats).forEach(function(cat){
    const d = document.createElement('div'); d.className='cat'; d.textContent=cat; box.appendChild(d);
    const chips = document.createElement('div'); chips.className='chips';
    cats[cat].slice().sort(function(a,b){return rank[a.sev]-rank[b.sev];}).forEach(function(t){
      const c = document.createElement('label');
      c.className = 'chip ' + (enabled.has(t.id) ? ('on') : 'off');
      c.setAttribute('data-sev', t.sev);
      c.innerHTML = '<input type="checkbox" '+(enabled.has(t.id)?'checked':'')+'>'+
        '<span class="dot" style="background:var(--'+t.sev+')"></span>'+esc(t.label)+
        ' <span style="color:var(--sub)">'+t.count+'</span>';
      c.querySelector('input').addEventListener('change', function(ev){
        if(ev.target.checked){enabled.add(t.id);} else {enabled.delete(t.id);}
        render();
      });
      chips.appendChild(c);
    });
    box.appendChild(chips);
  });
}

function render(){
  document.querySelectorAll('.sevbtn').forEach(function(b){
    b.classList.toggle('on', b.getAttribute('data-sev')===sev);
  });
  renderTypes();
  const left=[], right=[]; let n=0;
  DATA.blocks.forEach(function(b){
    left.push('<div class="loc">'+esc(b.loc)+'</div>');
    right.push('<div class="loc">'+esc(b.loc)+'</div>');
    const ms = b.marks.slice().sort(function(a,c){return a.s-c.s;});
    let pos=0, L='', R='';
    ms.forEach(function(m){
      const ls=m.s-b.start, le=m.e-b.start;
      if(ls<pos) return;
      L += esc(b.text.slice(pos,ls)); R += esc(b.text.slice(pos,ls));
      if(active(m)){
        n++;
        L += '<mark class="'+m.sev+'" title="'+esc(m.label)+' · 置信度 '+m.conf+'">'+esc(b.text.slice(ls,le))+'</mark>';
        R += '<mark class="'+m.sev+'">'+esc(m.masked)+'</mark>';
      } else {
        L += '<span class="off" title="未勾选，本次不脱敏">'+esc(b.text.slice(ls,le))+'</span>';
        R += esc(b.text.slice(ls,le));
      }
      pos = le;
    });
    L += esc(b.text.slice(pos)); R += esc(b.text.slice(pos));
    left.push(L||'&nbsp;'); right.push(R||'&nbsp;');
  });
  document.getElementById('left').innerHTML = left.join('');
  document.getElementById('right').innerHTML = right.join('');
  document.getElementById('stat').textContent = '将脱敏 '+n+' 处，涉及 '+enabled.size+' 类';
}

document.querySelectorAll('.sevbtn').forEach(function(b){
  b.addEventListener('click', function(){ sev = b.getAttribute('data-sev'); render(); });
});
document.getElementById('selAll').addEventListener('click', function(){
  enabled = new Set(DATA.types.map(function(t){return t.id;})); render();
});
document.getElementById('selNone').addEventListener('click', function(){
  enabled = new Set(); render();
});

function selection(){
  const on = DATA.types.filter(function(t){return enabled.has(t.id);});
  let minSev = 'high';
  if (on.some(function(t){return t.sev==='low';})) minSev='low';
  else if (on.some(function(t){return t.sev==='medium';})) minSev='medium';
  return {source: DATA.source, enabled_types: on.map(function(t){return t.id;}),
          min_confidence: DATA.min_confidence, min_severity: minSev};
}

document.getElementById('go').addEventListener('click', async function(){
  const sel = selection();
  const out = document.getElementById('result');
  if(!sel.enabled_types.length){ out.innerHTML='<span style="color:#dc2626">未选择任何类型，请先勾选。</span>'; return; }
  if(API){
    const btn=document.getElementById('go'); btn.disabled=true;
    out.textContent='正在执行脱敏改写…';
    try{
      const r = await fetch(API+'/apply', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(sel)});
      const j = await r.json();
      if(j.ok){
        out.innerHTML='完成：输出 <a href="'+j.download+'"><code>'+esc(j.output)+'</code></a>（替换 '+j.applied+' 处，跳过 '+j.skipped+' 处）';
      } else {
        out.innerHTML='<span style="color:#dc2626">失败：'+esc(j.error||'未知错误')+'</span>';
      }
    }catch(e){ out.innerHTML='<span style="color:#dc2626">请求失败：'+esc(String(e))+'</span>'; }
    btn.disabled=false;
  } else {
    const blob = new Blob([JSON.stringify(sel,null,2)], {type:'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = DATA.selName; a.click();
    out.innerHTML = '已下载选择文件 <code>'+esc(DATA.selName)+'</code>。静态页面不能直接执行改写，请运行下面命令（或用 serve 模式在本页一键执行）：'+
      '<textarea readonly>'+esc(DATA.cmd)+'</textarea>';
  }
});

DATA.warnings.forEach(function(w){
  const d=document.createElement('div'); d.className='warn'; d.textContent=w;
  document.getElementById('warns').appendChild(d);
});
render();
</script>
</div></body></html>
"""


def _build_review_payload(report: "Dict[str, Any]", doc: Document, full_raw: str,
                          out_hint: str) -> Dict[str, Any]:
    """把报告转成复核页所需的最小 JSON（块级文本 + 命中区间）。"""
    buckets: Dict[int, List[Dict[str, Any]]] = {}
    types: Dict[str, Dict[str, Any]] = {}
    for it in report["items"]:
        t = types.setdefault(it["type"], {
            "id": it["type"], "label": it["label"], "cat": it["category"],
            "sev": it["severity"], "count": 0,
        })
        t["count"] += it["count"]
        for o in it["occurrences"]:
            buckets.setdefault(o["block_index"], []).append({
                "s": o["offset"][0], "e": o["offset"][1], "t": it["type"],
                "sev": it["severity"], "label": it["label"],
                "masked": it["masked"], "conf": it["confidence"],
            })

    blocks: List[Dict[str, Any]] = []
    pos = 0
    for b in doc.blocks:
        text = b.text.rstrip("\n")
        blocks.append({"start": pos, "loc": b.location, "text": text,
                       "marks": buckets.get(len(blocks), [])})
        pos += len(text) + 1

    stem = os.path.splitext(os.path.basename(doc.source))[0]
    ext = os.path.splitext(doc.source)[1].lower() or ".txt"
    all_types = ",".join(types)
    return {
        "source": os.path.abspath(doc.source),
        "min_confidence": report["settings"]["min_confidence"],
        "selName": f"{stem}.selection.json",
        "cmd": (f'python contract_redactor.py "{os.path.abspath(doc.source)}" '
                f'--types {all_types} --out "{stem}_脱敏{ext}"'),
        "outHint": out_hint or f"{stem}_脱敏{ext}",
        "warnings": report["warnings"],
        "types": list(types.values()),
        "blocks": blocks,
    }


def write_review_html(report: Dict[str, Any], doc: Document, path: str, full_raw: str,
                      api_base: Optional[str] = None, out_hint: Optional[str] = None) -> None:
    payload = _build_review_payload(report, doc, full_raw, out_hint)
    meta = (f"{html.escape(os.path.basename(doc.source))} · "
            f"{html.escape(report['source']['type'].upper())} · {report['source']['chars']} 字 · "
            f"识别 {len(report['items'])} 类 / {report['summary']['occurrences']} 处 · "
            f"引擎 {html.escape(report['engine']['name'])} v{html.escape(report['engine']['version'])}（离线）· "
            f"生成于 {html.escape(report['generated_at'])}")
    body = (_REVIEW_TEMPLATE
            .replace("__TITLE__", html.escape(os.path.basename(doc.source)))
            .replace("__META__", meta)
            .replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
            .replace("__API__", json.dumps(api_base)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


# ==============================================================================
# 7. 配置 / 白名单
# ==============================================================================

def load_allowlist(path: Optional[str]) -> set:
    if not path:
        return set()
    out = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(line)
    return out


# 命名掩码策略：供规则清单 Markdown 的「掩码参数 mask=xxx」引用
NAMED_MASKS: Dict[str, Callable[[str], str]] = {
    "person": _mask_person,
    "passport": _mask_id_head,
    "hk_id": _mask_hk_id,
    "landline": _mask_landline,
    "address": _mask_address,
    "ipv4": _mask_ipv4,
    "mac": _mask_mac,
    "secret": _mask_secret,
    "amount": _mask_amount,
    "email": _mask_email,
}

_SEV_CN = {"高": "high", "中": "medium", "低": "low"}
_TRUE = ("是", "✓", "x", "true", "y", "yes", "1", "开", "启用")


def load_rules_md(path: str) -> List[RegexSpec]:
    """读取《脱敏规则清单.md》：对已有类型覆盖严重度/掩码/启用开关；
    对带正则的新行自动注册为自定义类型。返回新增的 RegexSpec 列表。"""
    import dataclasses

    extra: List[RegexSpec] = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip().replace("\\|", "|")
                 for c in re.split(r"(?<!\\)\|", s.strip("|"))]
        if len(cells) < 8:
            continue
        if cells[0] in ("#", "") or set(cells[0]) <= set("-: "):
            continue  # 表头 / 分隔行
        type_id = cells[1]
        if not type_id or type_id.startswith("-"):
            continue
        sev = _SEV_CN.get(cells[3], cells[3].lower())
        enabled = cells[7].lower() in _TRUE or cells[7] in _TRUE

        if type_id in TYPE_META:
            meta = TYPE_META[type_id]
            kw: Dict[str, Any] = {}
            if sev in ("high", "medium", "low"):
                kw["severity"] = sev
            kw["enabled"] = enabled
            for part in re.split(r"[;；]", cells[6]):
                if "=" not in part:
                    continue
                k, v = part.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "keep_head":
                    kw["keep_head"] = int(v)
                elif k == "keep_tail":
                    kw["keep_tail"] = int(v)
                elif k == "replacement":
                    kw["replacement"] = v
                    kw["mask_fn"] = None
                elif k == "mask" and v in NAMED_MASKS:
                    kw["mask_fn"] = NAMED_MASKS[v]
                    kw["replacement"] = None
            TYPE_META[type_id] = dataclasses.replace(meta, **kw)
        else:
            # 新类型：需要第 9 列提供正则
            pattern = cells[8] if len(cells) > 8 else ""
            if not pattern:
                sys.stderr.write(f"[warn] 规则清单中的未知类型 {type_id} 且未提供正则，已跳过\n")
                continue
            label = cells[4][:14] or type_id
            TYPE_META[type_id] = TypeMeta(
                type_id, label, cells[2] or "自定义",
                sev if sev in ("high", "medium", "low") else "medium",
                2, 2, priority=50, enabled=enabled,
            )
            extra.append(RegexSpec(
                type_id=type_id, pattern=pattern,
                conf_ok=0.7, conf_weak=0.4,
                keywords=("编号", "号码", "账号"), kw_boost=0.1,
            ))
    return extra


def load_config(path: Optional[str]) -> Tuple[Settings, List[RegexSpec]]:
    st = Settings()
    extra: List[RegexSpec] = []
    if not path:
        return st, extra
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    st.min_confidence = float(cfg.get("min_confidence", st.min_confidence))
    st.min_severity = cfg.get("min_severity", st.min_severity)
    st.disabled = set(cfg.get("disabled", []))
    st.enabled_only = set(cfg["only"]) if cfg.get("only") else None
    st.allowlist = set(cfg.get("allowlist", []))
    for r in cfg.get("custom_rules", []):
        extra.append(RegexSpec(
            type_id=r["type_id"],
            pattern=r["pattern"],
            conf_ok=float(r.get("confidence", 0.7)),
            conf_weak=float(r.get("confidence_weak", 0.4)),
            keywords=tuple(r.get("keywords", ())),
            kw_boost=float(r.get("kw_boost", 0.15)),
            require_keyword=bool(r.get("require_keyword", False)),
            validator=None,
        ))
        if r["type_id"] not in TYPE_META:
            TYPE_META[r["type_id"]] = TypeMeta(
                r["type_id"], r.get("label", r["type_id"]), "自定义",
                r.get("severity", "medium"), int(r.get("keep_head", 2)), int(r.get("keep_tail", 2)),
                priority=int(r.get("priority", 50)),
            )
    return st, extra


# ==============================================================================
# 8. 离线守卫
# ==============================================================================

def enforce_offline() -> None:
    """禁用 socket，任何联网尝试立即抛错 —— 从机制层面保证不外传。"""
    import socket

    def _deny(*_a, **_k):
        raise RuntimeError("离线模式已开启：本工具禁止任何网络连接")

    socket.socket = _deny          # type: ignore[assignment]
    socket.create_connection = _deny  # type: ignore[assignment]
    socket.getaddrinfo = _deny     # type: ignore[assignment]


# ==============================================================================
# 9. 自检
# ==============================================================================

SAMPLE_CONTRACT = """
技术开发（委托）合同

甲方（委托方）：北京星海智能科技有限公司
统一社会信用代码：91110108MA01KLMNX8
法定代表人：赵启明
地址：北京市海淀区中关村南大街 12 号院 3 号楼 1801 室
联系人：孙丽娟
联系电话：13812345678
电子邮箱：zhao.qiming@xinghai-tech.com.cn
开户银行：中国工商银行股份有限公司北京海淀支行
银行账号：0200049609200123456

乙方（受托方）：深圳市南山区云启软件工作室
纳税人识别号：440300123456789
负责人：欧阳博文
身份证号：440305199001012347
通讯地址：广东省深圳市南山区科技园南路 88 号 A 座 2203
手机号：13900139000
微信号：yunqi_bowen

第一条 合同金额
本合同技术开发费用总额为人民币 1,280,000.00 元（大写：壹佰贰拾捌万元整）。
甲方应于 2026年3月15日 前支付首期款 384,000.00 元至乙方上述账户。

第二条 保密条款
双方对因履行本合同而知悉的对方商业秘密、个人信息负有保密义务。
乙方联系人身份证号：11010519491231002X，护照号：E12345678。
甲方项目经理：陈嘉怡（工号 A20230987），直线电话：0755-86329871。

第三条 争议解决
因本合同发生争议，双方应协商解决；协商不成的，提交北京仲裁委员会仲裁。
合同签署日期：2026年2月28日
"""


# 用于「实体编号一致性」自检的样例：人名/机构名多次出现 + 显式简称 + 两类漏检场景
_ENTITY_SAMPLE = """甲方：北京星海智能科技有限公司（以下简称“星海智能”）
统一社会信用代码：91110108MA8A2X5K3R
联系电话：010-8666 2188
法定代表人：张三
乙方：上海星光数据服务有限公司
授权代表：李四
第一条 星海智能 委托乙方提供数据服务，乙方指派张三 作为项目负责人。
第二条 张三 应于每季度向星海智能 提交报告，同时抄送李四。
第三条 本协议由北京星海智能科技有限公司 与上海星光数据服务有限公司 共同签署。
第四条 星海智能 的联系电话为 010-86662188。
第五条 甲方法定代表人张三 签字，乙方授权代表李四 签字。
"""


def selftest(verbose: bool = True) -> int:
    """内置回归自检：校验算法 + 端到端识别。不需要任何外部文件。"""
    fails: List[str] = []

    def check(name: str, cond: bool, extra: str = "") -> None:
        if not cond:
            fails.append(name)
        if verbose:
            tail = f"  [{extra}]" if extra and not cond else ""
            print(f"  [{'PASS' if cond else 'FAIL'}] {name}{tail}")

    print("== 校验算法 ==")
    check("身份证 11010519491231002X 校验通过", id_card_check("11010519491231002X") is True)
    check("身份证 110101199003070011 校验通过", id_card_check("110101199003070011") is True)
    check("身份证 440305199001012347 校验通过", id_card_check("440305199001012347") is True)
    check("身份证篡改后校验失败", id_card_check("11010519491231002" + "1") is False)
    check("身份证非18位返回 None", id_card_check("44030519900101234") is None)
    check("USCC 91350100M000100Y43 校验通过", uscc_check("91350100M000100Y43") is True)
    check("USCC 91110108MA01KLMNX8 校验通过", uscc_check("91110108MA01KLMNX8") is True)
    check("USCC 91440300MA5EXY9H78 校验通过", uscc_check("91440300MA5EXY9H78") is True)
    check("USCC 篡改后失败", uscc_check("91350100M000100Y44") is False)
    check("USCC 含非法字符 I 返回 None", uscc_check("91350100M000100YI3") is None)
    check("Luhn 4111111111111111 通过", luhn_check("4111111111111111") is True)
    check("Luhn 4111111111111112 失败", luhn_check("4111111111111112") is False)
    check("Luhn 支持空格分组", luhn_check("4111 1111 1111 1111") is True)

    print("== 归一化与下标映射 ==")
    nt = NormalizedText("甲方：１２３４５６７８９０１２３４５６７　张三")
    dm = re.search(r"\d+", nt.norm)
    check("全角数字归一化", bool(dm) and dm.group(0) == "12345678901234567")
    check("全角空格归一化", nt.norm == "甲方:12345678901234567 张三")
    rs, re_ = nt.to_raw_span(dm.start(), dm.end())
    check("归一化下标回映原文正确", nt.raw[rs:re_] == "１２３４５６７８９０１２３４５６７")

    print("== 端到端识别 ==")
    settings = Settings(min_confidence=0.5, min_severity="low")
    engine = DetectorEngine(settings)
    doc = Document(source="<selftest>", file_type="txt",
                   blocks=[Block(text=line, block_type="line", location=f"第 {i} 行")
                           for i, line in enumerate(SAMPLE_CONTRACT.splitlines(), 1) if line.strip()])
    cands = engine.scan_document(doc)
    found = {c.type_id for c in cands}
    values = {c.value for c in cands}

    def has(t: str, v: str) -> bool:
        return any(c.type_id == t and c.value == v for c in cands)

    check("识别统一社会信用代码", has("USCC", "91110108MA01KLMNX8"))
    check("识别身份证号 440305199001012347", has("ID_CARD", "440305199001012347"))
    check("识别身份证号 11010519491231002X", has("ID_CARD", "11010519491231002X"))
    check("识别手机号 13812345678", has("PHONE_MOBILE", "13812345678"))
    check("识别邮箱", any(c.type_id == "EMAIL" and "xinghai-tech.com.cn" in c.value for c in cands))
    check("识别姓名 赵启明", has("PERSON_NAME", "赵启明"))
    check("识别复姓姓名 欧阳博文", has("PERSON_NAME", "欧阳博文"))
    check("识别姓名 陈嘉怡", has("PERSON_NAME", "陈嘉怡"))
    check("识别机构名（含有限公司）", any(c.type_id == "ORG_NAME" and "北京星海智能科技有限公司" in c.value
                                  for c in cands))
    check("识别地址", any(c.type_id == "ADDRESS" and "中关村南大街" in c.value for c in cands))
    check("识别银行账号", any(c.type_id == "BANK_ACCOUNT" for c in cands))
    check("识别金额", any(c.type_id == "AMOUNT" and "1,280,000.00" in c.value for c in cands))
    check("识别大写金额", any(c.type_id == "AMOUNT" and "壹佰贰拾捌万元整" in c.value for c in cands))
    check("识别纳税人识别号", any(c.type_id == "TAX_ID" for c in cands))
    check("识别座机 0755-86329871", any(c.type_id == "PHONE_LANDLINE" and "0755-86329871" in c.value
                                   for c in cands))
    check("识别日期", any(c.type_id == "DATE" for c in cands))
    check("未把『北京仲裁委员会』误判为地址", not any(
        c.type_id == "ADDRESS" and "仲裁委员会" in c.value for c in cands))
    check("占位符被剔除", not any(is_placeholder(c.value) for c in cands))

    print("== 实体编号一致性（同一实体必须同一个 [标签#N]） ==")
    ent_doc = Document(source="<entity-selftest>", file_type="txt",
                       blocks=[Block(text=line, block_type="line", location=f"第 {i} 行")
                               for i, line in enumerate(_ENTITY_SAMPLE.splitlines(), 1)
                               if line.strip()])
    ent_cands = DetectorEngine(settings).scan_document(ent_doc)
    ent_report = build_report(ent_doc, ent_cands, settings)
    numberer = EntityNumberer(ent_report["items"])
    n_zhang = numberer.number("PERSON_NAME", "张三")
    n_li = numberer.number("PERSON_NAME", "李四")
    n_full = numberer.number("ORG_NAME", "北京星海智能科技有限公司")
    n_short = numberer.number("ORG_NAME", "星海智能")
    n_other = numberer.number("ORG_NAME", "上海星光数据服务有限公司")
    check("同一个人名只占一个号（张三）", n_zhang == 1, f"张三={n_zhang}")
    check("不同人名各自占号（李四）", n_li == 2, f"李四={n_li}")
    check("机构全称与其简称同号", n_full == n_short == 1,
          f"全称={n_full} 简称={n_short}")
    check("不同机构各自占号（乙方）", n_other == 2, f"乙方={n_other}")
    check("占位符格式统一 [标签#N]",
          placeholder_text("自然人姓名", 1) == "[自然人姓名#1]")
    check("占位符可被解析", parse_placeholder("[组织机构名称#12]") == ("组织机构名称", 12))

    print("== 漏检修复：座机 / 统一社会信用代码 ==")
    check("座机带内部分组空格 010-8666 2188 能识别",
          any(c.type_id == "PHONE_LANDLINE" and "8666" in c.value and "2188" in c.value
              for c in ent_cands))
    check("校验码错误的统一社会信用代码仍能识别",
          any(c.type_id == "USCC" and c.value == "91110108MA8A2X5K3R"
              for c in ent_cands))
    check("座机脱敏保留区号与末 4 位",
          mask_value("010-8666 2188", "PHONE_LANDLINE") == "010-****2188")

    print("== 脱敏预览 ==")
    check("身份证脱敏 440305********2347", mask_value("440305199001012347", "ID_CARD") == "440305********2347")
    check("手机号脱敏 138****5678", mask_value("13812345678", "PHONE_MOBILE") == "138****5678")
    check("姓名脱敏 赵**", mask_value("赵启明", "PERSON_NAME") == "赵**")
    check("复姓姓名脱敏 欧阳**", mask_value("欧阳博文", "PERSON_NAME") == "欧阳**")
    m = mask_value("zhao.qiming@xinghai-tech.com.cn", "EMAIL")
    check("邮箱保留域名 " + m, m.startswith("z") and m.endswith("@xinghai-tech.com.cn"))

    print()
    if fails:
        print(f"自检失败 {len(fails)} 项：")
        for f in fails:
            print("  - " + f)
        return 1
    print("自检全部通过 ✔ 共识别 %d 类 / %d 处候选" % (
        len(cands), sum(c.count for c in cands)))
    return 0


# ==============================================================================
# 10. CLI
# ==============================================================================

def process_file(path: str, settings: Settings, out_dir: str, formats: set,
                 quiet: bool = False, include_headers: bool = True,
                 used_bases: Optional[set] = None,
                 review_api: Optional[str] = None) -> Dict[str, Any]:
    doc = load_document(path, include_headers=include_headers)
    engine = DetectorEngine(settings)
    candidates = engine.scan_document(doc)
    report = build_report(doc, candidates, settings)

    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    base = os.path.join(out_dir, stem)
    if used_bases is not None:
        # 同名不同格式（合同.docx / 合同.pdf）不能互相覆盖
        if base in used_bases:
            base = f"{base}_{doc.file_type}"
        n = 2
        while base in used_bases:
            base = f"{os.path.join(out_dir, stem)}_{doc.file_type}{n}"
            n += 1
        used_bases.add(base)
    written: List[str] = []

    if "json" in formats:
        p = base + ".sensitive.json"
        write_json(report, p)
        written.append(p)
    if "csv" in formats:
        p = base + ".sensitive.csv"
        write_csv(report, p)
        written.append(p)

    full_raw = "\n".join(b.text.rstrip("\n") for b in doc.blocks)
    if "txt" in formats:
        p = base + ".annotated.txt"
        with open(p, "w", encoding="utf-8") as f:
            f.write(build_annotated_text(doc, candidates, full_raw))
        written.append(p)
    if "masked" in formats:
        p = base + ".masked.txt"
        with open(p, "w", encoding="utf-8") as f:
            f.write(build_masked_text(doc, candidates, full_raw))
        written.append(p)
    if "html" in formats:
        p = base + ".review.html"
        write_review_html(report, doc, p, full_raw, api_base=review_api)
        written.append(p)
    if "mapping" in formats:
        p = base + ".mapping.json"
        write_mapping(report, p)
        written.append(p)
    # 默认导出 selection.json（detector 已经把报告里所有类型打包好，
    # 让 redactor 在没有 UI 时也能直接使用）
    sel_p = base + ".selection.json"
    if not os.path.exists(sel_p) or True:
        enabled = [it["type"] for it in report["items"]]
        with open(sel_p, "w", encoding="utf-8") as f:
            json.dump({
                "source": os.path.abspath(path),
                "enabled_types": enabled,
                "min_confidence": settings.min_confidence,
                "min_severity": settings.min_severity,
                "generated_by": f"{report['engine']['name']} v{report['engine']['version']}",
                "generated_at": report["generated_at"],
            }, f, ensure_ascii=False, indent=2)
        written.append(sel_p)

    if not quiet:
        s = report["summary"]
        print(f"\n■ {os.path.basename(path)}  [{doc.file_type}] {report['source']['chars']} 字")
        for w in doc.warnings:
            print(f"   ⚠ {w}")
        print(f"   候选 {s['candidate_types']} 类 / {s['occurrences']} 处")
        for c in candidates[:20]:
            loc = c.occurrences[0].location
            print(f"   [{c.cid:>2}] {SEVERITY_LABEL.get(c.severity,'?')} "
                  f"{c.label:<12} {c.confidence:.2f}  ×{c.count}  "
                  f"{c.value[:28]:<30} → {c.masked[:22]:<24} @ {loc}")
        if len(candidates) > 20:
            print(f"   … 其余 {len(candidates)-20} 类见报告文件")
        for p in written:
            print(f"   → {p}")
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="contract_sensitive_detector.py",
        description="合同敏感信息候选项识别器（完全离线：正则 + 上下文 + 国标校验位）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  python contract_sensitive_detector.py 合同.docx
  python contract_sensitive_detector.py a.pdf b.docx --out-dir out --format json,html
  python contract_sensitive_detector.py 合同.docx --min-severity high
  python contract_sensitive_detector.py 合同.docx --disable DATE,AMOUNT,PLATE
  python contract_sensitive_detector.py --selftest
""")
    ap.add_argument("inputs", nargs="*", help="待检测的 .docx / .pdf / .txt / .md 文件")
    ap.add_argument("--out-dir", default="./sensitive_reports", help="报告输出目录（默认 ./sensitive_reports）")
    ap.add_argument("--format", default="json,csv,txt",
                    help="输出格式，逗号分隔：json,csv,txt,masked,html,mapping（默认 json,csv,txt）")
    ap.add_argument("--min-confidence", type=float, default=0.5, help="置信度下限 0~1（默认 0.5）")
    ap.add_argument("--min-severity", default="low", choices=["low", "medium", "high"],
                    help="严重度下限（默认 low=全部）")
    ap.add_argument("--disable", default="", help="停用的类型，逗号分隔，如 DATE,AMOUNT")
    ap.add_argument("--only", default="", help="只启用这些类型，逗号分隔")
    ap.add_argument("--enable", default="", help="强制启用默认关闭的类型，逗号分隔（如 IPV4,MAC_ADDRESS）")
    ap.add_argument("--allowlist", help="白名单文件（每行一个值，命中即忽略）")
    ap.add_argument("--rules", help="脱敏规则清单 Markdown（默认读取脚本同目录的 脱敏规则清单.md）")
    ap.add_argument("--config", help="JSON 配置文件（可含 min_confidence/disabled/allowlist/custom_rules）")
    ap.add_argument("--context-chars", type=int, default=30, help="上下文摘录字数（默认 30）")
    ap.add_argument("--no-headers", action="store_true", help="不解析 docx 页眉页脚")
    ap.add_argument("--allow-network", action="store_true",
                    help="关闭离线守卫（默认开启，任何联网都会被阻断）")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检并退出")
    ap.add_argument("--quiet", "-q", action="store_true", help="不打印明细")
    ap.add_argument("--review-api", help="HTML 复核页用：写入 review.html 的 API base（默认从 $REVIEW_API 读取）")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    if not args.allow_network:
        enforce_offline()

    if args.selftest:
        return selftest(verbose=not args.quiet)

    if not args.inputs:
        ap.print_help()
        return 2

    settings, extra = load_config(args.config)
    if args.config is None:
        settings.min_confidence = args.min_confidence
        settings.min_severity = args.min_severity
        settings.disabled = {t.strip() for t in args.disable.split(",") if t.strip()}
        settings.enabled_only = {t.strip() for t in args.only.split(",") if t.strip()} or None
    else:
        if args.min_confidence != 0.5:
            settings.min_confidence = args.min_confidence
        if args.min_severity != "low":
            settings.min_severity = args.min_severity
        if args.disable:
            settings.disabled |= {t.strip() for t in args.disable.split(",") if t.strip()}
        if args.only:
            settings.enabled_only = {t.strip() for t in args.only.split(",") if t.strip()}
    settings.extra_specs = extra
    settings.allowlist |= load_allowlist(args.allowlist)
    settings.context_chars = args.context_chars
    settings.force_enabled = {t.strip() for t in args.enable.split(",") if t.strip()}

    rules_path = args.rules
    if rules_path is None:
        default_rules = os.path.join(os.path.dirname(os.path.abspath(__file__)), "脱敏规则清单.md")
        if os.path.exists(default_rules):
            rules_path = default_rules
    if rules_path:
        if not os.path.exists(rules_path):
            print(f"[错误] 规则清单不存在：{rules_path}", file=sys.stderr)
            return 1
        settings.extra_specs.extend(load_rules_md(rules_path))

    if args.review_api:
        os.environ["REVIEW_API"] = args.review_api
    formats = {f.strip() for f in args.format.split(",") if f.strip()}
    exit_code = 0
    used_bases: set = set()
    for path in args.inputs:
        if not os.path.exists(path):
            print(f"[错误] 文件不存在：{path}", file=sys.stderr)
            exit_code = 1
            continue
        try:
            process_file(path, settings, args.out_dir, formats, quiet=args.quiet,
                         include_headers=not args.no_headers, used_bases=used_bases,
                         review_api=args.review_api or os.environ.get("REVIEW_API"))
        except Exception as exc:
            print(f"[错误] {path} 处理失败：{exc}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
