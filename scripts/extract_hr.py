"""Extract a combined or split HR package and compare it to one Spain application."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hr_extractor import extract_hr_documents,compare_hr_with_application,make_hr_review_template
from spain_pdf_extractor import extract_spain_pdf
from scripts.run_spain_pilot import format_review_report


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hr',type=Path,nargs='+',required=True)
    parser.add_argument('--application',type=Path,required=True)
    parser.add_argument('--language',choices=['ar','en'],default='ar')
    parser.add_argument('--reviewed-values',type=Path)
    parser.add_argument('--output-dir',type=Path,default=Path('output/hr_pilot'))
    args=parser.parse_args()
    try:
        inputs={path:path.read_bytes() for path in [*args.hr,args.application,*([args.reviewed_values] if args.reviewed_values else [])]}
        reviewed=json.loads(inputs[args.reviewed_values].decode('utf-8-sig')) if args.reviewed_values else None
        application=extract_spain_pdf(inputs[args.application],'schengen_application',args.application.name)
        hr=extract_hr_documents([(path.name,inputs[path]) for path in args.hr],args.language,reviewed)
        comparison=compare_hr_with_application(hr,application)
    except (OSError,ValueError,ImportError) as error:parser.error(str(error))
    args.output_dir.mkdir(parents=True,exist_ok=True)
    report=format_review_report(comparison)
    for filename,data in [('hr_evidence.json',hr),('hr_values.json',hr['values']),
                          ('hr_comparisons.json',comparison),('hr_review_template.json',make_hr_review_template(hr))]:
        (args.output_dir/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report_path=args.output_dir/'review_report.txt'
    report_path.write_text(report,encoding='utf-8')
    print(report,flush=True)
    print(f'AI requests=0. Report saved to: {report_path.resolve()}',flush=True)


if __name__=='__main__':main()
