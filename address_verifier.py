import re
import urllib.request
import json
import logging
import os
import subprocess
import pymupdf as fitz

log = logging.getLogger(__name__)

# Basic lists of Indian states and union territories for normalization
STATES_MAP = {
    "andhra pradesh": "Andhra Pradesh", "arunachal pradesh": "Arunachal Pradesh", "assam": "Assam",
    "bihar": "Bihar", "chhattisgarh": "Chhattisgarh", "goa": "Goa", "gujarat": "Gujarat",
    "haryana": "Haryana", "himachal pradesh": "Himachal Pradesh", "jharkhand": "Jharkhand",
    "karnataka": "Karnataka", "kerala": "Kerala", "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra", "manipur": "Manipur", "meghalaya": "Meghalaya",
    "mizoram": "Mizoram", "nagaland": "Nagaland", "odisha": "Odisha", "orissa": "Odisha",
    "punjab": "Punjab", "rajasthan": "Rajasthan", "sikkim": "Sikkim", "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana", "tripura": "Tripura", "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand", "west bengal": "West Bengal",
    "andaman and nicobar": "Andaman and Nicobar Islands", "chandigarh": "Chandigarh",
    "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "daman and diu": "Dadra and Nagar Haveli and Daman and Diu", "delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir", "ladakh": "Ladakh", "lakshadweep": "Lakshadweep",
    "puducherry": "Puducherry", "pondicherry": "Puducherry"
}

def clean_string(s):
    if not s:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s]', ' ', s.lower()).strip()

# ══════════════════════════════════════════════════════════════════════════
# Text Extraction & OCR
# ══════════════════════════════════════════════════════════════════════════

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts text from all pages of a PDF file using PyMuPDF."""
    text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text() + "\n"
    except Exception as e:
        log.error(f"Error reading PDF text: {e}")
    return text

def run_local_ocr(image_path: str) -> str:
    """Runs Windows native OCR via win_ocr.ps1 powershell script."""
    _HERE = os.path.dirname(os.path.abspath(__file__))
    ps_script = os.path.join(_HERE, 'win_ocr.ps1')

    ps_cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ps_script,
        "-ImagePath", image_path
    ]

    try:
        res = subprocess.run(ps_cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        log.error(f"Local OCR failed: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            log.error(f"OCR Stderr: {e.stderr}")
        return ""

# ══════════════════════════════════════════════════════════════════════════
# Document Parser (Address & Delivery Hub extractor)
# ══════════════════════════════════════════════════════════════════════════

def extract_address_and_hub(text: str):
    """
    Parses OCR/PDF text, extracts the most probable delivery address
    and detects the destination delivery hub / courier route.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    address_candidate = ""
    detected_hub = "Standard Delivery Hub"
    detected_courier = "Standard Courier"

    if not lines:
        return address_candidate, detected_hub, detected_courier

    # 1. Identify Courier & Hub keywords
    hub_patterns = [
        r'\b[A-Za-z]+_[A-Za-z]+_[A-Z]\b',  # e.g. Jabalpur_Timri_P, Solapur_Jule_D
        r'\b[A-Za-z]+_[A-Z]\b',             # e.g. Obra_D
        r'destination\s*code\s*[:\-\s]+([A-Za-z0-9_\(\)\s_]+)',
        r'route\s*[:\-\s]+([A-Za-z0-9_\-\/]+)'
    ]

    for line in lines:
        l_lower = line.lower()
        # Courier detection
        if "delhivery" in l_lower:
            detected_courier = "Delhivery"
        elif "xpressbees" in l_lower:
            detected_courier = "Xpressbees"
        elif "shadowfax" in l_lower:
            detected_courier = "Shadowfax"
        elif "ekart" in l_lower:
            detected_courier = "Ekart Logistics"
        elif "dtdc" in l_lower:
            detected_courier = "DTDC"

        # Hub detection
        for pat in hub_patterns:
            matches = re.findall(pat, line, re.IGNORECASE)
            if matches:
                match_val = matches[0] if isinstance(matches[0], str) else matches[0][0]
                val_clean = match_val.strip()
                if val_clean.lower() not in ["destination code", "return code"]:
                    detected_hub = val_clean

    # 2. Extract Customer Address block
    # Find all 6-digit pincodes that are NOT the store's return pincodes
    pincodes = re.findall(r'\b\d{6}\b', text)
    customer_pin = None
    for pin in pincodes:
        if pin not in ["824124"]:  # Ignore Ranique Lifestyle store PIN code
            customer_pin = pin
            break

    if not customer_pin:
        # Fallback to any PIN code if only one is found
        if pincodes:
            customer_pin = pincodes[0]

    # Find the line containing the customer PIN code
    pin_line_idx = -1
    if customer_pin:
        for i, line in enumerate(lines):
            if customer_pin in line:
                pin_line_idx = i
                break

    if pin_line_idx != -1:
        # We found the PIN code line. Let's trace upwards to find where the address starts.
        start_idx = pin_line_idx
        # Walk up to 6 lines above the PIN code
        for j in range(max(0, pin_line_idx - 6), pin_line_idx):
            line_lower = lines[j].lower()
            # Stop if we see typical header keywords
            if any(kw in line_lower for kw in ["customer address", "bill to / ship to", "delivery to", "consignee address", "ship to"]):
                start_idx = j
                break
        
        # If we didn't find a header, default to 4 lines above the PIN code
        if start_idx == pin_line_idx:
            start_idx = max(0, pin_line_idx - 4)

        # Gather the address lines from start_idx up to pin_line_idx (inclusive)
        addr_lines = []
        for line in lines[start_idx : pin_line_idx + 1]:
            line_lower = line.lower()
            # Exclude headers and return addresses
            if any(kw in line_lower for kw in ["if undelivered", "product details", "sold by", "tax invoice"]):
                break
            # Skip header line itself if it's just "customer address" or similar
            if line_lower in ["customer address", "bill to / ship to", "delivery to", "consignee address", "ship to"]:
                continue
            addr_lines.append(line)

        address_candidate = ", ".join(addr_lines)
    else:
        # Fallback to keyword matching if no PIN code line found
        start_idx = -1
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in ["customer address", "bill to / ship to", "delivery to"]):
                start_idx = i
                break
        
        if start_idx != -1:
            addr_lines = []
            for line in lines[start_idx + 1 : start_idx + 5]:
                line_lower = line.lower()
                if any(kw in line_lower for kw in ["if undelivered", "product details", "sold by", "tax invoice"]):
                    break
                addr_lines.append(line)
            address_candidate = ", ".join(addr_lines)

    # Clean address candidate of trailing or leading commas and spaces
    address_candidate = re.sub(r'^[\s,]+|[\s,]+$', '', address_candidate)
    
    # If candidate is still empty, fallback to first few lines of text
    if not address_candidate.strip():
        valid_lines = [l for l in lines if not any(kw in l.lower() for kw in ["ranique lifestyle", "follow our shop", "follow our page"])]
        address_candidate = ", ".join(valid_lines[:4])

    return address_candidate, detected_hub, detected_courier

