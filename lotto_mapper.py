import streamlit as st
import sqlite3
import random
import re

DB_PATH = "coverings.db"

# --- Helper ---
def get_v_from_description(description):
    """Handles formats like '08-06-03' or '8N-3S' or '15N-3S'"""
    match = re.match(r"(\d+)", description)
    if match:
        return int(match.group(1))
    else:
        raise ValueError(f"Could not extract v from description: {description}")

@st.cache_data
def get_design_descriptions():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT description FROM CoveringDesigns ORDER BY description")
    descs = [row[0] for row in cur.fetchall()]
    conn.close()
    return descs

def get_blocks_by_description(description):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM CoveringDesigns WHERE description = ?", (description,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return []
    design_id = row[0]
    cur.execute("""
        SELECT b1, b2, b3, b4, b5, b6
        FROM Blocks
        WHERE design_id = ?
        ORDER BY id
    """, (design_id,))
    blocks = cur.fetchall()
    conn.close()
    return blocks

def map_user_numbers(user_numbers, block):
    """Map block positions (1-based) to actual user-selected values"""
    try:
        return [user_numbers[i - 1] for i in block]
    except IndexError:
        return None

# --- App ---
st.set_page_config(page_title="🎰 Lotto Mapper", layout="centered")
st.title("🎰 Lotto Mapper with Covering Designs & Prize Checker")

# --- Pick design ---
designs = get_design_descriptions()
if not designs:
    st.warning("⚠️ No covering designs found.")
    st.stop()

selected = st.selectbox("Choose a Covering Design", designs)

# Extract v from chosen design
v_design = get_v_from_description(selected)

# 🎲 Generate random base numbers
if st.button(f"🎲 Generate Random {v_design} Numbers (1–42)"):
    random_numbers = sorted(random.sample(range(1, 43), v_design))
    random_numbers_str = ', '.join(str(n) for n in random_numbers)
    st.session_state['generated_numbers'] = random_numbers_str
else:
    if 'generated_numbers' not in st.session_state:
        st.session_state['generated_numbers'] = ''

user_input = st.text_input(
    f"Enter your {v_design} lotto numbers (comma-separated):",
    st.session_state['generated_numbers']
)

try:
    user_numbers = [int(x) for x in user_input.strip().split(",") if x.strip()]
    v = len(user_numbers)
    if v < 6:
        st.error("❌ You must enter at least 6 numbers.")
        st.stop()
except:
    st.error("❌ Invalid input format.")
    st.stop()

# 🎯 Drawn input
draw_input = st.text_input(
    "Enter the 6 drawn numbers (comma-separated):",
    st.session_state.get('generated_drawn_numbers', '')
)

# 🎲 Generate random drawn numbers AFTER input
if st.button("🎲 Generate Random Drawn Numbers (6 numbers, 1–42)"):
    random_drawn = sorted(random.sample(range(1, 43), 6))
    random_drawn_str = ', '.join(str(n) for n in random_drawn)
    st.session_state['generated_drawn_numbers'] = random_drawn_str
    # st.experimental_rerun()

try:
    draw_numbers = [int(x) for x in draw_input.strip().split(",") if x.strip()]
    if len(draw_numbers) != 6 or len(set(draw_numbers)) != 6:
        st.error("❌ Must be exactly 6 unique drawn numbers.")
        st.stop()
except:
    st.error("❌ Invalid drawn format.")
    st.stop()

# --- Get blocks ---
blocks = get_blocks_by_description(selected)
mapped_blocks = []
invalid_blocks = []

for blk in blocks:
    if all(1 <= i <= v for i in blk):
        mapped = map_user_numbers(user_numbers, blk)
        if mapped:
            mapped_blocks.append(mapped)
    else:
        invalid_blocks.append(blk)

st.write(f"✅ Loaded {len(mapped_blocks)} valid blocks for design `{selected}`.")
if invalid_blocks:
    st.warning(f"⚠️ Skipped {len(invalid_blocks)} blocks (index out of range for base set).")

with st.expander("📦 Show Mapped Blocks", expanded=False):
    for i, block in enumerate(mapped_blocks, start=1):
        st.write(f"Block {i}: {block}")

# Match check
min_hits = st.slider("Minimum hits to display", 0, 6, 1)

st.subheader(f"🎯 Matched Blocks (≥ {min_hits} hits)")

hit_blocks = []
match_counter = {}

for i, block in enumerate(mapped_blocks, start=1):
    hits = sorted(set(block) & set(draw_numbers))
    count = len(hits)
    if count >= min_hits:
        hit_blocks.append((i, block, hits))
    match_counter[count] = match_counter.get(count, 0) + 1

if hit_blocks:
    for i, block, hits in hit_blocks:
        st.write(f"✅ Block {i}: {block} → Hits: {hits} ({len(hits)} match{'es' if len(hits)!=1 else ''})")
else:
    st.info("😔 No matching blocks at this threshold.")

# Prize Summary
st.markdown("---")
prize_table = {
    5: 24000,
    4: 800,
    3: 20
}

jackpot_amount = st.number_input("🏆 Jackpot amount (per 6-hit win)", value=30000000, step=1000000)

six_hit_count = match_counter.get(6, 0)
total_fixed = sum(match_counter.get(k, 0) * prize_table[k] for k in prize_table)
total_jackpot = six_hit_count * jackpot_amount
grand_total = total_fixed + total_jackpot

ticket_price = 20
total_blocks = len(mapped_blocks)
total_cost = total_blocks * ticket_price
net_profit = grand_total - total_cost

st.subheader("💰 Prize Summary")
if six_hit_count > 0:
    st.success(f"🎉 {six_hit_count} block(s) matched ALL 6 — JACKPOT! Each ₱{jackpot_amount:,.2f} → Total: ₱{total_jackpot:,.2f}")
for matches in sorted(prize_table.keys(), reverse=True):
    count = match_counter.get(matches, 0)
    if count:
        prize = prize_table[matches]
        st.write(f"✅ {count} block(s) with {matches} hits × ₱{prize:,.2f} = ₱{count * prize:,.2f}")
st.info(f"📦 Total Blocks: {total_blocks} × ₱{ticket_price} = ₱{total_cost:,.2f}")
st.success(f"🏆 Total Winnings: ₱{grand_total:,.2f}")
st.write(f"💸 Net Profit: {'🟢' if net_profit >= 0 else '🔴'} ₱{net_profit:,.2f}")

# Toast / Popup
draw_sorted = sorted(draw_numbers)
draw_str = ', '.join(str(n) for n in draw_sorted)

if six_hit_count > 0:
    st.toast(
        f"💎 JACKPOT! Drawn: [{draw_str}] — Each Jackpot: ₱{jackpot_amount:,.2f} — Total Won: ₱{grand_total:,.2f}",
        icon="💎"
    )
    st.balloons()
elif grand_total > 0:
    st.toast(
        f"✅ Win! Drawn: [{draw_str}] — Total Won: ₱{grand_total:,.2f}",
        icon="💰"
    )
else:
    st.toast(
        f"🎟️ Checked vs [{draw_str}]. No hits this time, better luck next draw!",
        icon="🎟️"
    )
