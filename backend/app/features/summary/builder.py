SECTIONS = [
    ("Company & Vehicle Details", [
        ("company_name", "Company Name"),
        ("vehicle_number", "Vehicle Number"),
        ("brand", "Brand"),
        ("line_mark", "Line Mark"),
        ("weight", "Weight"),
    ]),
    ("Banana Hand & Cluster Quantities", [
        ("four_hand", "Four-Hand Quantity"),
        ("five_hand", "Five-Hand Quantity"),
        ("six_hand", "Six-Hand Quantity"),
        ("eight_hand", "Eight-Hand Quantity"),
        ("cluster", "Cluster Quantity"),
        ("total", "Total Quantity"),
    ]),
    ("Additional Information", [
        ("remarks", "Remarks"),
        ("labor_name", "Labor Name"),
        ("vehicle_out_time", "Vehicle Out Time"),
        ("vehicle_in_time", "Vehicle In Time"),
        ("vehicle_for_storage", "Vehicle for Storage"),
        ("vehicle_receiver_name", "Vehicle Receiver Name"),
    ]),
]


def build_summary(fields: dict) -> str:
    """Template-only summary builder, no LLM — per spec, the LLM never touches confirmation
    text. `fields` must already be validated and `total` already computed by
    validation/calculator.py before this is called."""
    all_keys = [key for _, field_list in SECTIONS for key, _ in field_list]
    missing_keys = [key for key in all_keys if key not in fields]
    if missing_keys:
        raise ValueError(f"Missing fields for summary: {', '.join(missing_keys)}")

    lines = ["Please confirm the following details:", ""]
    for section_title, field_list in SECTIONS:
        lines.append(f"{section_title}:")
        for key, label in field_list:
            value = fields.get(key)
            display = "—" if value in (None, "") else value
            lines.append(f"  {label}: {display}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
