# -*- coding: utf-8 -*-
# Streamlit app: mkwab – マリオカートワールド オートバランス by あすとらふぃーだ
# 目的:
#  - 参加最大24人までのチーム自動編成（2 / 3 / 4チーム）
#  - 一括入力（「名前：レート, 名前：レート, ...」）対応
#  - 参加チェック・個別入力・結果表示・勝利チームのレート更新
#  - ★編成結果をPNG画像でダウンロード（Pillow使用）
#
# ファイル名の想定: mkwab.py
# ※本ツールは非公式のファンメイドです。任天堂・各権利者とは一切関係ありません。

import re
import io
from typing import List, Tuple, Dict, Any
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Pillow (画像出力) は任意機能
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

st.set_page_config(page_title="mkwab – マリオカートワールド オートバランス", layout="wide")

# =========================
# セッション変数 初期化
# =========================
if "stage" not in st.session_state:
    # start -> フォーム入力中
    # assigned -> 「チームを分ける」押下直後（編成処理トリガ）
    # assigned_done -> チーム表示中
    # updated -> レート更新後
    st.session_state.stage = "start"

# プレイヤー 24枠（(name, rate) のタプル）
if "players" not in st.session_state:
    st.session_state.players = [("", 2000) for _ in range(24)]

# 参加チェック（24枠ぶん）
if "participate" not in st.session_state:
    st.session_state.participate = [False for _ in range(24)]

# 一括入力保持
if "bulk_input" not in st.session_state:
    st.session_state.bulk_input = ""

# チーム選択（2/3/4 のチェック状態）
if "team_check_2" not in st.session_state:
    st.session_state.team_check_2 = True
if "team_check_3" not in st.session_state:
    st.session_state.team_check_3 = False
if "team_check_4" not in st.session_state:
    st.session_state.team_check_4 = False

# 編成結果（k -> {"teams": List[List[(name, rate)]], "diff": int}）
if "assigned_results" not in st.session_state:
    st.session_state.assigned_results = {}

# =========================
# タイトル（by あすとらふぃーだ 部分をXにリンク）
# =========================
st.markdown(
    "## 🏎️ mkwab – マリオカートワールド オートバランス by "
    "[あすとらふぃーだ](https://x.com/Ascalaphidae)"
)

st.markdown("""
マリオカートワールドの **レート** に応じて **2 / 3 / 4チーム** の最適化を試みた編成を行い、  
勝利チームの **レート更新** と **編成結果のPNG保存** までワンストップで行えます ✨

> **注意:** 本アプリは非公式のファンメイドツールです。各権利者とは関係ありません。
---
""")

# =========================
# ① 一括入力 UI
# =========================
st.subheader("🧩 一括入力（プレイヤー名とレート）")
st.caption("例： あすふぃだ：7000、イシガケ：7100、ウスバキ：6900、エサキモンツノ：7200（全角/半角の「：」「,」「、」「；」「;」、改行OK）")
st.session_state.bulk_input = st.text_area(
    "形式：名前：レート をカンマ等で区切って入力（最大24人まで）",
    value=st.session_state.bulk_input,
    height=100,
    placeholder="あすふぃだ：7000、イシガケ：7100、ウスバキ：6900、エサキモンツノ：7200"
)

