import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- 初期設定 ---
if 'transactions' not in st.session_state:
    # 履歴データフレーム
    st.session_state.transactions = pd.DataFrame(columns=['日時', 'タイプ', '対象者', '金額', 'メモ'])

if 'users' not in st.session_state:
    st.session_state.users = ["自分(B)", "友達(C)"]

if 'lender_name' not in st.session_state:
    st.session_state.lender_name = "Aさん"

# --- 関数：履歴に「取引後残高」を計算して付与する ---
def get_history_with_balance():
    if st.session_state.transactions.empty:
        return st.session_state.transactions
    
    # 時系列順に並べて残高を計算
    df = st.session_state.transactions.copy()
    df['日時'] = pd.to_datetime(df['日時'])
    df = df.sort_values('日時')
    
    # ユーザーごとの累計残高を計算
    current_balances = {user: 0 for user in st.session_state.users}
    balance_after = []
    
    for _, row in df.iterrows():
        name = row['対象者']
        # ユーザーが現在存在しない場合も考慮
        if name not in current_balances:
            current_balances[name] = 0
        current_balances[name] += row['金額']
        balance_after.append(current_balances[name])
    
    df['取引後残高'] = balance_after
    return df.sort_values('日時', ascending=False) # 最新順に戻す

# --- サイドバー：設定エリア ---
st.sidebar.title("⚙️ 設定・メンバー管理")

# 1. 貸し手の名前変更
st.sidebar.subheader("貸している人の名前")
new_lender_name = st.sidebar.text_input("貸し手 (ハブ役)", value=st.session_state.lender_name)
if new_lender_name != st.session_state.lender_name:
    st.session_state.lender_name = new_lender_name
    st.rerun()

st.sidebar.markdown("---")

# 2. 借り手の名前変更
st.sidebar.subheader("借りている人の名前")
for i, old_name in enumerate(st.session_state.users):
    new_name = st.sidebar.text_input(f"メンバー {i+1}", value=old_name, key=f"user_input_{i}")
    if new_name != old_name:
        st.session_state.transactions['対象者'] = st.session_state.transactions['対象者'].replace(old_name, new_name)
        st.session_state.users[i] = new_name
        st.rerun()

# メンバー追加
new_member = st.sidebar.text_input("新規メンバー追加")
if st.sidebar.button("追加"):
    if new_member and new_member not in st.session_state.users:
        st.session_state.users.append(new_member)
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("修正・取り消し")

# 【新機能】1つ戻る（直前の操作を取り消す）
if st.sidebar.button("↩️ 直前の操作を1つ取り消す"):
    if not st.session_state.transactions.empty:
        # 末尾の行（最新の操作）を削除
        st.session_state.transactions = st.session_state.transactions[:-1]
        st.sidebar.success("直前の入力を取り消しました！")
        st.rerun()
    else:
        st.sidebar.warning("取り消す履歴がありません。")

st.sidebar.markdown("---")
st.sidebar.subheader("データ管理")

# 借金を0にしてリセット（履歴保存）
if st.sidebar.button("💰 今の借金をすべて0にする (清算)"):
    current_balances = {user: 0 for user in st.session_state.users}
    for _, row in st.session_state.transactions.iterrows():
        name = row['対象者']
        if name in current_balances:
            current_balances[name] += row['金額']
    
    reset_entries = []
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for user, bal in current_balances.items():
        if bal != 0:
            reset_entries.append({
                '日時': now, 'タイプ': '清算/リセット', 
                '対象者': user, '金額': -bal, 'メモ': '一括清算（履歴保存）'
            })
    
    if reset_entries:
        st.session_state.transactions = pd.concat([st.session_state.transactions, pd.DataFrame(reset_entries)], ignore_index=True)
        st.sidebar.success("全員の借金を0円にリセットしました。")
        st.rerun()

# （ここに以前あった削除ボタンは削除しました）

# --- メインエリア ---
lender = st.session_state.lender_name
st.title(f"💰 {lender} 経由の借金管理")

# 現在の状況計算
balance = {user: 0 for user in st.session_state.users}
for _, row in st.session_state.transactions.iterrows():
    name = row['対象者']
    if name in balance:
        balance[name] += row['金額']

