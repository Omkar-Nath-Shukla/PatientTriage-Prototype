"""
PatientTriage.ai - Synthetic Patient Data Generator
Generates realistic simulated ED patient records covering the FULL input
schema defined in models.py, including mandatory edge cases:
  - Ambiguous presentation
  - Pediatric / Geriatric case
  - Zero-history (first-time) patient
"""

import random
import json
from datetime import datetime, timedelta

random.seed(42)

CHIEF_COMPLAINTS = [
    "chest pain", "breathing difficulty", "fever", "abdominal pain",
    "injury/trauma", "headache", "dizziness", "allergic reaction",
    "vomiting", "back pain", "minor cut", "prescription refill"
]

CHRONIC_ILLNESS_POOL = ["diabetes", "hypertension", "asthma", "heart disease",
                        "COPD", "chronic kidney disease", "cancer_under_treatment",
                        "immunosuppressed"]

ARRIVAL_MODES = ["walk-in", "ambulance", "referred"]


def generate_weight_kg(age):
    """Rough realistic weight ranges by age - not clinically precise, just
    enough for demo purposes and to allow extreme-weight edge cases."""
    if age < 1:
        return round(random.uniform(3.0, 10.0), 1)
    elif age < 12:
        return round(random.uniform(10.0, 45.0), 1)
    elif age < 65:
        return round(random.uniform(45.0, 100.0), 1)
    else:
        return round(random.uniform(45.0, 90.0), 1)


def generate_symptom_onset_hours(severity_hint="normal"):
    """Critical cases are more likely to have sudden/rapid onset; mild cases
    more likely to have been building for a while."""
    if severity_hint == "critical":
        return round(random.uniform(0.2, 3.0), 1)
    elif severity_hint == "moderate":
        return round(random.uniform(1.0, 12.0), 1)
    else:
        return round(random.uniform(4.0, 72.0), 1)


def generate_pregnancy_status(age, gender):
    if gender != "F" or not (14 <= age <= 50):
        return "not_applicable"
    return "pregnant" if random.random() < 0.08 else "not_pregnant"


def random_timestamp(base_time, minute_offset_range=(0, 240)):
    offset = random.randint(*minute_offset_range)
    return (base_time + timedelta(minutes=offset)).isoformat()


def generate_vitals(severity_hint="normal"):
    """Vitals loosely correlated with an intended severity hint, used only
    to build a realistic-looking dataset - the triage engine re-derives
    severity independently from these values, it does not trust the hint."""
    if severity_hint == "critical":
        hr = random.randint(120, 190)
        rr = random.randint(28, 40)
        spo2 = random.randint(78, 90)
        temp = round(random.uniform(38.5, 40.5), 1)
        bp_sys = random.randint(70, 90)
        pain = random.randint(7, 10)
        consciousness = random.choice(["verbal", "pain", "unresponsive"])
    elif severity_hint == "moderate":
        hr = random.randint(100, 120)
        rr = random.randint(20, 28)
        spo2 = random.randint(91, 95)
        temp = round(random.uniform(37.8, 39.0), 1)
        bp_sys = random.randint(95, 115)
        pain = random.randint(4, 7)
        consciousness = "alert"
    else:  # normal / mild
        hr = random.randint(60, 98)
        rr = random.randint(12, 19)
        spo2 = random.randint(96, 100)
        temp = round(random.uniform(36.5, 37.4), 1)
        bp_sys = random.randint(110, 130)
        pain = random.randint(0, 3)
        consciousness = "alert"

    bp_dia = bp_sys - random.randint(30, 50)

    return {
        "heart_rate": hr,
        "blood_pressure": f"{bp_sys}/{bp_dia}",
        "temperature": temp,
        "respiratory_rate": rr,
        "spo2": spo2,
        "pain_score": pain,
        "consciousness_level": consciousness,
    }


def generate_patient(patient_id, base_time, age=None, severity_hint="normal",
                      symptom_text=None, has_prior_record=None, arrival_mode=None,
                      chief_complaint=None, edge_case_tag=None,
                      gender=None, weight_kg=None, symptom_onset_hours=None,
                      pregnancy_status=None, chronic_illness_conditions=None):
    if age is None:
        age = random.randint(18, 65)
    if gender is None:
        gender = random.choice(["M", "F"])
    if has_prior_record is None:
        has_prior_record = random.random() > 0.5  # ~50/50 split per PS
    if arrival_mode is None:
        arrival_mode = random.choices(ARRIVAL_MODES, weights=[0.6, 0.3, 0.1])[0]
    if chief_complaint is None:
        chief_complaint = random.choice(CHIEF_COMPLAINTS)
    if weight_kg is None:
        weight_kg = generate_weight_kg(age)
    if symptom_onset_hours is None:
        symptom_onset_hours = generate_symptom_onset_hours(severity_hint)
    if pregnancy_status is None:
        pregnancy_status = generate_pregnancy_status(age, gender)

    vitals = generate_vitals(severity_hint)

    if chronic_illness_conditions is None:
        chronic_illness_conditions = []
        if has_prior_record:
            num_conditions = random.choices([0, 1, 2], weights=[0.5, 0.35, 0.15])[0]
            chronic_illness_conditions = random.sample(CHRONIC_ILLNESS_POOL, k=num_conditions)

    if symptom_text is None:
        symptom_text = f"Patient reports {chief_complaint}, onset within last few hours."

    arrival_ts = random_timestamp(base_time)
    consent_ts = random_timestamp(base_time, (0, 5))

    return {
        # 1. Identity & demographics
        "patient_id": patient_id,
        "age": age,
        "gender": gender,
        "arrival_mode": arrival_mode,
        "weight_kg": weight_kg,
        # 2. Vitals
        **vitals,
        # 3. Symptoms
        "chief_complaint": chief_complaint,
        "symptom_description": symptom_text,
        "symptom_onset_hours": symptom_onset_hours,
        # 4. History
        "has_prior_record": has_prior_record,
        "chronic_illness_conditions": chronic_illness_conditions,
        "prior_visits_count": random.randint(1, 5) if has_prior_record else 0,
        "pregnancy_status": pregnancy_status,
        # 5. Consent
        "consent_given": True,
        "consent_timestamp": consent_ts,
        # 6. Time tracking
        "arrival_timestamp": arrival_ts,
        "last_reassessment_timestamp": None,
        # internal tracking (not part of clinical schema, used for our own testing)
        "_edge_case_tag": edge_case_tag,
    }