def _parse_and_apply_bulk():
    raw = st.session_state.bulk_input or ""
    # 区切りをカンマに正規化（読点・セミコロン・改行など）
    s = raw.replace("\n", ",")
    s = re.sub(r"[、；;]", ",", s)
    entries = [e.strip() for e in s.split(",") if e.strip()]
    applied = 0
    errors = []
    idx = 0

    for e in entries:
        # コロン（全角/半角）で name:rate に分割
        if "：" in e:
            parts = e.split("：", 1)
        elif ":" in e:
            parts = e.split(":", 1)
        else:
            errors.append(f"区切り（: または ：）が見つかりません: {e}")
            continue

        name = parts[0].strip()
        rate_str = parts[1].strip()

        if not name:
            errors.append(f"名前が空です: {e}")
            continue

        # 全角数字を半角へ
        rate_str = rate_str.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        if not re.fullmatch(r"\d+", rate_str):
            errors.append(f"レートが数値ではありません: {e}")
            continue

        rate = max(0, int(rate_str))

        if idx < 24:
            st.session_state.players[idx] = (name, rate)
            st.session_state.participate[idx] = True  # 反映枠は参加ON
            idx += 1
            applied += 1
        else:
            errors.append(f"24枠を超えたためスキップ: {e}")

    if applied > 0:
        st.success(f"✅ {applied}人を一括反映しました（参加ON）。")
    if errors:
        st.warning("⚠️ 次の項目は反映できませんでした：\n- " + "\n- ".join(errors))

st.button("反映", type="primary", on_click=_parse_and_apply_bulk)

# =========================
# ② チーム数の選択（チェックボックス）
# =========================
st.subheader("🧮 チーム数の選択（複数チェック可）")
c2, c3, c4 = st.columns(3)
with c2:
    st.session_state.team_check_2 = st.checkbox("2チーム", value=st.session_state.team_check_2, key="team2")
with c3:
    st.session_state.team_check_3 = st.checkbox("3チーム", value=st.session_state.team_check_3, key="team3")
with c4:
    st.session_state.team_check_4 = st.checkbox("4チーム", value=st.session_state.team_check_4, key="team4")

if not any([st.session_state.team_check_2, st.session_state.team_check_3, st.session_state.team_check_4]):
    st.info("※ 少なくとも1つのチーム数（2 / 3 / 4）をチェックしてください。未選択の場合はデフォルトで **2チーム** を使用します。")

# =========================
# 個別入力フォーム（24枠）
# =========================
st.subheader("📝 プレイヤー情報の入力（個別）")
st.markdown("各プレイヤーの**名前**・**レート**・**参加可否**を調整してください。")

def _reset_all():
    st.session_state.players = [("", 2000) for _ in range(24)]
    st.session_state.participate = [False for _ in range(24)]
    st.session_state.assigned_results = {}
    st.session_state.stage = "start"
    st.rerun()

with st.form(key="player_form"):
    top_cols = st.columns([1, 5])
    with top_cols[0]:
        st.form_submit_button("🔄 入力をリセット", on_click=_reset_all)
    with top_cols[1]:
        st.caption("※ レートは0以上の整数を想定。参加ONかつ名前が空でない枠だけが編成対象です。")

    # 24枠を 6列 × 4行 で表示
    num_slots = 24
    cols_per_row = 6
    rows = num_slots // cols_per_row  # 4
    idx = 0
    for r in range(rows):
        cols = st.columns(cols_per_row)
        for c in range(cols_per_row):
            with cols[c]:
                st.markdown(f"**枠{idx+1}**")
                name = st.text_input(f"名前{idx+1}", value=st.session_state.players[idx][0], key=f"name_{idx}")
                rate = st.number_input(
                    f"レート{idx+1}",
                    min_value=0,
                    value=int(st.session_state.players[idx][1]),
                    step=50,
                    key=f"rate_{idx}"
                )
                part = st.checkbox(
                    "参加する",
                    value=st.session_state.participate[idx],
                    key=f"part_{idx}"
                )
                st.session_state.players[idx] = (name, int(rate))
                st.session_state.participate[idx] = bool(part)
                idx += 1

    submit = st.form_submit_button("✅ チームを分ける")
    if submit:
        st.session_state.stage = "assigned"

# =========================
# チーム分けロジック（k=2/3/4 対応）
# =========================
def _team_sizes(n: int, k: int) -> List[int]:
    """n人をkチームにほぼ均等に分割したときの各チーム目標人数を返す（先のチームから+1）。"""
    base = n // k
    rem = n % k
    sizes = [base + (1 if i < rem else 0) for i in range(k)]
    return sizes

