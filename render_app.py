"""Render web entry point for the Alice/OpenAI webhook."""
import hmac
import os

from flask import Flask, jsonify, request

from api.index import handler_alice

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


@app.route("/", methods=["GET"])
def health():
    # Simple health check; does not reveal secrets or configuration.
    return "Alice webhook is running", 200


@app.route("/", methods=["POST"])
def alice_webhook():
    expected = os.environ.get("ALICE_WEBHOOK_TOKEN", "").strip()
    supplied = request.args.get("token", "")
    if not expected or not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "not found"}), 404

    skill_id = os.environ.get("ALICE_SKILL_ID", "").strip()
    if not skill_id:
        return jsonify({"error": "ALICE_SKILL_ID is not configured"}), 503

    event = request.get_json(silent=True)
    if not isinstance(event, dict):
        return jsonify({"error": "invalid JSON"}), 400

    session = event.get("session") or {}
    if not isinstance(session, dict) or session.get("skill_id") != skill_id:
        return jsonify({"error": "invalid skill"}), 403

    try:
        result = handler_alice(event, None)
        return jsonify(result), 200
    except Exception:
        app.logger.exception("Unhandled webhook error")
        return jsonify({
            "version": "1.0",
            "response": {
                "text": "Произошла внутренняя ошибка. Попробуйте позже.",
                "end_session": False
            }
        }), 200


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "request too large"}), 413
