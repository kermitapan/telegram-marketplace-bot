async def send_alert(client, classification: dict, raw_text: str, message_link: str | None):
    value = classification['estimated_value_chf']
    weight = classification.get('estimated_weight_kg', 0)
    item = classification['item_description']
    confidence = classification['confidence']
    reason = classification['reason']
    postcode = classification.get('postcode', '')

    carryable = weight == 0 or weight <= 15
    bike_line = f"Bike: yes (~{weight}kg)" if carryable else f"Bike: no (~{weight}kg, consider taxi)"

    lines = [
        "**Free item alert**",
        "",
        f"**Item:** {item}",
        f"**Est. value:** ~CHF {value}",
        f"**Weight:** ~{weight}kg  |  {bike_line}",
        f"**Pickup:** {postcode or 'no postcode'}",
        f"**Confidence:** {confidence}",
        f"**Why:** {reason}",
    ]
    if raw_text:
        lines += ["", "**Original post:**", raw_text[:500]]
    if message_link:
        lines += ["", f"[Open in Telegram]({message_link})"]

    await client.send_message('me', '\n'.join(lines), parse_mode='md')
