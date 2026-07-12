"""
heuristics.py — Structured extraction helpers for printed medical reports.

Copied from the main project's experiments/ocr_tuning/pipeline/heuristics.py.
Only depends on the Python standard library (re, difflib).
"""
import re
import difflib


def group_ocr_into_lines(ocr_results, y_tolerance_px=15):
    """
    Groups OCR detection dictionaries into lines by their y-coordinates.
    Returns a list of lines, where each line is a list of OCR results sorted from left to right.
    """
    parsed_items = []
    for item in ocr_results:
        text = item.get("text", "")
        bbox = item.get("bounding_box", [])
        if not bbox or len(bbox) < 4:
            continue
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        y_center = (y_min + y_max) / 2.0
        height = y_max - y_min
        parsed_items.append({
            "text": text,
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "y_center": y_center,
            "height": height,
            "raw": item
        })

    if not parsed_items:
        return []

    parsed_items.sort(key=lambda item: item["y_center"])

    lines = []
    for item in parsed_items:
        placed = False
        for line in lines:
            line_y_center = sum(member["y_center"] for member in line) / len(line)
            line_avg_height = sum(member["height"] for member in line) / len(line)
            if abs(item["y_center"] - line_y_center) < max(y_tolerance_px, line_avg_height * 0.5):
                line.append(item)
                placed = True
                break
        if not placed:
            lines.append([item])

    for line in lines:
        line.sort(key=lambda x: x["x_min"])

    lines.sort(key=lambda line: sum(x["y_center"] for x in line) / len(line))

    return [[member["raw"] for member in line] for line in lines]


def find_test_name_match(text, test_mappings, threshold=0.7):
    """
    Given an OCR text, looks up if it maps to any canonical test name.
    """
    text_lower = text.lower().strip()
    text_clean = re.sub(r'[:\-\*]', '', text_lower).strip()

    for canonical, synonyms in test_mappings.items():
        if text_clean == canonical:
            return canonical
        for syn in synonyms:
            if text_clean == syn.lower().strip():
                return canonical

    for canonical, synonyms in test_mappings.items():
        if text_clean in canonical or canonical in text_clean:
            return canonical
        for syn in synonyms:
            syn_clean = syn.lower().strip()
            if syn_clean in text_clean or text_clean in syn_clean:
                return canonical

    all_targets = list(test_mappings.keys())
    for canonical, synonyms in test_mappings.items():
        all_targets.extend(synonyms)

    matches = difflib.get_close_matches(text_clean, all_targets, n=1, cutoff=threshold)
    if matches:
        matched_str = matches[0]
        for canonical, synonyms in test_mappings.items():
            if matched_str == canonical or matched_str in synonyms:
                return canonical

    return None


def parse_range(range_str):
    """
    Parses a reference range string to return (min_val, max_val).
    """
    if not range_str:
        return None, None

    range_str_clean = range_str.replace(',', '').strip()

    lt_match = re.search(r'<\s*([\d\.]+)', range_str_clean)
    if lt_match:
        return 0.0, float(lt_match.group(1))

    gt_match = re.search(r'>\s*([\d\.]+)', range_str_clean)
    if gt_match:
        return float(gt_match.group(1)), float('inf')

    range_match = re.findall(r'[\d\.]+', range_str_clean)
    if len(range_match) >= 2:
        try:
            return float(range_match[0]), float(range_match[1])
        except ValueError:
            pass

    return None, None


