"""Installed CLI: reproducible seven-engine examples with no network calls."""
import argparse
from importlib.resources import files
import json
from pathlib import Path
from .pipeline import run_pipeline


def load_fixture(name='populated'):
    case = json.loads(files('property_underwriting').joinpath('fixtures/seven_engine.json').read_text())
    if name == 'insufficient':
        case.update(sale_comps=[], rental_comps=[], condition_evidence=[], quotes=[], payment_standard=None)
    elif name == 'identity-conflict':
        conflict = dict(case['observations'][0], observation_id='synthetic-conflicting-area', normalized_value=5000, raw_value=5000)
        case['observations'].append(conflict)
    elif name != 'populated':
        raise ValueError('Unknown fixture')
    return case


def load_scenario():
    return json.loads(files('property_underwriting').joinpath('fixtures/financial_scenario.json').read_text())


def render_report(result):
    e = result['engines']
    d = result['decision']
    lines = ['PROPERTY UNDERWRITING INTELLIGENCE', 'Seven-engine synthetic demonstration | zero live calls',
             result['warning'], '', 'ENGINE / READINESS']
    for i, (domain, row) in enumerate(d['domain_readiness'].items(), 1):
        lines.append(f'{i}. {domain:18} {row["status"]}')
    lines.extend([f'7. DECISION           {d["real_evidence_decision_state"]}', '',
                  f'Synthetic ARV: {e["ENGINE4"]["ARV_BASE"]} | accepted sales: {e["ENGINE4"]["accepted_comp_count"]}',
                  f'Synthetic market rent/month: {e["ENGINE5"]["market_rent"]["MARKET_RENT_BASE"]}',
                  f'Priced rehab subset only: {e["ENGINE3"]["VISIBLE_REHAB_BASE"]}',
                  'Unpriced work and hidden systems remain unknown; the subset is not a complete budget.',
                  f'HCV approved contract rent: {e["ENGINE5"]["APPROVED_HCV_CONTRACT_RENT"]}',
                  'HCV payment standards are reference values, never guaranteed revenue.'])
    if result['scenario']:
        s = result['scenario']
        lines.extend(['', 'SEPARATE SYNTHETIC FINANCIAL SCENARIO (does not clear blockers)',
                      f'Financial profile: {s["FINANCIAL_PROFILE_STATUS"]}; sources and uses: {s["sources_and_uses"]["status"]}'])
        for metric in ('TOTAL_PROJECT_COST', 'NET_OPERATING_INCOME', 'DSCR', 'MONTHLY_CASH_FLOW'):
            item = s['metrics'][metric]
            value = 'UNAVAILABLE' if item['value'] is None else f'{item["value"]:,.2f}'
            lines.append(f'{metric}: {value} [{item["evidence_class"]}]')
    lines.extend(['', f'READINESS BLOCKERS ({len(d["hard_blockers"])})'])
    lines.extend(f'- {b["code"]}: {b["message"]}' for b in d['hard_blockers'])
    lines.extend(['', 'NEXT ACTIONS'])
    for action in d['next_required_actions']:
        deps = ', '.join(action['depends_on']) or 'none'
        lines.append(f'{action["priority"]}. {action["title"]} [depends on: {deps}]')
    lines.extend(['', 'Acquisition recommendation: DISABLED. Readiness is not investment merit.'])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['populated', 'insufficient', 'identity-conflict'], default='populated')
    parser.add_argument('--no-scenario', action='store_true')
    parser.add_argument('--json', action='store_true', help='Print full provenance and all seven engine records')
    parser.add_argument('--output', type=Path, help='Write the report to a file instead of stdout')
    args = parser.parse_args(argv)
    result = run_pipeline(load_fixture(args.case), None if args.no_scenario else load_scenario())
    report = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n' if args.json else render_report(result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    else:
        print(report, end='')


if __name__ == '__main__':
    main()
