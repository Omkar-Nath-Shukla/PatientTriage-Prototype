"""
PatientTriage.ai - Main Pipeline
Runs the complete prototype end-to-end and prints a demo-ready summary:

  1. Generate synthetic patients (with mandatory edge cases)
  2. Run ESI triage on each (hybrid decision-tree + confidence)
  3. Assign beds using the 90/10 buffer rule
  4. Simulate a 3x surge and compare against a no-buffer baseline
  5. Monitor the waiting queue and trigger re-assessments
  6. Log one clinician override with a full audit trail
"""

import json
from generate_patients import generate_dataset
from triage_engine import triage_patient
from bed_management import BedManager
from queue_monitor import monitor_queue
from override_log import log_override


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def run_normal_volume_demo(total_beds=22, num_patients=20, doctors_on_duty=6):
    section("1. NORMAL VOLUME - Triage + 90/10 Bed Allocation")

    patients = generate_dataset(num_patients)
    with open("patients.json", "w") as f:
        json.dump(patients, f, indent=2)

    bm = BedManager(total_beds=total_beds, reserved_pct=0.10)
    results = []

    print(f"{'ID':<7}{'Age':<5}{'Band':<10}{'ESI':<5}{'Conf%':<7}"
          f"{'Escalated':<11}{'Bed pool'}")
    for p in patients:
        r = triage_patient(p)
        outcome = bm.assign_bed(r["patient_id"], r["final_esi_level"])
        r["bed_outcome"] = outcome
        results.append(r)
        print(f"{r['patient_id']:<7}{r['age']:<5}{r['age_band']:<10}"
              f"{r['final_esi_level']:<5}{r['confidence_pct']:<7}"
              f"{str(r['escalated']):<11}{outcome['assigned_pool'] or 'WAITLISTED'}")

    print("\nBed status:", json.dumps(bm.status(), indent=2))

    # Highlight the ambiguous case explicitly
    for r in results:
        if r.get("escalated"):
            print(f"\n>>> Escalation example: {r['patient_id']} - {r['explanation_summary']}")
            for step in r["decision_trace"]:
                print("   ", step)
            break

    return results, bm


def run_surge_demo(multiplier=3, base_patient_count=20, total_beds=22):
    section(f"2. SURGE TEST - {multiplier}x normal volume")

    surge_count = base_patient_count * multiplier
    patients = generate_dataset(surge_count)

    bm = BedManager(total_beds=total_beds, reserved_pct=0.10)
    results = []
    for p in patients:
        r = triage_patient(p)
        outcome = bm.assign_bed(r["patient_id"], r["final_esi_level"])
        r["bed_outcome"] = outcome
        results.append(r)

    waitlisted_total = sum(1 for r in results if r["bed_outcome"]["waitlisted"])
    waitlisted_critical = sum(
        1 for r in results if r["bed_outcome"]["waitlisted"] and r["final_esi_level"] <= 2
    )
    reserved_used = [r for r in results if r["bed_outcome"]["assigned_pool"] == "reserved_critical"]

    print(f"{surge_count} patients arrived against {total_beds} beds "
          f"({bm.dynamic_beds} dynamic + {bm.reserved_beds} reserved)")
    print(f"Total waitlisted: {waitlisted_total} | Critical (ESI 1-2) waitlisted: {waitlisted_critical}")
    print(f"Patients rescued by the reserved pool: {len(reserved_used)}")
    for r in reserved_used:
        print(f"  - {r['patient_id']} (ESI {r['final_esi_level']}, age {r['age']}, {r['age_band']})")

    # Comparison baseline: no buffer at all
    bm_baseline = BedManager(total_beds=total_beds, reserved_pct=0.0)
    baseline_critical_waitlisted = 0
    for r in results:
        outcome = bm_baseline.assign_bed(r["patient_id"], r["final_esi_level"])
        if outcome["waitlisted"] and r["final_esi_level"] <= 2:
            baseline_critical_waitlisted += 1

    print(f"\nWithout 90/10 buffer, critical patients waitlisted would be: {baseline_critical_waitlisted}")
    print(f"With 90/10 buffer, critical patients waitlisted: {waitlisted_critical}")
    print(f"=> Buffer rule saved {baseline_critical_waitlisted - waitlisted_critical} "
          f"critical patients from queuing behind non-critical ones.")

    return results, bm


def run_queue_monitoring_demo(results, doctors_on_duty=4):
    section(f"3. WAITING QUEUE MONITORING (doctors_on_duty={doctors_on_duty})")
    waitlisted_results = [r for r in results if r["bed_outcome"]["waitlisted"]]
    report = monitor_queue(waitlisted_results, doctors_on_duty=doctors_on_duty)

    flagged = [e for e in report if e["reassessment_triggered"]]
    print(f"{len(flagged)} of {len(report)} waitlisted patients exceeded their safe wait threshold:\n")
    for entry in flagged:
        print(f"  REASSESS: {entry['patient_id']} (ESI {entry['esi_level']}, "
              f"wait={entry['actual_wait_min']}min, safe<= {entry['safe_wait_threshold_min']}min)")
    return report


def run_override_demo(results):
    section("4. CLINICIAN OVERRIDE + AUDIT TRAIL")
    target = results[0]
    entry = log_override(
        patient_id=target["patient_id"],
        ai_esi_level=target["final_esi_level"],
        ai_confidence=target["confidence_pct"],
        new_esi_level=max(1, target["final_esi_level"] - 1),
        overridden_by="Nurse_ID_204",
        reason="Patient's condition visibly worsened on visual inspection; "
               "AI's text-based signal did not capture this.",
    )
    print(json.dumps(entry, indent=2))
    print("\nFull audit log saved to audit_log.json")


if __name__ == "__main__":
    normal_results, _ = run_normal_volume_demo(total_beds=22, num_patients=20, doctors_on_duty=6)
    surge_results, _ = run_surge_demo(multiplier=3, base_patient_count=20, total_beds=22)
    run_queue_monitoring_demo(surge_results, doctors_on_duty=4)
    run_override_demo(normal_results)

    section("DONE - prototype pipeline ran successfully end-to-end")
