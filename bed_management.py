"""
PatientTriage.ai - Real-Time Resource Integration with 90/10 Buffer Rule
(Round 1 proposal, component 3)

90% of beds are allocated dynamically as patients arrive (any severity).
10% of beds are RESERVED exclusively for critical/severe (ESI 1-2) cases -
even if the 90% dynamic pool is already full.
"""


class BedManager:
    def __init__(self, total_beds=22, reserved_pct=0.10):
        self.total_beds = total_beds
        self.reserved_beds = max(1, round(total_beds * reserved_pct))
        self.dynamic_beds = total_beds - self.reserved_beds

        self.dynamic_occupied = 0
        self.reserved_occupied = 0
        self.assignment_log = []  # audit trail

    def status(self):
        return {
            "total_beds": self.total_beds,
            "dynamic_pool": {
                "capacity": self.dynamic_beds,
                "occupied": self.dynamic_occupied,
                "available": self.dynamic_beds - self.dynamic_occupied,
            },
            "reserved_critical_pool": {
                "capacity": self.reserved_beds,
                "occupied": self.reserved_occupied,
                "available": self.reserved_beds - self.reserved_occupied,
            },
        }

    def assign_bed(self, patient_id, esi_level):
        """
        ESI 1-2 (critical/severe): try dynamic pool first, fall back to reserved pool.
        ESI 3-5: dynamic pool ONLY, never touches the reserved pool.
        """
        is_critical = esi_level <= 2
        outcome = {
            "patient_id": patient_id, "esi_level": esi_level,
            "assigned_pool": None, "waitlisted": False, "reason": None,
        }

        if self.dynamic_occupied < self.dynamic_beds:
            self.dynamic_occupied += 1
            outcome["assigned_pool"] = "dynamic"
        elif is_critical and self.reserved_occupied < self.reserved_beds:
            self.reserved_occupied += 1
            outcome["assigned_pool"] = "reserved_critical"
        else:
            outcome["waitlisted"] = True
            outcome["reason"] = (
                "Both dynamic and reserved pools full - true full-capacity event"
                if is_critical else
                "No dynamic beds free; reserved pool is exclusive to ESI 1-2"
            )

        self.assignment_log.append(outcome)
        return outcome

    def discharge_bed(self, pool):
        if pool == "dynamic" and self.dynamic_occupied > 0:
            self.dynamic_occupied -= 1
        elif pool == "reserved_critical" and self.reserved_occupied > 0:
            self.reserved_occupied -= 1


if __name__ == "__main__":
    import json
    from triage_engine import triage_patient

    with open("patients.json") as f:
        patients = json.load(f)

    bm = BedManager(total_beds=22, reserved_pct=0.10)
    print(f"Total beds: {bm.total_beds} | Dynamic (90%): {bm.dynamic_beds} | "
          f"Reserved critical (10%): {bm.reserved_beds}\n")

    for p in patients:
        r = triage_patient(p)
        outcome = bm.assign_bed(r["patient_id"], r["final_esi_level"])
        print(f"{r['patient_id']} ESI={r['final_esi_level']} -> {outcome['assigned_pool'] or 'WAITLISTED'}")

    print("\nFinal bed status:", json.dumps(bm.status(), indent=2))