def assign_k_teams_greedy(players_list: List[Tuple[str, int]], k: int):
    """
    (name, rate) のリストを kチームに分割。
    - 手順1: レート降順で並べ、合計が最小かつ人数上限未満のチームへ順番に割当（貪欲）
    - 手順2: 軽い局所改善（2チーム間の1対1スワップ）で max(sum)-min(sum) を縮小試行
    戻り値: (teams: List[List[(name, rate)]], diff: int)
    """
    n = len(players_list)
    if n < k:
        return [[] for _ in range(k)], None

    sizes = _team_sizes(n, k)
    players_sorted = sorted(players_list, key=lambda x: x[1], reverse=True)

    teams: List[List[Tuple[str, int]]] = [[] for _ in range(k)]
    sums = [0 for _ in range(k)]

    # 貪欲割当
    for p in players_sorted:
        candidates = [(i, sums[i]) for i in range(k) if len(teams[i]) < sizes[i]]
        if not candidates:
            candidates = [(i, len(teams[i])) for i in range(k)]
        target_idx = min(candidates, key=lambda x: x[1])[0]
        teams[target_idx].append(p)
        sums[target_idx] += p[1]

    # 軽い局所改善（最大200試行）
    def current_diff(ss: List[int]) -> int:
        return max(ss) - min(ss)

    improved = True
    tries = 0
    while improved and tries < 200:
        improved = False
        tries += 1
        for a in range(k):
            for b in range(a+1, k):
                best_local_gain = 0
                best_pair = None
                base_diff = current_diff(sums)
                for i, pa in enumerate(teams[a]):
                    for j, pb in enumerate(teams[b]):
                        new_sa = sums[a] - pa[1] + pb[1]
                        new_sb = sums[b] - pb[1] + pa[1]
                        new_sums = sums.copy()
                        new_sums[a] = new_sa
                        new_sums[b] = new_sb
                        new_diff = current_diff(new_sums)
                        gain = base_diff - new_diff
                        if gain > best_local_gain:
                            best_local_gain = gain
                            best_pair = (i, j, new_sums)
                if best_pair:
                    i, j, new_sums = best_pair
                    pa = teams[a][i]
                    pb = teams[b][j]
                    teams[a][i], teams[b][j] = pb, pa
                    sums = new_sums
                    improved = True

    diff = max(sums) - min(sums)
    return teams, diff

# =========================
# チーム編成 実行（より堅牢に：stageだけで判定）
# =========================
def _run_assignment():
    selected = [
        (n, r)
        for (n, r), use in zip(st.session_state.players, st.session_state.participate)
        if use and str(n).strip() != ""
    ]
    n_sel = len(selected)

    if n_sel > 24:
        st.session_state.stage = "start"
        st.session_state.assigned_results = {}
        st.error("❌ 参加者が24人を超えています。チェックを外して再実行してください。")
        return

    if n_sel < 2:
        st.warning("⚠️ 2人以上選んでください。（名前が空欄だと無視されます）")
        return

    selected_k_list = []
    if st.session_state.team_check_2:
        selected_k_list.append(2)
    if st.session_state.team_check_3:
        selected_k_list.append(3)
    if st.session_state.team_check_4:
        selected_k_list.append(4)
    if not selected_k_list:
        selected_k_list = [2]

    results: Dict[int, Dict[str, Any]] = {}
    for k in selected_k_list:
        if n_sel < k:
            st.warning(f"⚠️ {k}チーム編成には最低{k}人が必要です。（現在 {n_sel} 人）")
            continue
        teams, diff = assign_k_teams_greedy(selected, k)
        results[k] = {"teams": teams, "diff": diff}

    if results:
        st.session_state.assigned_results = results
        st.session_state.stage = "assigned_done"
        st.success(f"💡 チーム分けしました！ 参加人数: {n_sel}（選択チーム数: {', '.join(map(str, results.keys()))}）")
    else:
        st.info("（条件を満たすチーム数が選択されていないため、編成は行われませんでした）")