def correct_numeric_value(raw_val_str, canonical_test, config, parsed_range=None):
    """
    Applies heuristic corrections to a raw value string using config rules and range context.
    """
    if not raw_val_str:
        return None, None

    val_clean = raw_val_str.strip()

    num_match = re.search(r'[\d\.,]+', val_clean)
    if not num_match:
        return raw_val_str, "no_numeric_part_found"

    num_str = num_match.group(0)

    corr_rules = config.get("correction_rules", {})
    magnitude_rules = corr_rules.get("magnitude_checks", {}).get(canonical_test, {})
    decimal_comma_swap_keys = corr_rules.get("decimal_to_comma_swap_keys", [])

    expected_min = magnitude_rules.get("expected_min")
    expected_max = magnitude_rules.get("expected_max")
    allow_swap = magnitude_rules.get("allow_decimal_comma_swap", False) or (canonical_test in decimal_comma_swap_keys)

    if (expected_min is None or expected_max is None) and parsed_range:
        expected_min = expected_min if expected_min is not None else parsed_range[0]
        expected_max = expected_max if expected_max is not None else parsed_range[1]

    if expected_min is None or expected_max is None:
        try:
            return float(num_str.replace(',', '')), "no_correction_context"
        except ValueError:
            return raw_val_str, "unparsable_float"

    try:
        val_float = float(num_str.replace(',', ''))
        if expected_min <= val_float <= expected_max:
            return val_float, "none"
    except ValueError:
        pass

    if allow_swap and '.' in num_str:
        val_no_dot_str = num_str.replace('.', '')
        try:
            val_no_dot = float(val_no_dot_str)
            if expected_min <= val_no_dot <= expected_max * 1.5:
                return val_no_dot, "decimal_to_comma_swap"
        except ValueError:
            pass

    if ',' in num_str:
        val_dot_str = num_str.replace(',', '.')
        try:
            val_dot = float(val_dot_str)
            if expected_min <= val_dot <= expected_max * 1.5:
                return val_dot, "comma_to_decimal_swap"
        except ValueError:
            pass

    try:
        return float(num_str.replace(',', '')), "none"
    except ValueError:
        return raw_val_str, "error_parsing"


def extract_structured_results(ocr_results, config):
    """
    Groups OCR results into lines, identifies test names, and extracts matching values and reference ranges.
    """
    test_mappings = config.get("test_name_mappings", {})
    fuzzy_threshold = config.get("fuzzy_match_threshold", 0.7)
    lines = group_ocr_into_lines(ocr_results)

    extracted_tests = []

    for line in lines:
        test_match = None
        test_index = -1

        for i, item in enumerate(line):
            text = item.get("text", "")
            match = find_test_name_match(text, test_mappings, threshold=fuzzy_threshold)
            if match:
                test_match = match
                test_index = i
                break

        if not test_match:
            continue

        other_items = line[test_index + 1:]

        val_candidate = None
        range_candidate = None
        unit_candidate = ""

        for item in other_items:
            text = item.get("text", "").strip()
            if re.search(r'(\d+\s*[-~]\s*\d+|to|[\d\.]+\s*-\s*[\d\.]+|[<>]\s*[\d\.]+)', text):
                range_candidate = text
                break

        for item in other_items:
            text = item.get("text", "").strip()
            if text == range_candidate:
                continue
            if re.search(r'\d+', text):
                letters_only = re.sub(r'[\d\.,\s]+', '', text)
                if letters_only and len(letters_only) <= 8:
                    unit_candidate = letters_only
                val_candidate = text
                break

        if not val_candidate and other_items:
            for item in other_items:
                text = item.get("text", "").strip()
                if text != range_candidate and text:
                    val_candidate = text
                    break

        parsed_range = parse_range(range_candidate)
        corrected_val, correction_type = correct_numeric_value(val_candidate, test_match, config, parsed_range)

        extracted_tests.append({
            "test_name": {
                "raw_ocr": line[test_index].get("text"),
                "normalized": test_match
            },
            "value": {
                "raw_ocr": val_candidate,
                "normalized_value": corrected_val,
                "unit": unit_candidate,
                "correction_applied": correction_type
            },
            "reference_range": {
                "raw_ocr": range_candidate,
                "min": parsed_range[0] if parsed_range else None,
                "max": parsed_range[1] if parsed_range else None
            }
        })

    return extracted_tests
