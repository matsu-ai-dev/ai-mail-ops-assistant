from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import openai, base64, io, textwrap
from PIL import Image

app = FastAPI(title="Vision 商品説明 API")

# 画像 → base64 変換ヘルパ
def img_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    # サイズが大き過ぎる場合は 800 px にリサイズ (コスト削減)
    if max(img.size) > 800:
        img.thumbnail((800, 800))
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

@app.post("/generate")
async def generate(
    file: UploadFile = File(...),
    # 追加でヒントを受け取れるようにしておく（任意）
    name: str | None = None,
    material: str | None = None,
    color: str | None = None,
):
    # ① 形式チェック
    if file.content_type not in ("image/png", "image/jpeg"):
        raise HTTPException(400, "PNG / JPEG をアップロードしてください")

    # ② 画像読み込み
    img = Image.open(io.BytesIO(await file.read()))
    img_b64 = img_to_b64(img)

    # ③ ユーザーヒントを組み立てる
    extra = []
    if name:
        extra.append(f"商品カテゴリ: {name}")
    if material:
        extra.append(f"素材: {material}")
    if color:
        extra.append(f"色: {color}")
    hint_text = " / ".join(extra) if extra else " "

    # ④ Vision プロンプト
    system_prompt = textwrap.dedent(
        """
        あなたは優秀な EC ライターです。
        画像に写っている商品の特徴を分析し、
        日本語で 120〜150 字の説明文を作成してください。
        ・誇張表現は禁止
        ・リスクがある推測は避ける
        ・箇条書きは使わず 1 文〜2 文
        """
    )
    user_prompt = (
        "以下の画像を見て EC サイト向け商品説明文を生成してください。"
        "写真だけでは不明な情報は推測しないでください。"
        f"{hint_text}"
    )

    try:
        rsp = openai.chat.completions.create(
            model="gpt-4o-mini",  # 必要なら gpt-4o に変更
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img_b64}},
                    ],
                },
            ],
            max_tokens=180,
        )
        desc = rsp.choices[0].message.content.strip()

    except openai.OpenAIError as e:
        # Vision がブロック or クォータ不足など
        raise HTTPException(500, f"OpenAI Error: {e}")

    return JSONResponse({"description": desc})