if st.session_state.get("stage") == "assigned":
    _run_assignment()

# =========================
# 状況に応じた画像（任意）
# =========================
if st.session_state.stage in ("start", "updated"):
    img_url = "https://cdn.discordapp.com/attachments/1291365679429189632/1362413372217364784/1.png?ex=68024dd4&is=6800fc54&hm=12d406f6e7bbda55e86f2fcbf700164ad03b8ce1142bd1766d449d383f2cf7a7&"
elif st.session_state.stage in ("assigned", "assigned_done"):
    img_url = "https://cdn.discordapp.com/attachments/1291365679429189632/1362413397353693184/2.png?ex=68024dda&is=6800fc5a&hm=7537e4ecb893d42b6d028bc267f8e53b701d7e3b021fc9ea4a66b92dbe323f14&"
else:
    img_url = ""

if img_url:
    components.html(f"""
    <script>
    function confirmAndRedirect() {{
        if (confirm('あすとらふぃーだのチャンネルを表示する？')) {{
            window.open('https://www.youtube.com/channel/UCjJbi4Fs5kZIRAVWvNBPOpA', '_blank');
        }}
    }}
    </script>
    <div style='position: fixed; bottom: 1rem; right: 1rem; z-index: 5;'>
        <img src='{img_url}' width='170' style='opacity: 0.85; border-radius: 10px; cursor: pointer;' onclick='confirmAndRedirect()'>
    </div>
    """, height=260)

