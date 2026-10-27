"""Probe a real local stdio server with configured sources and synthetic contexts."""
import argparse
import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def probe(args):
    root=Path(__file__).resolve().parents[1]
    params=StdioServerParameters(command=sys.executable,
        args=['-m','atgt.mcp_server','--db',str(args.db.resolve()),'--lin',str(args.lin.resolve()),
              '--tcvn4054',str(args.tcvn4054.resolve()),'--rules',str(args.rules.resolve())],
        env={**os.environ,'PYTHONUTF8':'1','PYTHONPATH':str(root/'src')})
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=20)) as session:
            await session.initialize()
            async def call(name,**kwargs):
                result=await session.call_tool(name,kwargs)
                if result.isError:raise RuntimeError(f'{name}: {result.content}')
                return result.structuredContent
            definitions=await session.list_tools()
            result={'tools':[t.name for t in definitions.tools], 'status':await call('atgt_status')}
            result['project_rules']=await call('atgt_get_project_rules',section='all')
            result['search']=await call('atgt_search',query='P.102',limit=3)
            result['source']=await call('atgt_get',kind='sign',key='P.102')
            result['asset']=await call('atgt_resolve_asset',sign_code='P.102')
            for kind,field,file in [('edge','intervals','edge-contexts.json'),('box44','junctions','box44-contexts.json')]:
                example=json.loads((root/'examples'/file).read_text(encoding='utf-8'))
                request={'kind':kind,field:example[field]}
                plan=await call('atgt_evaluate_rules',request=request)
                validation=await call('atgt_validate_plan',request=request,candidate=plan)
                if not validation['matches_recomputed_plan']:raise RuntimeError('Unchanged proposal failed consistency')
                changed=deepcopy(plan);changed['cad_execution_allowed']=True
                rejection=await call('atgt_validate_plan',request=request,candidate=changed)
                if rejection['matches_recomputed_plan']:raise RuntimeError('Tampered plan was accepted')
                result[kind]={'request':request,'plan':plan,'validation':validation,'tamper_rejected':True}
            for kind,field,file in [
                    ('sign_placement','signs','sign-placement-contexts.json'),
                    ('junction_warning','corridors','junction-warning-contexts.json')]:
                example=json.loads((root/'examples'/file).read_text(encoding='utf-8'))
                request={'kind':kind,field:example[field]}
                plan=await call('atgt_evaluate_rules',request=request)
                validation=await call('atgt_validate_plan',request=request,candidate=plan)
                if plan['blocked_count'] or not validation['matches_recomputed_plan']:
                    raise RuntimeError(f'{kind} proposal was blocked or failed consistency')
                result[kind]={'request':request,'plan':plan,'validation':validation}
            if result['edge']['plan']['blocked_count'] != 1:raise RuntimeError('Missing movement evidence was not blocked')
            if len(result['box44']['plan']['proposals'][0]['boxes']) != 1:raise RuntimeError('4.4 skill classification failed')
            if result['sign_placement']['plan']['proposals'][0]['distance_before_target_m'] != '75':
                raise RuntimeError('TCVN 4054 stopping sight distance failed')
            warning=result['junction_warning']['plan']['proposals'][0]['placements'][0]
            if warning['representative_sign_code'] != 'W.207d' or warning['s501_length_m'] != '130':
                raise RuntimeError('W.207 dense-sequence grouping failed')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'tools':result['tools'],'source_counts':result['status']['counts'],
                      'edge_proposals':len(result['edge']['plan']['proposals']),
                      'edge_blocked':result['edge']['plan']['blocked_count'],'box44_boxes':1,
                      'sign_distance_m':'75','junction_sign':'W.207d','s501_length_m':'130',
                      'tamper_rejected':True,'cad_execution_allowed':False},ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True,type=Path)
    p.add_argument('--lin',required=True,type=Path)
    p.add_argument('--tcvn4054',required=True,type=Path)
    p.add_argument('--rules',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.output.resolve() in {args.db.resolve(),args.lin.resolve(),args.tcvn4054.resolve(),
                                 args.rules.resolve()}:
        p.error('Output must differ from sources')
    asyncio.run(probe(args))


if __name__=='__main__':main()
