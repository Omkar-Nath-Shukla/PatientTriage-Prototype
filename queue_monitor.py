"""
PatientTriage.ai - Waiting Queue Monitoring & Reassessment
Monitors patients still in the queue and triggers automatic re-assessment
if their wait time exceeds the safe threshold for their ESI level, or if
doctor availability is low enough to push their estimated wait past it.
"""

from models import SAFE_WAIT_THRESHOLD_MIN

# Rough base service time per patient (minutes) used to estimate queue wait
BASE_SERVICE_TIME_MIN = 15


def estimate_wait_time(queue_position: int, doctors_on_duty: int) -> float:
    """Simple estimate: more doctors on duty -> proportionally shorter wait.
    This is where doctors_on_duty (Round 1: 'live data on bed occupancy and
    doctor availability') factors into the system."""
    doctors_on_duty = max(1, doctors_on_duty)  # avoid divide-by-zero
    return round((queue_position * BASE_SERVICE_TIME_MIN) / doctors_on_duty, 1)


def check_reassessment(triage_result: dict, wait_time_min: float) -> dict:
    """Returns whether this patient's wait has exceeded their safe threshold,
    and what action the system takes."""
    esi = triage_result["final_esi_level"]
    threshold = SAFE_WAIT_THRESHOLD_MIN[esi]
    exceeded = wait_time_min > threshold

    return {
        "patient_id": triage_result["patient_id"],
        "esi_level": esi,
        "safe_wait_threshold_min": threshold,
        "actual_wait_min": wait_time_min,
        "reassessment_triggered": exceeded,
        "action": ("URGENT: escalate for re-assessment now" if exceeded else "within safe window"),
    }


def monitor_queue(triage_results: list, doctors_on_duty: int) -> list:
    """Run reassessment checks across an entire waiting queue, ordered by
    arrival (position in list = queue position)."""
    report = []
    for position, result in enumerate(triage_results, start=1):
        wait = estimate_wait_time(position, doctors_on_duty)
        report.append(check_reassessment(result, wait))
    return report


if __name__ == "__main__":
    import json
    from triage_engine import triage_patient

    with open("patients.json") as f:
        patients = json.load(f)

    results = [triage_patient(p) for p in patients]

    print("=== Queue monitoring at doctors_on_duty = 3 (understaffed) ===")
    for entry in monitor_queue(results, doctors_on_duty=3):
        flag = "  <<< REASSESS" if entry["reassessment_triggered"] else ""
        print(f"{entry['patient_id']} ESI={entry['esi_level']} "
              f"wait={entry['actual_wait_min']}min "
              f"(safe<= {entry['safe_wait_threshold_min']}min){flag}")

    print("\n=== Queue monitoring at doctors_on_duty = 8 (well-staffed) ===")
    for entry in monitor_queue(results, doctors_on_duty=8):
        flag = "  <<< REASSESS" if entry["reassessment_triggered"] else ""
        print(f"{entry['patient_id']} ESI={entry['esi_level']} "
              f"wait={entry['actual_wait_min']}min "
              f"(safe<= {entry['safe_wait_threshold_min']}min){flag}")
