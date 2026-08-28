"""
PatientTriage.ai - ESI Decision-Tree Engine
Follows the real ESI algorithm structure:

  Step 1: Immediate life-threat?              -> ESI 1
  Step 2: High-risk situation?                -> ESI 2
  Step 3: Predict resource need (0/1/2+)      -> ESI 5 / ESI 4 / continue
  Step 4: Vitals danger zone (2+ resources)?  -> ESI 2 (escalate) / ESI 3

Confidence is calculated SEPARATELY from the ESI decision, then used to
apply escalation bias (never downgrade) when the system is uncertain.
This directly implements the PS requirement: "bias toward escalation
under uncertainty rather than optimized for average accuracy."
"""

from models import (
    RED_FLAG_KEYWORDS, AMBIGUITY_HEDGE_WORDS, HIGH_RESOURCE_COMPLAINTS,
    LOW_RESOURCE_COMPLAINTS, AGE_BAND_DANGER_ZONES, get_age_band,
    HIGH_RISK_CHRONIC_CONDITIONS, PREGNANCY_HIGH_RISK_COMPLAINTS,
    PREGNANCY_RED_FLAG_KEYWORDS, RAPID_ONSET_THRESHOLD_HOURS
)


def scan_symptom_text(text: str):
    text_lower = text.lower()
    matched = [kw for kw in RED_FLAG_KEYWORDS if kw in text_lower]
    hedges = sum(1 for h in AMBIGUITY_HEDGE_WORDS if h in text_lower)
    return matched, hedges


def step1_life_threat(patient):
    if patient["consciousness_level"] == "unresponsive":
        return True, "Unresponsive"
    if patient["spo2"] < 85:
        return True, f"SpO2 {patient['spo2']}% - severe hypoxia"
    if patient["heart_rate"] < 40 or patient["heart_rate"] > 180:
        return True, f"Heart rate {patient['heart_rate']} - extreme abnormal"
    return False, None


def step2_high_risk(patient, keyword_matches):
    if patient["consciousness_level"] in ("verbal", "pain"):
        return True, f"Altered mental status ('{patient['consciousness_level']}')"
    if patient["pain_score"] >= 8:
        return True, f"Severe pain/distress ({patient['pain_score']}/10)"
    if keyword_matches:
        return True, f"Red-flag symptom keyword(s): {keyword_matches}"

    # Pregnancy-specific risk: certain complaints or red-flag phrases carry
    # materially higher risk in pregnancy (ectopic pregnancy, preeclampsia, etc.)
    if patient.get("pregnancy_status") == "pregnant":
        text_lower = patient["symptom_description"].lower()
        preg_flags = [kw for kw in PREGNANCY_RED_FLAG_KEYWORDS if kw in text_lower]
        if preg_flags:
            return True, f"Pregnancy + red-flag symptom(s): {preg_flags}"
        if patient["chief_complaint"] in PREGNANCY_HIGH_RISK_COMPLAINTS:
            return True, f"Pregnancy + high-risk complaint ('{patient['chief_complaint']}')"

    # Rapid onset of a high-resource-category complaint is itself a high-risk signal -
    # sudden chest pain 30 minutes ago is more concerning than the same pain building for 2 days
    onset = patient.get("symptom_onset_hours")
    if (onset is not None and onset <= RAPID_ONSET_THRESHOLD_HOURS
            and patient["chief_complaint"] in HIGH_RESOURCE_COMPLAINTS):
        return True, f"Rapid onset ({onset}hr) of '{patient['chief_complaint']}'"

    return False, None


def step3_predict_resources(chief_complaint, keyword_matches, chronic_illness_conditions,
                             weight_kg=None, age_band=None):
    """AI estimate of resources needed (labs, imaging, IV, ECG, consult),
    based on chief complaint + free-text signal + chronic illness burden.
    This is the 'unstructured data' half of the hybrid ESI calculation."""
    if chief_complaint in HIGH_RESOURCE_COMPLAINTS:
        base = 2
    elif chief_complaint in LOW_RESOURCE_COMPLAINTS:
        base = 0
    else:
        base = 1

    if chronic_illness_conditions:
        base += 1
    # High-risk chronic conditions (immunosuppressed, COPD, CKD, cancer) need
    # extra workup even for otherwise routine-looking complaints
    if any(c in HIGH_RISK_CHRONIC_CONDITIONS for c in (chronic_illness_conditions or [])):
        base += 1
    if keyword_matches:
        base += 1

    # Extreme-for-age pediatric weight (dehydration/malnutrition risk) bumps resource need
    if age_band == "pediatric" and weight_kg is not None:
        if (age_band == "pediatric" and weight_kg < 8.0):
            base += 1

    return min(base, 2)  # represented as "2+" once capped


