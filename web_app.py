import streamlit as st
import pandas as pd
import re
import random
import io

# --- 頁面設定 ---
st.set_page_config(page_title="自動化提示詞填充器 (Web版)", layout="wide")

# --- 初始化 Session State (用來記憶變數) ---
if 'history' not in st.session_state:
    st.session_state.history = [] # 儲存歷史紀錄
if 'detected_tags' not in st.session_state:
    st.session_state.detected_tags = []
if 'df_raw' not in st.session_state:
    st.session_state.df_raw = None
if 'column_pools' not in st.session_state:
    st.session_state.column_pools = {}
if 'generated_text' not in st.session_state:
    st.session_state.generated_text = ""

# --- 標題 ---
st.title("🎨 自動化提示詞填充器 (Web版)")

# === 步驟 1: 輸入與偵測 ===
st.header("步驟 1: 輸入提示詞")

# 定義一個 callback 函數來處理歷史回填
def load_history_to_prompt():
    # 這裡可以實作將歷史填回輸入框，但在 Web 模式下，
    # 通常是將結果顯示在結果區，讓使用者複製，比較符合網頁操作邏輯。
    pass

prompt_text = st.text_area(
    "輸入提示詞模板 (使用 [ ] 包裹變數)", 
    value="A frame-filling composition.\nAppearance: Wearing [上衣顏色] [上衣類型]",
    height=150,
    key="prompt_input"
)

if st.button("🔍 偵測 [ ] 標籤"):
    tags = re.findall(r'\[(.*?)\]', prompt_text)
    # 去除重複並保持順序
    st.session_state.detected_tags = list(dict.fromkeys(tags))
    
    if st.session_state.detected_tags:
        st.success(f"偵測到標籤: {', '.join(st.session_state.detected_tags)}")
    else:
        st.error("未偵測到任何 [ ] 標籤")

# === 步驟 2: CSV 上傳與預覽 ===
st.header("步驟 2: 上傳 CSV")

uploaded_file = st.file_uploader("選擇 CSV 檔案", type=['csv'])

if uploaded_file is not None:
    try:
        # 嘗試讀取 (處理編碼)
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0) # 重置指標
            df = pd.read_csv(uploaded_file, encoding='cp950')
        
        # 處理空值
        df = df.replace(r'^\s*$', pd.NA, regex=True)
        st.session_state.df_raw = df
        
        # 顯示預覽 (只顯示前 5 行)
        st.dataframe(df.head(), height=150, use_container_width=True)
        
        # 統計欄位
        if st.session_state.detected_tags:
            missing = [t for t in st.session_state.detected_tags if t not in df.columns]
            if missing:
                st.error(f"❌ CSV 缺少欄位: {missing}")
                st.session_state.column_pools = {}
            else:
                pools = {}
                stats_msg = []
                for tag in st.session_state.detected_tags:
                    valid_items = df[tag].dropna().tolist()
                    valid_items = [str(x).strip() for x in valid_items if str(x).strip() != ""]
                    pools[tag] = valid_items
                    stats_msg.append(f"**[{tag}]**: {len(valid_items)}個")
                
                st.session_state.column_pools = pools
                st.info(" | ".join(stats_msg))
    except Exception as e:
        st.error(f"讀取失敗: {e}")

# === 步驟 3: 生成與結果 ===
st.header("步驟 3: 生成結果")

col1, col2 = st.columns([1, 1])

with col1:
    if st.button("🎲 隨機生成 (Mix & Match)", type="primary", disabled=not st.session_state.column_pools):
        # 執行生成邏輯
        pools = st.session_state.column_pools
        tags = st.session_state.detected_tags
        
        # 簡單防重複邏輯 (Web版為了效能，這裡做輕量化處理)
        max_attempts = 1000
        found = False
        selected_indices = ()
        existing_indices = {item['indices'] for item in st.session_state.history}

        for _ in range(max_attempts):
            temp = []
            for tag in tags:
                if pools[tag]:
                    temp.append(random.randint(0, len(pools[tag]) - 1))
                else:
                    temp.append(-1) # 空欄位
            current_tuple = tuple(temp)
            if current_tuple not in existing_indices:
                selected_indices = current_tuple
                found = True
                break
        
        if found:
            # 替換文字
            res_text = prompt_text
            desc_list = []
            display_idx = []
            
            for i, tag in enumerate(tags):
                idx = selected_indices[i]
                val = pools[tag][idx]
                res_text = res_text.replace(f"[{tag}]", val, 1)
                desc_list.append(f"{tag}:{val}")
                display_idx.append(str(idx + 1))
            
            # 加入編號
            no = len(st.session_state.history) + 1
            final_text = f"No.{no:03d} {res_text}"
            st.session_state.generated_text = final_text
            
            # 存入歷史
            summary = f"No.{no} | [{'-'.join(display_idx)}] | {', '.join(desc_list)}"
            st.session_state.history.insert(0, {
                'indices': selected_indices,
                'summary': summary,
                'full_text': final_text
            })
        else:
            st.warning("已窮盡所有組合或運氣不佳")

    # 顯示結果文字框
    st.text_area("生成結果 (可直接複製)", value=st.session_state.generated_text, height=150)

with col2:
    st.subheader("📋 抽選歷史")
    
    # 匯出按鈕
    if st.session_state.history:
        # 製作 CSV 用於下載
        export_list = []
        for item in st.session_state.history:
            export_list.append({
                'Summary': item['summary'],
                'Full_Prompt': item['full_text']
            })
        df_export = pd.DataFrame(export_list)
        csv_bytes = df_export.to_csv(index=False).encode('utf-8-sig')
        
        st.download_button(
            label="📥 下載歷史紀錄 (CSV)",
            data=csv_bytes,
            file_name="history.csv",
            mime="text/csv",
        )
        
        if st.button("🗑️ 清空歷史"):
            st.session_state.history = []
            st.rerun()

    # 顯示歷史列表 (使用 dataframe 比較整齊，或用 radio button 模擬點選)
    if st.session_state.history:
        # 這裡我們用一個 selectbox 讓使用者選擇歷史，選中後顯示在下方
        history_options = [item['summary'] for item in st.session_state.history]
        selected_option = st.selectbox("選擇歷史紀錄以回填/檢視:", history_options)
        
        # 找到對應的完整文字
        for item in st.session_state.history:
            if item['summary'] == selected_option:
                st.info(f"回顧內容:\n{item['full_text']}")
                # Web 限制：很難直接逆向寫回上方的 input，通常是用顯示的方式讓使用者複製
                break