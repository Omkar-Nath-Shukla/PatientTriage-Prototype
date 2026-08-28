"""
PatientTriage.ai - Data Schema Reference
==========================================
This file documents every data field used in the system. It is the single
source of truth for the input/output schema described in the proposal deck.

--------------------------------------------------------------------------
1. PATIENT IDENTITY & DEMOGRAPHICS
--------------------------------------------------------------------------
patient_id          str    Unique patient identifier, e.g. "P1023"
age                 int    Age in years
gender              str    "M" / "F"
arrival_mode        str    "walk-in" / "ambulance" / "referred"

--------------------------------------------------------------------------
2. VITALS (structured)
--------------------------------------------------------------------------
heart_rate          int    Beats per minute
blood_pressure       str    "systolic/diastolic", e.g. "120/80"
respiratory_rate     int    Breaths per minute
spo2                int    Oxygen saturation, percent
temperature          float  Degrees Celsius
pain_score           int    Self-reported pain, 0-10
consciousness_level  str    "alert" / "verbal" / "pain" / "unresponsive" (AVPU)

--------------------------------------------------------------------------
3. SYMPTOMS (hybrid: structured + unstructured)
--------------------------------------------------------------------------
chief_complaint       str   Structured category, e.g. "chest pain"
symptom_description   str   Free-text nurse/patient description (unstructured
                             signal scanned for red-flag phrases)

--------------------------------------------------------------------------
4. HISTORY & CONTEXT
--------------------------------------------------------------------------
has_prior_record         bool   Whether hospital has a prior record for this patient
chronic_illness_conditions list  e.g. ["diabetes", "COPD"] - see CHRONIC_ILLNESS_POOL below
prior_visits_count        int   Number of previous ED visits on file
weight_kg                 float Body weight in kilograms
symptom_onset_hours       float Hours since symptom onset (rapid onset = higher risk)
pregnancy_status           str   "pregnant" / "not_pregnant" / "not_applicable"

--------------------------------------------------------------------------
5. CONSENT (DPDP Act 2023 / DPDP Rules 2025 compliance)
--------------------------------------------------------------------------
consent_given          bool       Explicit consent captured at intake
consent_timestamp       str (ISO)  When consent was captured

--------------------------------------------------------------------------
6. TIME / QUEUE TRACKING
--------------------------------------------------------------------------
arrival_timestamp        str (ISO)  When patient arrived
wait_time_elapsed_min     float      Computed at query time
last_reassessment_timestamp str (ISO, nullable)  Last time vitals were re-checked

--------------------------------------------------------------------------
7. HOSPITAL-LEVEL OPERATIONAL DATA (not per-patient; shared state)
--------------------------------------------------------------------------
total_beds                      int   Total ED beds
reserved_critical_pct           float Fraction of beds reserved for ESI 1-2 (default 0.10)
doctors_on_duty                 int   Doctors currently staffed
current_queue_length             int   Patients currently waiting

--------------------------------------------------------------------------
8. SYSTEM-GENERATED OUTPUT (produced by the engine, not supplied as input)
--------------------------------------------------------------------------
predicted_resource_count   int    0 / 1 / 2 (AI estimate of resources needed)
raw_esi_level               int    1-5, before escalation-bias adjustment
final_esi_level              int    1-5, after escalation-bias adjustment
confidence_pct               int    0-100
escalated                    bool
escalation_reason             str/None
decision_trace                list  Step-by-step explanation (explainability)
bed_assigned_pool             str   "dynamic" / "reserved_critical" / None (waitlisted)
estimated_wait_min            float Adjusted for doctors_on_duty
reassessment_triggered        bool  True if wait exceeded the safe threshold
override_flag                 bool
override_reason                str/None
overridden_by                  str/None

--------------------------------------------------------------------------
Safe wait thresholds by ESI level (minutes) - illustrative, would be
clinically calibrated in a real deployment.
--------------------------------------------------------------------------
"""

SAFE_WAIT_THRESHOLD_MIN = {1: 0, 2: 10, 3: 30, 4: 60, 5: 120}

AGE_BAND_DANGER_ZONES = {
    "pediatric": {"hr": 140, "rr": 30, "spo2": 92},
    "adult": {"hr": 100, "rr": 20, "spo2": 92},
    "geriatric": {"hr": 100, "rr": 20, "spo2": 94},
}

RED_FLAG_KEYWORDS = [
    "radiates to left arm", "jaw", "crushing", "can't breathe", "cannot breathe",
    "unresponsive", "confusion", "seizure", "severe bleeding", "blue lips",
    "worst headache", "slurred speech", "one sided weakness", "lethargy"
]

AMBIGUITY_HEDGE_WORDS = ["a bit", "mild but", "feels off", "not sure", "maybe", "kind of"]

HIGH_RESOURCE_COMPLAINTS = ["chest pain", "abdominal pain", "breathing difficulty", "injury/trauma"]
LOW_RESOURCE_COMPLAINTS = ["minor cut", "prescription refill", "mild headache"]

# Chronic illness conditions - split into standard vs high-risk (immunocompromised /
# organ-impaired patients deteriorate faster and need closer attention for the
# same presenting symptoms)
CHRONIC_ILLNESS_POOL = ["diabetes", "hypertension", "asthma", "heart disease",
                        "COPD", "chronic kidney disease", "cancer_under_treatment",
                        "immunosuppressed"]
HIGH_RISK_CHRONIC_CONDITIONS = ["COPD", "chronic kidney disease",
                                 "cancer_under_treatment", "immunosuppressed"]

# Complaints where pregnancy changes the risk profile significantly
# (e.g. abdominal pain in pregnancy could be ectopic pregnancy or placental abruption;
# headache could signal preeclampsia)
PREGNANCY_HIGH_RISK_COMPLAINTS = ["abdominal pain", "headache", "back pain"]
PREGNANCY_RED_FLAG_KEYWORDS = ["vaginal bleeding", "severe swelling", "vision changes",
                               "reduced fetal movement", "contractions"]

# Onset is considered "rapid" (higher risk for the same complaint) below this many hours
RAPID_ONSET_THRESHOLD_HOURS = 1.0

# Pediatric weight bands (kg) - used to flag extreme-for-age weight as a risk signal
PEDIATRIC_WEIGHT_LOW_KG = {  # below this = concerning (dehydration/malnutrition risk)
    "infant": 3.0, "toddler": 8.0, "child": 12.0
}


def get_age_band(age: int) -> str:
    if age < 12:
        return "pediatric"
    elif age >= 65:
        return "geriatric"
    return "adult"
    
