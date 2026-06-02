import os
from datetime import datetime
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

BOT_ID = os.environ.get("BOT_ID")

agent_totals = {}
team_totals = {}
company_total = 0.0
sales_history = []


def money(value: float) -> str:
    return f"${value:,.2f}"


def send_message(text: str) -> None:
    if not BOT_ID:
        print("ERROR: BOT_ID environment variable is missing.")
        return

    payload = {
        "bot_id": BOT_ID,
        "text": text
    }

    try:
        response = requests.post(
            "https://api.groupme.com/v3/bots/post",
            json=payload,
            timeout=10
        )
        print(f"GroupMe response: {response.status_code} {response.text}")
    except Exception as e:
        print(f"ERROR sending message to GroupMe: {e}")


def help_message() -> str:
    return (
        "🤖 Sales Bot Commands\n\n"
        "Record a sale using 4 lines:\n"
        "Carrier\n"
        "$AP\n"
        "Product\n"
        "Team\n\n"
        "Example:\n"
        "Moo\n"
        "$3,828.80\n"
        "IMM\n"
        "Trendsetters\n\n"
        "Commands:\n"
        "/totals - Show all totals\n"
        "/leaderboard - Rank agents\n"
        "/teams - Show team totals\n"
        "/reset - Reset all totals\n"
        "/delete - Delete your last sale\n"
        "/help - Show this menu"
    )


def reset_totals() -> str:
    global agent_totals, team_totals, company_total, sales_history

    agent_totals = {}
    team_totals = {}
    company_total = 0.0
    sales_history = []

    return "✅ All totals have been reset."


def show_totals() -> str:
    if company_total == 0:
        return "📊 No sales recorded yet."

    lines = ["📊 Current Totals", ""]

    lines.append("Company:")
    lines.append(f"Allen & Associates total: {money(company_total)}")

    if team_totals:
        lines.append("")
        lines.append("Teams:")
        for team, total in sorted(team_totals.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {team}: {money(total)}")

    if agent_totals:
        lines.append("")
        lines.append("Agents:")
        for agent, total in sorted(agent_totals.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {agent}: {money(total)}")

    return "\n".join(lines)


def show_leaderboard() -> str:
    if not agent_totals:
        return "🏆 No agents on the leaderboard yet."

    lines = ["🏆 Agent Leaderboard", ""]

    sorted_agents = sorted(agent_totals.items(), key=lambda x: x[1], reverse=True)

    medals = ["🥇", "🥈", "🥉"]

    for index, (agent, total) in enumerate(sorted_agents, start=1):
        medal = medals[index - 1] if index <= 3 else f"{index}."
        lines.append(f"{medal} {agent}: {money(total)}")

    return "\n".join(lines)


def show_teams() -> str:
    if not team_totals:
        return "📊 No team totals yet."

    lines = ["📊 Team Totals", ""]

    sorted_teams = sorted(team_totals.items(), key=lambda x: x[1], reverse=True)

    for team, total in sorted_teams:
        lines.append(f"- {team}: {money(total)}")

    return "\n".join(lines)


def delete_last_sale(sender_name: str) -> str:
    global company_total

    for sale in reversed(sales_history):
        if sale["agent"] == sender_name and not sale.get("deleted", False):
            sale["deleted"] = True

            amount = sale["amount"]
            team = sale["team"]

            agent_totals[sender_name] = max(0, agent_totals.get(sender_name, 0) - amount)
            team_totals[team] = max(0, team_totals.get(team, 0) - amount)
            company_total = max(0, company_total - amount)

            if agent_totals[sender_name] == 0:
                agent_totals.pop(sender_name, None)

            if team_totals.get(team) == 0:
                team_totals.pop(team, None)

            return (
                "🗑️ Last sale deleted.\n"
                f"Removed: {money(amount)}\n"
                f"Agent total: {money(agent_totals.get(sender_name, 0))}\n"
                f"Company total: {money(company_total)}"
            )

    return "⚠️ I could not find a sale from you to delete."


def parse_sale_message(text: str, sender_name: str) -> str | None:
    global company_total

    if not text:
        return None

    clean_text = text.strip()
    command = clean_text.lower()

    if command in ["/help", "help"]:
        return help_message()

    if command in ["/reset", "reset", "reset totals"]:
        return reset_totals()

    if command in ["/totals", "totals", "show totals"]:
        return show_totals()

    if command in ["/leaderboard", "leaderboard", "/rank", "rank"]:
        return show_leaderboard()

    if command in ["/teams", "teams", "team totals"]:
        return show_teams()

    if command in ["/delete", "delete", "undo", "/undo"]:
        return delete_last_sale(sender_name)

    lines = [line.strip() for line in clean_text.split("\n") if line.strip()]

    # Ignore normal chat messages.
    if len(lines) != 4:
        return None

    carrier = lines[0]

    try:
        ap_value = float(
            lines[1]
            .replace("$", "")
            .replace(",", "")
            .replace(" ", "")
        )
    except ValueError:
        return "⚠️ I could not read the AP amount. Example: $3,828.80"

    product = lines[2]
    team = lines[3]

    if ap_value <= 0:
        return "⚠️ AP amount must be greater than $0."

    agent_totals[sender_name] = agent_totals.get(sender_name, 0.0) + ap_value
    team_totals[team] = team_totals.get(team, 0.0) + ap_value
    company_total += ap_value

    sale = {
        "agent": sender_name,
        "carrier": carrier,
        "amount": ap_value,
        "product": product,
        "team": team,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "deleted": False
    }

    sales_history.append(sale)

    return "\n".join([
        f"Carrier: {carrier}",
        f"AP: {money(ap_value)}",
        f"EFT: {sale['date']}",
        f"Team: {team}",
        f"Agent: {sender_name}",
        "",
        "✅ Close Recorded",
        f"Agent total: {money(agent_totals[sender_name])}",
        f"{team} total: {money(team_totals[team])}",
        f"Allen & Associates total: {money(company_total)}"
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
