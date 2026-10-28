"""Extract the three Spain forms offline; private output stays under ignored output/."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spain_pdf_extractor import extract_spain_pdf, compare_spain_values

FILES={'schengen_application':'Schengen_Application.pdf','bank_declaration':'Bank-Decleration.pdf',
       'national_id_translation':'National_ID_Translation.pdf'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=Path('output/spain_extraction'))
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    reports={}
    for name,filename in FILES.items():
        result=extract_spain_pdf((args.source_dir/filename).read_bytes(),name,filename)
        reports[name]=result
        print(f'{name}: {result["status"]}; {len(result["filled_values"])} populated keys; '
              f'{len(result["unassigned_answers"])} unassigned objects; AI requests=0')
    files={'filled_values.json':{key:value['filled_values'] for key,value in reports.items()},
           'all_values.json':{key:value['values'] for key,value in reports.items()},
           'extraction_evidence.json':reports,'comparisons.json':compare_spain_values(reports)}
    for filename,value in files.items():
        (args.output_dir/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
