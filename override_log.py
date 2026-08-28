"""
PatientTriage.ai - Clinician Override & Audit Trail
(Round 1 proposal component 5: "AI acts as decision-support, not replacing
human judgment - clinical judgment always takes precedence")

Every override is logged with who, when, original vs new value, and reason -
matching what DPDP Act 2023 / DPDP Rules 2025 require a clinician override
to legally record.
"""

import json
from datetime import datetime

AUDIT_LOG_FILE = "audit_log.json"


def log_override(patient_id, ai_esi_level, ai_confidence, new_esi_level,
                  overridden_by, reason, log_file=AUDIT_LOG_FILE):
    entry = {
        "event": "clinician_override",
        "timestamp": datetime.now().isoformat(),
        "patient_id": patient_id,
        "ai_recommended_esi": ai_esi_level,
        "ai_confidence_pct": ai_confidence,
        "clinician_final_esi": new_esi_level,
        "overridden_by": overridden_by,
        "reason": reason,
        "direction": ("upgrade" if new_esi_level < ai_esi_level else
                      "downgrade" if new_esi_level > ai_esi_level else "no_change"),
    }

    try:
        with open(log_file, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []

    log.append(entry)
    with open(log_file, "w") as f:
        json.dump(log, f, indent=2)

    return entry


def log_ai_downtime_fallback(reason, staff_member, log_file=AUDIT_LOG_FILE):
    """Round 1 proposal component 5: staff must be able to fall back to
    manual triage if the AI system is unavailable. This logs that event."""
    entry = {
        "event": "ai_unavailable_manual_fallback",
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
        "handled_by": staff_member,
    }
    try:
        with open(log_file, "r") as f:
            log = json.load(f)
    except FileNotFoundError:
        log = []
    log.append(entry)
    with open(log_file, "w") as f:
        json.dump(log, f, indent=2)
    return entry


if __name__ == "__main__":
    from triage_engine import triage_patient
    with open("patients.json") as f:
        patients = json.load(f)

    target = patients[3]
    r = triage_patient(target)
    print(f"Patient {r['patient_id']}: AI recommends ESI {r['final_esi_level']} "
          f"(confidence {r['confidence_pct']}%)")

    entry = log_override(
        patient_id=r["patient_id"],
        ai_esi_level=r["final_esi_level"],
        ai_confidence=r["confidence_pct"],
        new_esi_level=max(1, r["final_esi_level"] - 1),
        overridden_by="Nurse_ID_204",
        reason="Patient's condition visibly worsened on visual inspection; "
               "AI's text-based signal did not capture this.",
    )
    print("Override logged:", json.dumps(entry, indent=2))
