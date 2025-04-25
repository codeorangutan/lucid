import sys
import os
import argparse
from generate_report.report_generator import generate_report_json

def main():
    parser = argparse.ArgumentParser(description="Generate cognitive/ADHD report from JSON or DB, with flexible template.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--patient-id', type=str, help='Patient ID to generate report for (preferred)')
    # Optionally add referral-id/pdf logic here if needed
    parser.add_argument('--output', type=str, help='Output PDF path (default: auto-named)')
    parser.add_argument('--json-dir', type=str, default="json", help='Directory for JSON files (default: json)')
    # Section toggles (add CLI flags if you want, or edit config dict below)
    args = parser.parse_args()

    patient_id = args.patient_id
    if not patient_id:
        print("[ERROR] Must specify --patient-id")
        sys.exit(1)

    # Output path
    if args.output:
        output_path = args.output
    else:
        output_path = f"report_{patient_id}.pdf"

    # Section toggles (edit as needed)
    config = {
        "include_demographics": True,
        "include_cognitive_scores": True,
        "include_subtests": True,
        "include_asrs": True,
        "include_dass": True,
        "include_epworth": True,
        "include_npq": True,
    }

    # Generate report from JSON (extract if needed)
    generate_report_json(
        patient_id=patient_id,
        output_path=output_path,
        json_dir=args.json_dir,
        config=config
    )
    print(f"[INFO] Report generated at {output_path}")

if __name__ == "__main__":
    main()
