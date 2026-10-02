import argparse
import json
import logging
from radar.etl import create_run, execute_run

def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    parser=argparse.ArgumentParser(description='Radar: extracción y ETL oficial SUNAT')
    subs=parser.add_subparsers(dest='command',required=True)
    bulk=subs.add_parser('bulk');bulk.add_argument('--weeks',type=int,default=1);bulk.add_argument('--end');bulk.add_argument('--scope',choices=['plastics','all'],default='plastics');bulk.add_argument('--force',action='store_true',help='Revisitar fuente; preserva versiones originales anteriores')
    query=subs.add_parser('query');query.add_argument('--kind',choices=['importer','hs'],required=True);query.add_argument('--value',required=True);query.add_argument('--start',required=True);query.add_argument('--end',required=True);query.add_argument('--force',action='store_true')
    resume=subs.add_parser('resume');resume.add_argument('id')
    subs.add_parser('reprocess',help='Reaplicar normalización a originales ya cargados')
    args=vars(parser.parse_args());command=args.pop('command')
    if command=='bulk' and not 1<=args['weeks']<=52: parser.error('--weeks debe ser 1–52')
    run_id=args['id'] if command=='resume' else create_run(command,args,status='running')
    print('run_id='+run_id,flush=True)
    print(json.dumps(execute_run(run_id),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