df_balance = pd.DataFrame(list(balance.items()), columns=['名前', '借金残高'])
total_lent = df_balance['借金残高'].sum()

# 合計表示
col1, col2 = st.columns(2)
col1.metric(f"{lender} が貸している総額", f"{total_lent:,} 円")
col2.info("サイドバーの「戻る」ボタンで、間違えた入力を消せます。")

# グラフ表示
if total_lent != 0:
    fig = px.bar(df_balance, x='名前', y='借金残高', title=f"{lender} への借金状況", 
                 color='借金残高', color_continuous_scale="Reds")
    st.plotly_chart(fig, use_container_width=True)

# --- 取引入力エリア ---
st.markdown("---")
st.subheader("📝 取引を入力")

tab1, tab2, tab3 = st.tabs(["💸 借金・割り勘", "↩️ 返済", "🔀 友達間の移動"])

with tab1:
    with st.form("borrow_form", clear_on_submit=True):
        target_users = st.multiselect("対象者", st.session_state.users, default=st.session_state.users)
        amount_total = st.number_input("金額", min_value=0, step=100)
        split_method = st.radio("入力方法", ["全員にこの金額を追加", "合計金額を全員で割る"])
        desc_borrow = st.text_input("内容", "割り勘")
        if st.form_submit_button("登録"):
            if target_users and amount_total > 0:
                amount_per = int(amount_total / len(target_users)) if split_method == "合計金額を全員で割る" else amount_total
                new_entries = pd.DataFrame([{
                    '日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'タイプ': '借入', '対象者': user, '金額': amount_per, 'メモ': desc_borrow
                } for user in target_users])
                st.session_state.transactions = pd.concat([st.session_state.transactions, new_entries], ignore_index=True)
                st.rerun()

with tab2:
    with st.form("repay_form", clear_on_submit=True):
        payer = st.selectbox("返済する人", st.session_state.users)
        amount_repay = st.number_input("返済額", min_value=0, step=100)
        desc_repay = st.text_input("メモ", "現金返済")
        if st.form_submit_button("返済を記録"):
            if amount_repay > 0:
                entry = pd.DataFrame([{'日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'タイプ': '返済', '対象者': payer, '金額': -amount_repay, 'メモ': desc_repay}])
                st.session_state.transactions = pd.concat([st.session_state.transactions, entry], ignore_index=True)
                st.rerun()

with tab3:
    st.caption("例：BさんがCさんの分を払ってあげた場合など、借金の付け替えを行います。")
    with st.form("transfer_form", clear_on_submit=True):
        taker = st.selectbox("お金を渡した人 (借金が増える)", st.session_state.users)
        reducer = st.selectbox("お金をもらった人 (借金が減る)", st.session_state.users)
        amt = st.number_input("移動金額", min_value=0, step=100)
        # 【新機能】理由入力欄
        reason = st.text_input("移動の理由", placeholder="ランチ代の立て替え、など")
        
        if st.form_submit_button("数値移動を実行"):
            if amt > 0 and taker != reducer:
                # 理由が空の場合は自動で補完
                memo_taker = f"{reducer}への支払い" + (f" ({reason})" if reason else "")
                memo_reducer = f"{taker}からの受取" + (f" ({reason})" if reason else "")

                entries = pd.DataFrame([
                    {'日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'タイプ': '移動(+)', '対象者': taker, '金額': amt, 'メモ': memo_taker},
                    {'日時': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'タイプ': '移動(-)', '対象者': reducer, '金額': -amt, 'メモ': memo_reducer}
                ])
                st.session_state.transactions = pd.concat([st.session_state.transactions, entries], ignore_index=True)
                st.rerun()

# --- 履歴表示（取引後残高付き） ---
st.markdown("---")
st.subheader("📜 取引履歴 (最新順)")
history_df = get_history_with_balance()

if not history_df.empty:
    history_df = history_df[['日時', '対象者', 'タイプ', '金額', '取引後残高', 'メモ']]
    st.dataframe(history_df, use_container_width=True)
else:
    st.write("履歴はまだありません。")

# CSV保存
csv = st.session_state.transactions.to_csv(index=False).encode('utf-8-sig')
st.download_button("履歴をCSV保存", data=csv, file_name='debt_history.csv', mime='text/csv')