def generate_dataset(num_patients=20):
    base_time = datetime(2026, 8, 24, 8, 0, 0)
    patients = []
    pid_counter = 1000

    def next_id():
        nonlocal pid_counter
        pid_counter += 1
        return f"P{pid_counter}"

    # --- Mandatory edge cases (always included, regardless of num_patients) ---
    patients.append(generate_patient(
        next_id(), base_time, age=45, severity_hint="normal",
        chief_complaint="chest pain",
        symptom_text="Patient says pain is mild, 3/10, but mentions it radiates to left "
                      "arm and jaw, and feels 'a bit off'.",
        edge_case_tag="ambiguous_presentation"
    ))

    patients.append(generate_patient(
        next_id(), base_time, age=3, severity_hint="moderate",
        chief_complaint="fever",
        symptom_text="Child crying, high fever since morning, refusing to eat, "
                      "mother reports lethargy.",
        has_prior_record=False,
        edge_case_tag="pediatric"
    ))

    patients.append(generate_patient(
        next_id(), base_time, age=78, severity_hint="moderate",
        chief_complaint="dizziness",
        symptom_text="Elderly patient reports dizziness and mild confusion since "
                      "this morning, lives alone.",
        has_prior_record=True,
        edge_case_tag="geriatric"
    ))

    patients.append(generate_patient(
        next_id(), base_time, age=29, severity_hint="normal",
        chief_complaint="abdominal pain",
        symptom_text="First-time patient, new to city, reports moderate abdominal "
                      "pain since last night.",
        has_prior_record=False,
        edge_case_tag="zero_history"
    ))

    # High self-reported urgency but normal vitals / no red-flag keyword
    # (subjective-urgency-vs-objective-vitals mismatch case)
    patients.append(generate_patient(
        next_id(), base_time, age=34, severity_hint="normal",
        chief_complaint="headache",
        symptom_text="Patient insists this is a medical emergency and demands to "
                      "be seen immediately, but describes a routine tension headache.",
        edge_case_tag="subjective_urgency_mismatch"
    ))

    # Pregnant patient with a pregnancy-specific red-flag symptom
    patients.append(generate_patient(
        next_id(), base_time, age=27, gender="F", severity_hint="normal",
        chief_complaint="abdominal pain",
        symptom_text="Patient reports abdominal pain with some vaginal bleeding, "
                      "28 weeks pregnant.",
        pregnancy_status="pregnant",
        symptom_onset_hours=1.5,
        edge_case_tag="pregnancy_high_risk"
    ))

    # Immunosuppressed patient with rapid-onset fever (sepsis risk pattern)
    patients.append(generate_patient(
        next_id(), base_time, age=58, severity_hint="moderate",
        chief_complaint="fever",
        symptom_text="Patient undergoing cancer treatment, fever started suddenly "
                      "about 45 minutes ago, feels weak.",
        chronic_illness_conditions=["cancer_under_treatment"],
        symptom_onset_hours=0.75,
        has_prior_record=True,
        edge_case_tag="immunosuppressed_rapid_onset"
    ))

    # --- Remaining randomised patients ---
    remaining = max(0, num_patients - len(patients))
    severity_mix = (["critical"] * max(1, remaining // 10) +
                     ["moderate"] * max(1, remaining // 3) +
                     ["normal"] * remaining)
    severity_mix = severity_mix[:remaining]
    random.shuffle(severity_mix)

    for sev in severity_mix:
        age = random.choices(
            [random.randint(1, 11), random.randint(12, 64), random.randint(65, 95)],
            weights=[0.15, 0.65, 0.20]
        )[0]
        patients.append(generate_patient(next_id(), base_time, age=age, severity_hint=sev))

    return patients


if __name__ == "__main__":
    dataset = generate_dataset(20)
    with open("patients.json", "w") as f:
        json.dump(dataset, f, indent=2)
    print(f"Generated {len(dataset)} patient records -> patients.json")
    print(f"Edge cases included: "
          f"{[p['_edge_case_tag'] for p in dataset if p['_edge_case_tag']]}")
