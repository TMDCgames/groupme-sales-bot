import os
from datetime import datetime
from flask import Flask, request, jsonify
import requests

# Flask app setup
app = Flask(__name__)

# Bot ID from environment variable (required for posting messages back to GroupMe)
BOT_ID = os.environ.get('BOT_ID')

# In-memory stores for cumulative totals
agent_totals = {}
team_totals = {}
company_total = 0.0


def send_message(text: str) -> None:
    """Send a message using the GroupMe Bot API."""
    if not BOT_ID:
        print("Error: BOT_ID environment variable is not set.")
        return
    payload = {
        "bot_id": BOT_ID,
        "text": text
    }
    # GroupMe Bot post endpoint
    url = "https://api.groupme.com/v3/bots/post"
    resp = requests.post(url, json=payload)
    if resp.status_code != 202:
        print(f"Failed to send message: {resp.status_code} {resp.text}")


def parse_sale_message(text: str, sender_name: str) -> str:
    """
    Parse the incoming sale message into structured fields and update totals.
    Expected message format (each part on its own line):
    Carrier\nAP\nProduct\nTeam
    Example:
    Moo
    $3,828.8
    IMM
    Trendsetters
    """
    global company_total

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) < 4:
        return "⚠️ Unable to parse sale message. Please follow the expected format."

    carrier = lines[0]
    # Remove currency symbols and commas, then convert to float
    try:
        ap_value = float(lines[1].replace('$', '').replace(',', ''))
    except ValueError:
        return "⚠️ Unable to parse AP amount."
    product = lines[2]
    team = lines[3]

    # Update totals
    agent_totals[sender_name] = agent_totals.get(sender_name, 0.0) + ap_value
    team_totals[team] = team_totals.get(team, 0.0) + ap_value
    company_total += ap_value

    # Format totals as currency strings
    agent_total_str = f"${agent_totals[sender_name]:,.2f}"
    team_total_str = f"${team_totals[team]:,.2f}"
    company_total_str = f"${company_total:,.2f}"

    # Use today’s date in ISO format for EFT field
    eft_date = datetime.now().strftime("%Y-%m-%d")

    # Construct response message
    response_lines = [
        f"Carrier: {carrier}",
        f"AP: ${ap_value:,.2f}",
        f"EFT: {eft_date}",
        f"Team: {team}",
        f"Agent: {sender_name}",
        "\U00002705 Close Recorded",  # ✅ check mark emoji
        f"Agent total: {agent_total_str}",
        f"{team} total: {team_total_str}",
        f"Company total: {company_total_str}"
    ]
    return "\n".join(response_lines)


@app.route('/groupme_callback', methods=['POST'])
def groupme_callback():
    """Endpoint for receiving GroupMe webhook events."""
    data = request.get_json()
    if not data:
        return jsonify({}), 200

    # Ignore messages sent by bots
    if data.get('sender_type') == 'bot':
        return jsonify({}), 200

    text = data.get('text', '')
    sender_name = data.get('name', 'Agent')

    # Parse the sale message and build a response
    response_message = parse_sale_message(text, sender_name)

    # Send the response back to the GroupMe group
    send_message(response_message)

    return jsonify({}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
