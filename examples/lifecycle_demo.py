"""Minimal lifecycle demo — earned autonomy in ~30 seconds.

A side-effecting (G3) action is rejected with zero side effects while the
runtime is still climbing the gear ladder, then admitted once the gear has
been earned through clean cycles. Run:

    python examples/lifecycle_demo.py
"""
from entropy_sdk import EntropyRuntime, Gear, action, observe


def main() -> None:
    world = {"deleted": []}

    def delete_records(table: str) -> str:
        world["deleted"].append(table)
        return f"deleted {table}"

    rt = EntropyRuntime(utility=lambda s, a: 1.0, theta=0.15,
                        initial_gear=Gear.OBSERVE)
    good = observe(lambda: 1)
    risky = action(delete_records, "users", required_gear=Gear.EXECUTE)

    def climb(n: int) -> None:
        for _ in range(n):
            rt.step(state=None, action=good, execute=lambda a: a())
        print(f"climbed {n} clean cycles -> gear {rt.state.gear.label}")

    climb(6)                                   # G0 -> Plan
    r = rt.step(state=None, action=risky, execute=lambda a: a())
    print(f"attempt risky at {r.gear_before.label}: executed={r.executed}, "
          f"world={world['deleted']}  (rejected, zero side effects)")

    climb(6)                                   # earned back up -> Execute
    r = rt.step(state=None, action=risky, execute=lambda a: a())
    print(f"attempt risky at {r.gear_before.label}: executed={r.executed}, "
          f"world={world['deleted']}  (admitted after earning the gear)")

    print(f"\naudit entries: {len(rt.audit.entries)}, "
          f"acceptance rate: {rt.audit.gate_acceptance_rate():.2f}")


if __name__ == "__main__":
    main()
