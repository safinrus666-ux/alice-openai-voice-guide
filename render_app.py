
import os
import hmac
import json
import urllib.request
import urllib.error

from flask import Flask, request, jsonify

app = Flask(__name__)

SYSTEM_PROMPT = (
    "Ты голосовой помощник Алисы. "
    "Отвечай по-русски, кратко, понятно и естественно. "
    "Не используй Markdown и эмодзи."
)


def alice_response(text, end_session=False):
    return {
        "version": "1.0",
        "response": {
            "text": text[:1024],
            "end_session": end_session
        }
    }


@app.route("/", methods=["GET"])
def health():
    return "Alice webhook is running", 200


@app.route("/", methods=["POST"])
def webhook():
    expected = os.getenv("ALICE_WEBHOOK_TOKEN", "")
    supplied = request.args.get("token", "")

    if not expected or not hmac.compare_digest(expected, supplied):
        return jsonify({"error": "Unauthorized"}), 403

    event = request.get_json(silent=True)

    if not isinstance(event, dict):
        return jsonify({"error": "Invalid JSON"}), 400

    session = event.get("session", {})
    skill_id = os.getenv("ALICE_SKILL_ID", "")

    if not skill_id or session.get("skill_id") != skill_id:
        return jsonify({"error": "Invalid skill"}), 403

    user_request = event.get("request", {})
    message = user_request.get("command", "").strip()

    if not message:
        return jsonify(alice_response(
            "Привет! Я готов отвечать на вопросы."
        ))

    if message.lower() in ("выход", "стоп", "хватит"):
        return jsonify(alice_response("До встречи!", True))

    api_key = os.getenv("OPENROUTER_API_KEY", "")

    if not api_key:
        return jsonify(alice_response(
            "Ключ OpenRouter пока не настроен."
        ))

    payload = {
        "model": "liquid/lfm-3-1.7b:free",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ],
        "max_tokens": 150
    }

    api_request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(api_request, timeout=4) as response:
            data = json.load(response)

        answer = data["choices"][0]["message"]["content"]

        if not isinstance(answer, str) or not answer.strip():
            answer = "Не удалось получить ответ. Повторите вопрос."

    except urllib.error.HTTPError as error:
        app.logger.warning("OpenRouter status: %s", error.code)
        if error.code == 429:
            answer = "Бесплатный лимит запросов исчерпан. Попробуйте позже."
        else:
            answer = "Сервис нейросети временно недоступен."

    except Exception:
        app.logger.exception("OpenRouter request failed")
        answer = "Не удалось получить ответ. Попробуйте ещё раз."

    return jsonify(alice_response(answer))
