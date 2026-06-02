import os
from datetime import datetime
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

BOT_ID = os.environ.get("BOT_ID")

agent_totals = {}
team_totals = {}
company_total = 0.0


def send_message(text: str) -> None:
    if not BOT_ID:
        print("ERROR: BOT_ID environment variable is missing.")
        return

    payload = {
        "bot_id": BOT_ID,
        "text": text
    }

    try:
        resp = requests.post("https://api.groupme.com/v3/bots/post", json=payload, timeout=10)
        print(f"GroupMe post response: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"ERROR sending message to GroupMe: {e}")


def money(value: float) -> str:
    return f"${value:,.2f}"


def reset_totals() -> str:
    global agent_totals, team_totals, company_total

    agent_totals = {}
    team_totals = {}
    company_total = 0.0

    return "✅ Totals reset successfully."


def show_totals() -> str:
    if company_total == 0:
        return "📊 No sales recorded yet."

    lines = ["📊 Current Totals", ""]

    if agent_totals:
        lines.append("Agents:")
        for agent, total in agent_totals.items():
            lines.append(f"- {agent}: {money(total)}")

    if team_totals:
        lines.append("")
        lines.append("Teams:")
        for team, total in team_totals.items():
            lines.append(f"- {team}: {money(total)}")

    lines.append("")
    lines.append(f"Company total: {money(company_total)}")

    return "\n".join(lines)


def parse_sale_message(text: str, sender_name: str) -> str | None:
    global company_total

    clean_text = text.strip()

    if clean_text.lower() in ["/reset", "reset totals", "reset"]:
        return reset_totals()

    if clean_text.lower() in ["/totals", "totals", "show totals"]:
        return show_totals()

    if clean_text.lower() in ["/help", "help"]:
        return (
            "Sales Bot Commands:\n\n"
            "Record a sale with 4 lines:\n"
            "Carrier\n"
            "$AP\n"
            "Product\n"
            "Team\n\n"
            "Commands:\n"
            "/totals - show current totals\n"
            "/reset - reset all totals"
        )

    lines = [line.strip() for line in clean_text.split("\n") if line.strip()]

    # Ignore normal chat messages instead of spamming errors
    if len(lines) != 4:
        return None

    carrier = lines[0]

    try:
        ap_value = float(lines[1].replace("$", "").replace(",", ""))
    except ValueError:
        return "⚠️ I could not read the AP amount. Example: $3,828.80"

    product = lines[2]
    team = lines[3]

    agent_totals[sender_name] = agent_totals.get(sender_name, 0.0) + ap_value
    team_totals[team] = team_totals.get(team, 0.0) + ap_value
    company_total += ap_value

    eft_date = datetime.now().strftime("%Y-%m-%d")

    return "\n".join([
        f"Carrier: {carrier}",
        f"AP: {money(ap_value)}",
        f"EFT: {eft_date}",
        f"Team: {team}",
        f"Agent: {sender_name}",
        "",
        "✅ Close Recorded",
        f"Agent total: {money(agent_totals[sender_name])}",
        f"{team} total: {money(team_totals[team])}",
        f"Company total: {money(company_total)}"
    ])


@app.route("/", methods=["GET"])
def home():
    return "Sales Bot is running ✅", 200


@app.route("/groupme_callback", methods=["POST"])
def groupme_callback():
    data = request.get_json(silent=True)

    print("Incoming GroupMe data:", data)

    if not data:
        return jsonify({}), 200

    if data.get("sender_type") == "bot":
        return jsonify({}), 200

    text = data.get("text", "")
    sender_name = data.get("name", "Agent")

    response_message = parse_sale_message(text, sender_name)

    if response_message:
        send_message(response_message)

    return jsonify({}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