# =========================
# 画像保存（PNG）用ヘルパー
# =========================
def _load_jp_font(size: int):
    """日本語対応フォントを探索して読み込み（見つからなければデフォルト）"""
    candidates = [
        "./NotoSansJP-Regular.ttf",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf",
        "/System/Library/Fonts/Hiragino Sans W3.ttc",
        "/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/Library/Fonts/Hiragino Sans W3.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    if not PIL_AVAILABLE:
        return None
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def _render_teams_png(teams: List[List[Tuple[str, int]]], labels: List[str], totals: List[int], diff: int) -> bytes:
    """編成結果をPNG画像に描画してbytesで返す（Pillow）。"""
    if not PIL_AVAILABLE:
        return b""

    k = len(teams)
    pad = 40
    gap = 24
    col_w = 460
    row_h = 38
    title_h = 58
    sub_h = 28
    head_h = 40

    max_rows = max((len(t) for t in teams), default=0)
    width = pad * 2 + k * col_w + (k - 1) * gap
    height = pad * 2 + title_h + sub_h + head_h + (max_rows + 1) * row_h

    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    font_title = _load_jp_font(28)
    font_sub = _load_jp_font(16)
    font_head = _load_jp_font(20)
    font_row = _load_jp_font(18)

    # タイトル
    title = "mkwab – マリオカートワールド オートバランス"
    draw.text((pad, pad), title, fill=(0, 0, 0), font=font_title)
    # サブ（差分）
    sub = f"合計レート差: {diff}"
    draw.text((pad, pad + title_h - 10), sub, fill=(80, 80, 80), font=font_sub)

    # 各カラム
    base_x = pad
    base_y = pad + title_h + sub_h

    for ci in range(k):
        x = base_x + ci * (col_w + gap)
        # ヘッダ
        head_text = f"チーム{labels[ci]}（合計: {totals[ci]}）"
        draw.rectangle([(x, base_y), (x + col_w, base_y + head_h)], fill=(245, 245, 245))
        draw.text((x + 12, base_y + 8), head_text, fill=(0, 0, 0), font=font_head)

        # 行
        y = base_y + head_h + 6
        for ri, (name, rate) in enumerate(teams[ci]):
            line = f"{ri+1:>2}. {name}    {rate}"
            draw.text((x + 12, y), line, fill=(0, 0, 0), font=font_row)
            y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# =========================
# チーム表示 & レート更新 & PNG保存
# =========================
if st.session_state.assigned_results:
    st.divider()
    st.header("📊 編成結果 & レート更新 / 画像保存")

    def _team_label(idx: int) -> str:
        return ["A", "B", "C", "D"][idx]

    for k in sorted(st.session_state.assigned_results.keys()):
        block = st.session_state.assigned_results[k]
        teams = block["teams"]
        diff = block["diff"]

        st.subheader(f"🧩 {k}チーム編成  （合計レート差: {diff}）")

        team_cols = st.columns(k)
        team_totals = []
        for ti in range(k):
            with team_cols[ti]:
                tlabel = _team_label(ti)
                st.markdown(f"### 🟥 チーム{tlabel}")
                df = pd.DataFrame(teams[ti], columns=["名前", "レート"])
                st.dataframe(df, use_container_width=True, height=260)
                total = int(df["レート"].sum()) if not df.empty else 0
                team_totals.append(total)
                st.markdown(f"**合計パワー：{total}**")

        st.markdown("---")
        st.markdown(f"#### 🏆 勝利チームのレート更新（{k}チーム編成 用）")

        win_team = st.radio(
            f"どのチームが勝ちましたか？（{k}チーム編成）",
            [_team_label(i) for i in range(k)],
            horizontal=True,
            key=f"win_team_k{k}"
        )
        multiplier = st.number_input(
            f"更新倍率（例：1.03 = 3%加算）〔{k}チーム編成〕",
            value=1.03,
            step=0.01,
            key=f"mult_k{k}"
        )

        def _update_rates_for_k(_k: int, _winner_label: str, _mult: float):
            st.session_state.stage = "updated"
            block = st.session_state.assigned_results.get(_k)
            if not block:
                st.warning("この編成の結果が見つかりません。もう一度編成してください。")
                return
            winner_idx = ["A", "B", "C", "D"].index(_winner_label)
            if winner_idx >= len(block["teams"]):
                st.warning("勝利チームの指定が不正です。")
                return
            winners = set(n for n, _ in block["teams"][winner_idx])

            updated_players = []
            for (n, r) in st.session_state.players:
                if str(n).strip() != "" and n in winners:
                    try:
                        new_rate = round(float(r) * float(_mult))
                    except Exception:
                        new_rate = r
                    updated_players.append((n, new_rate))
                else:
                    updated_players.append((n, r))

            st.session_state.players = updated_players
            # 最新レートで再編成して表示を同期
            st.session_state.stage = "assigned"
            st.session_state.assigned_results = {}
            _run_assignment()
            st.success(f"✅ レートを更新しました！（{_k}チーム編成／勝利: { _winner_label }／倍率: { _mult }）")

        st.button(
            f"📈 レートを更新する（{k}チーム編成）",
            key=f"btn_update_k{k}",
            on_click=_update_rates_for_k,
            args=(k, win_team, multiplier)
        )

        # --- PNG保存（Pillow使用） ---
        st.markdown("#### 🖼️ 編成結果の画像保存（PNG）")
        if PIL_AVAILABLE:
            labels = [_team_label(i) for i in range(k)]
            png_bytes = _render_teams_png(teams, labels, team_totals, diff)
            st.download_button(
                label=f"🖼️ PNGをダウンロード（{k}チーム編成）",
                data=png_bytes,
                file_name=f"mkwab_{k}teams.png",
                mime="image/png",
                key=f"dl_png_k{k}"
            )
            st.caption("※ 日本語フォントが見つからない環境では文字化けする場合があります。必要なら `NotoSansJP-Regular.ttf` を同じフォルダに置いてください。")
        else:
            st.info("画像保存機能を使うには、`pip install pillow` を実行してください。")
else:
    st.info("まだ編成結果はありません。「✅ チームを分ける」を押して編成を実行してください。")
