# In utils/ocr_utils.py, replace the parse_ocr_text function with this one.

def parse_ocr_text(text: str):
    parsed_data = {
        "vendor": "N/A", "date": "N/A", "total_amount": 0.0,
        "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
    }

    # --- Stage 1: Basic Field Extraction (Vendor & Date) ---
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        for line in lines:
            if line.lower().startswith("sold by / vendu par:"):
                parsed_data["vendor"] = line.split(":", 1)[1].strip()
                break
        if parsed_data["vendor"] == "N/A" and len(lines[0]) < 50:
            parsed_data["vendor"] = lines[0]

    date_pattern = r'(?i)(?:Date|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4})'
    date_match = re.search(date_pattern, text)
    if date_match: parsed_data["date"] = date_match.group(1).strip()

    # --- Stage 2: Mathematical parsing for Total, Subtotal, and Taxes ---
    all_amounts = sorted(list(set([float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)])), reverse=True)
    
    if len(all_amounts) >= 2:
        grand_total = all_amounts[0]
        subtotal = all_amounts[1]
        
        parsed_data["total_amount"] = grand_total
        
        # Calculate the expected sum of all taxes
        expected_tax_sum = round(grand_total - subtotal, 2)
        
        # --- LOGIC CORRECTED HERE ---
        # Find all other smaller numbers that could be taxes,
        # but EXCLUDE the expected sum itself from the candidates.
        tax_candidates = [amt for amt in all_amounts if amt < subtotal and abs(amt - expected_tax_sum) > 0.01]
        
        validated_taxes = []
        # Find a combination of candidates that adds up to the expected tax sum
        for i in range(1, len(tax_candidates) + 1):
            for combo in combinations(tax_candidates, i):
                if abs(sum(combo) - expected_tax_sum) < 0.02: # 2 cent tolerance
                    validated_taxes = sorted(list(combo))
                    break
            if validated_taxes:
                break
        
        # --- Stage 3: Assign validated taxes ---
        if validated_taxes:
            if len(validated_taxes) == 1:
                # If only one tax is found, it could be HST or a lone GST/PST
                if any(keyword in text.lower() for keyword in ["hst", "tvh"]):
                     parsed_data["hst_amount"] = validated_taxes[0]
                else:
                     parsed_data["gst_amount"] = validated_taxes[0]
            elif len(validated_taxes) >= 2:
                # If two taxes are found, assume the smaller is GST and the larger is PST.
                parsed_data["gst_amount"] = validated_taxes[0]
                parsed_data["pst_amount"] = validated_taxes[1]

    return parsed_data
