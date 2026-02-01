"""
Risk Scan Demo (Survivability Gate)

Demonstrates governance-first risk scanning.
"""

import subprocess


def main():
    print("=== Risk Scan Demo ===")
    cmd = [
        "python",
        "tools/risk_scan.py",
        "--exchange",
        "bybit",
        "--profile",
        "paper",
    ]

    subprocess.run(cmd, check=False)

    print("\\nRisk scan finished.")
    print("Governance exists before execution.")


if __name__ == "__main__":
    main()
