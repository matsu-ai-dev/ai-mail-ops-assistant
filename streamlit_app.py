import streamlit as st, requests
from PIL import Image

st.title("🖼️ → 📝 商品説明ジェネレータ")

file = st.file_uploader("商品画像をアップロード", type=["png", "jpg", "jpeg"])

if st.button("説明文を生成") and file:
    img = Image.open(file)
    st.image(img, width=300)

    files = {"file": (file.name, file.getvalue(), file.type)}
    with st.spinner("GPT-4o Vision が生成中…"):
        res = requests.post("http://localhost:8000/generate", files=files)

    if res.status_code == 200:
        st.success(res.json()["description"])
    else:
        st.error(f"エラー: {res.text}")