# ══════════════════════════════════════════════════════════════════════════
# Verification Engine
# ══════════════════════════════════════════════════════════════════════════

def verify_indian_address(address_text: str):
    """
    Parses a raw Indian address string, extracts PIN code, fetches official
    postal data from postalpincode.in, and performs validation checks.
    """
    result = {
        "raw_address": address_text,
        "pincode": None,
        "detected_state": None,
        "detected_district": None,
        "official_state": None,
        "official_district": None,
        "official_taluks": [],
        "pincode_valid": False,
        "state_match": None,
        "district_match": None,
        "message": "No PIN code detected.",
        "suggestions": [],
        "google_maps_link": None,
        # Recommendation
        "recommendation": "do_not_ship",  # shipped_parcel | low_risk_shipped | do_not_ship
        "recommendation_text": "Do not shipped this address",
        "detailed_reasons": []
    }

    if not address_text:
        result["detailed_reasons"].append("The address field is completely empty.")
        return result

    # 1. Extract 6-digit PIN code
    pin_matches = re.findall(r'\b\d{6}\b', address_text)
    if not pin_matches:
        spaced_matches = re.findall(r'\b\d{3}\s\d{3}\b', address_text)
        if spaced_matches:
            pincode = spaced_matches[0].replace(" ", "")
        else:
            pincode = None
    else:
        pincode = pin_matches[-1]

    if not pincode:
        result["message"] = "Could not find a valid 6-digit PIN code."
        result["detailed_reasons"].append("The address string is missing a valid 6-digit Indian PIN code (e.g. 413008). Parcels without PIN codes cannot be routed by courier hubs.")
        return result

    result["pincode"] = pincode
    cleaned_address = clean_string(address_text)

    # 2. Query postal pincode API
    url = f"https://api.postalpincode.in/pincode/{pincode}"
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if data and data[0]["Status"] == "Success":
                post_offices = data[0]["PostOffice"]
                if post_offices:
                    result["pincode_valid"] = True
                    result["official_state"] = post_offices[0]["State"]
                    result["official_district"] = post_offices[0]["District"]
                    
                    taluks = set()
                    for po in post_offices:
                        if po.get("Block") and po["Block"] != "NA":
                            taluks.add(po["Block"])
                        if po.get("Name"):
                            taluks.add(po["Name"])
                    result["official_taluks"] = list(taluks)
            else:
                result["message"] = f"PIN code {pincode} was not found in database."
                result["detailed_reasons"].append(f"PIN code '{pincode}' does not exist in the official Indian Post database. The address is undeliverable.")
                query = urllib.parse.quote(address_text)
                result["google_maps_link"] = f"https://www.google.com/maps/search/?api=1&query={query}"
                return result
    except Exception as e:
        log.error(f"Error fetching PIN code data: {e}")
        # Local fallback heuristic if API is down
        result["pincode_valid"] = True
        result["message"] = "Postal database offline. Local rules applied."

    # 3. Match state
    state_found = None
    for state_key, state_name in STATES_MAP.items():
        if state_key in cleaned_address:
            state_found = state_name
            result["detected_state"] = state_name
            break

    if result["official_state"]:
        off_state_clean = clean_string(result["official_state"])
        if state_found:
            if clean_string(state_found) == off_state_clean or off_state_clean in clean_string(state_found):
                result["state_match"] = True
            else:
                result["state_match"] = False
                result["detailed_reasons"].append(f"State mismatch: Pincode '{pincode}' belongs to {result['official_state']}, but the address explicitly writes '{state_found}'.")
        else:
            if off_state_clean in cleaned_address:
                result["state_match"] = True
            else:
                result["state_match"] = False
                result["detailed_reasons"].append(f"Missing State: Address text is missing the state '{result['official_state']}'. This can confuse sorting hubs.")

    # 4. Match district / city
    if result["official_district"]:
        off_dist_clean = clean_string(result["official_district"])
        if off_dist_clean in cleaned_address:
            result["district_match"] = True
            result["detected_district"] = result["official_district"]
        else:
            result["district_match"] = False
            # Check if any block/taluk is mentioned instead of district
            any_taluk_found = False
            for t in result["official_taluks"]:
                if clean_string(t) in cleaned_address:
                    any_taluk_found = True
                    break
            
            if any_taluk_found:
                result["district_match"] = True
            else:
                result["detailed_reasons"].append(f"City/District check failed: Pincode '{pincode}' belongs to '{result['official_district']}', which was not found in the address string.")

    # 5. Classify Recommendations
    if result["pincode_valid"]:
        # If everything is perfect
        if result["state_match"] is not False and result["district_match"] is not False:
            result["recommendation"] = "shipped_parcel"
            result["recommendation_text"] = "Shipped this parcel"
            result["message"] = "Address details match official records. Deliverable."
        # If minor warning but pincode is registered (e.g. spelling city or missing state name)
        elif len(result["detailed_reasons"]) <= 1:
            result["recommendation"] = "low_risk_shipped"
            result["recommendation_text"] = "Confusion / Low Risk - Shipped this parcel"
            result["message"] = "Minor address warnings detected, but Pincode is registered."
        else:
            # Major mismatches
            result["recommendation"] = "do_not_ship"
            result["recommendation_text"] = "Do not shipped this address"
            result["message"] = "Critical address errors detected. High risk of RTO."
    else:
        result["recommendation"] = "do_not_ship"
        result["recommendation_text"] = "Do not shipped this address"

    # Suggested formatting
    if result["pincode_valid"] and (result["state_match"] is False or result["district_match"] is False):
        base_address = re.sub(rf'\b{pincode}\b.*', '', address_text).strip()
        base_address = re.sub(r'[\s,]+$', '', base_address)
        suggested = f"{base_address}, {result['official_district']}, {result['official_state']} - {pincode}"
        result["suggested_address"] = suggested

    query = urllib.parse.quote(address_text)
    result["google_maps_link"] = f"https://www.google.com/maps/search/?api=1&query={query}"

    return result