def step4_vitals_danger_zone(patient, age_band):
    zone = AGE_BAND_DANGER_ZONES[age_band]
    reasons = []
    if patient["heart_rate"] > zone["hr"]:
        reasons.append(f"HR {patient['heart_rate']} above {age_band} threshold ({zone['hr']})")
    if patient["respiratory_rate"] > zone["rr"]:
        reasons.append(f"RR {patient['respiratory_rate']} above {age_band} threshold ({zone['rr']})")
    if patient["spo2"] < zone["spo2"]:
        reasons.append(f"SpO2 {patient['spo2']}% below {age_band} threshold ({zone['spo2']}%)")
    return (len(reasons) > 0), reasons


def calculate_confidence(patient, keyword_matches, hedges_found, vital_score_present):
    """Confidence starts at 100 and is reduced by specific, explainable
    factors. Floors at 20 - the system never claims near-zero confidence;
    instead it should be read as 'flag for manual review'."""
    confidence = 100
    reasons = []

    if not patient.get("has_prior_record", False):
        confidence -= 15
        reasons.append("No prior health record (zero-history patient)")

    if hedges_found > 0:
        confidence -= 10 * hedges_found
        reasons.append(f"{hedges_found} ambiguous/hedging phrase(s) in symptom text")

    if not vital_score_present and keyword_matches:
        confidence -= 25
        reasons.append("Vitals appear mild but red-flag keyword(s) found in text - contradictory signal")

    if patient["pain_score"] >= 8 and not vital_score_present and not keyword_matches:
        confidence -= 15
        reasons.append("High self-reported urgency but no objective/textual correlate - recommend manual review")

    if not vital_score_present and not keyword_matches:
        confidence -= 10
        reasons.append("Thin evidence overall")

    confidence = max(confidence, 20)
    return confidence, reasons


def triage_patient(patient: dict) -> dict:
    """Runs the full ESI decision tree + confidence + escalation bias on a
    single patient record. Returns a result dict that is fully explainable
    (every field traceable to a specific rule)."""
    age_band = get_age_band(patient["age"])
    keyword_matches, hedges_found = scan_symptom_text(patient["symptom_description"])

    is_life_threat, reason1 = step1_life_threat(patient)
    if is_life_threat:
        raw_esi = 1
        trace = [f"Step 1: LIFE-THREAT - {reason1}"]
    else:
        is_high_risk, reason2 = step2_high_risk(patient, keyword_matches)
        if is_high_risk:
            raw_esi = 2
            trace = ["Step 1: No immediate life-threat", f"Step 2: HIGH-RISK - {reason2}"]
        else:
            resource_count = step3_predict_resources(
                patient["chief_complaint"], keyword_matches,
                patient.get("chronic_illness_conditions", []),
                weight_kg=patient.get("weight_kg"), age_band=age_band
            )
            trace = ["Step 1: No immediate life-threat", "Step 2: Not high-risk",
                     f"Step 3: Predicted resources = {resource_count}"]

            if resource_count == 0:
                raw_esi = 5
            elif resource_count == 1:
                raw_esi = 4
            else:
                in_danger_zone, danger_reasons = step4_vitals_danger_zone(patient, age_band)
                if in_danger_zone:
                    raw_esi = 2
                    trace.append(f"Step 4: VITALS DANGER ZONE - escalated. {danger_reasons}")
                else:
                    raw_esi = 3
                    trace.append("Step 4: Vitals stable, within age-adjusted safe range")

    vital_score_present = is_life_threat or (
        patient["consciousness_level"] in ("verbal", "pain") or patient["pain_score"] >= 8
    )

    confidence, confidence_reasons = calculate_confidence(
        patient, keyword_matches, hedges_found, vital_score_present
    )

    final_esi = raw_esi
    escalated = False
    escalation_reason = None
    if confidence < 60 and final_esi > 1:
        final_esi -= 1
        escalated = True
        escalation_reason = f"Escalated due to low confidence ({confidence}%)"

    return {
        "patient_id": patient["patient_id"],
        "age": patient["age"],
        "age_band": age_band,
        "raw_esi_level": raw_esi,
        "final_esi_level": final_esi,
        "confidence_pct": confidence,
        "escalated": escalated,
        "escalation_reason": escalation_reason,
        "decision_trace": trace,
        "keyword_matches": keyword_matches,
        "confidence_reasons": confidence_reasons,
        "explanation_summary": (
            f"ESI {final_esi} (confidence={confidence}%). "
            + (escalation_reason if escalated else "No escalation needed.")
        ),
    }


if __name__ == "__main__":
    import json
    with open("patients.json") as f:
        patients = json.load(f)

    print(f"{'ID':<7}{'Age':<5}{'Band':<10}{'RawESI':<8}{'FinalESI':<9}{'Conf%':<7}Escalated")
    for p in patients:
        r = triage_patient(p)
        print(f"{r['patient_id']:<7}{r['age']:<5}{r['age_band']:<10}"
              f"{r['raw_esi_level']:<8}{r['final_esi_level']:<9}{r['confidence_pct']:<7}{r['escalated']}")
