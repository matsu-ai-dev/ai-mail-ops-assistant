import os

import pandas as pd
import streamlit as st


# 読み込むCSVのファイル名です。
# 実ログがない公開環境でも画面を確認できるように、サンプルを用意しています。
REAL_LOG_FILE = "mail_sort_log_v3.csv"
SAMPLE_LOG_FILE = "sample_mail_sort_log.csv"


st.set_page_config(
    page_title="AIメール分類ログ",
    layout="wide",
)

st.title("AIメール分類ログビューア")


# 実ログがあれば優先し、なければ公開用サンプルを選びます。
# この判定はCSVを見るだけで、メール接続やOpenAI API呼び出しは行いません。
if os.path.exists(REAL_LOG_FILE):
    log_file = REAL_LOG_FILE
    log_status = "ローカル実行ログを表示中"
elif os.path.exists(SAMPLE_LOG_FILE):
    log_file = SAMPLE_LOG_FILE
    log_status = "公開用デモデータを表示中"
else:
    st.warning("ログファイルがありません")
    st.stop()

# 今どちらのCSVを表示しているか、利用者に分かるように案内します。
st.info(log_status)


# CSVを読み込みます。
# utf-8-sig は、Excelでも開きやすいBOM付きCSVに対応するための指定です。
df = pd.read_csv(log_file, encoding="utf-8-sig")


# 総処理件数を表示します。
st.subheader("総処理件数")
st.metric("件数", len(df))


# 件数集計で使う列名です。
folder_column = "分類予定フォルダ"
move_result_column = "移動結果"
process_mode_column = "処理モード"


# フィルタ条件を画面から選べるようにします。
# 「すべて」を選んだ場合は、その列では絞り込みをしません。
st.subheader("フィルタ")

filtered_df = df.copy()


def get_filter_options(column_name):
    """CSVの列から、フィルタ用の選択肢を作ります。"""
    if column_name not in df.columns:
        return ["すべて"]

    values = df[column_name].dropna().unique()
    sorted_values = sorted(values)
    return ["すべて"] + sorted_values


folder_filter = st.selectbox(
    "分類予定フォルダ",
    get_filter_options(folder_column),
)

move_result_filter = st.selectbox(
    "移動結果",
    get_filter_options(move_result_column),
)

process_mode_filter = st.selectbox(
    "処理モード",
    get_filter_options(process_mode_column),
)


# 選ばれた条件に合わせて、表示用データを絞り込みます。
if folder_filter != "すべて" and folder_column in filtered_df.columns:
    filtered_df = filtered_df[filtered_df[folder_column] == folder_filter]

if move_result_filter != "すべて" and move_result_column in filtered_df.columns:
    filtered_df = filtered_df[filtered_df[move_result_column] == move_result_filter]

if process_mode_filter != "すべて" and process_mode_column in filtered_df.columns:
    filtered_df = filtered_df[filtered_df[process_mode_column] == process_mode_filter]


# フィルタ後に何件残っているかを表示します。
st.subheader("フィルタ後の件数")
st.metric("件数", len(filtered_df))


st.subheader("分類予定フォルダごとの件数")
if folder_column in filtered_df.columns:
    folder_counts = filtered_df[folder_column].value_counts().reset_index()
    folder_counts.columns = ["分類予定フォルダ", "件数"]
    st.dataframe(folder_counts, use_container_width=True)
else:
    st.info(f"CSVに「{folder_column}」列がありません")


st.subheader("移動結果ごとの件数")
if move_result_column in filtered_df.columns:
    move_result_counts = filtered_df[move_result_column].value_counts().reset_index()
    move_result_counts.columns = ["移動結果", "件数"]
    st.dataframe(move_result_counts, use_container_width=True)
else:
    st.info(f"CSVに「{move_result_column}」列がありません")


st.subheader("処理モードごとの件数")
if process_mode_column in filtered_df.columns:
    process_mode_counts = filtered_df[process_mode_column].value_counts().reset_index()
    process_mode_counts.columns = ["処理モード", "件数"]
    st.dataframe(process_mode_counts, use_container_width=True)
else:
    st.info(f"CSVに「{process_mode_column}」列がありません")


st.subheader("ログ一覧")
st.dataframe(filtered_df, use_container_width=True)
