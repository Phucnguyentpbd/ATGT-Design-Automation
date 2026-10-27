"""Real stdio boundary: discover schema, call tools, preserve source and reject drift."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import sqlite3
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from atgt.qcvn_ingest import PDF_SHA, digest
from atgt.service import ATGTService


@pytest.fixture
def sources(tmp_path):
    dbpath=tmp_path/'test.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.executescript('''
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE pages(page INTEGER PRIMARY KEY,annex TEXT,text TEXT,requires_visual_review INTEGER);
            CREATE VIRTUAL TABLE page_fts USING fts5(text,content='pages',content_rowid='page');
            CREATE TABLE articles(article INTEGER);
            CREATE TABLE sign_index(code TEXT,pages_json TEXT,count INTEGER,status TEXT);
            CREATE TABLE mark_index(code TEXT,pages_json TEXT,count INTEGER,status TEXT);
            CREATE TABLE cad_assets(asset_id TEXT,source_path TEXT,sha256 TEXT,candidate_codes_json TEXT,status TEXT);
            CREATE TABLE line_patterns(name TEXT);
        ''')
        db.executemany('INSERT INTO metadata VALUES (?,?)',[('schema_version','1'),('qcvn_pdf_sha256',PDF_SHA)])
        db.executemany('INSERT INTO pages VALUES (?,?,?,?)',[
            (80,'B','Synthetic P.102 first source passage',0),
            (81,'B','Synthetic P.102 second source passage',1),
            (166,'G','Synthetic marking 3.1a source text',0)])
        db.execute("INSERT INTO page_fts(page_fts) VALUES ('rebuild')")
        db.execute("INSERT INTO sign_index VALUES ('P.102','[80,81]',2,'source_text_only')")
        db.execute("INSERT INTO mark_index VALUES ('3.1a','[166]',1,'source_text_only')")
        db.execute("INSERT INTO cad_assets VALUES ('fixture-102','Bien_Cam/102.dwg',?,'[\"P.102\"]','unverified')",('a'*64,))
    lin=tmp_path/'test.lin'
    lin.write_text('*VACH_3.1B_0.6M,Synthetic\nA,0.6,-0.6\n',encoding='utf-8')
    rules=tmp_path/'rules.toml'
    rules.write_text(r'''
schema_version=1
ruleset_id="ATGT-TEST-RULES-V1"
effective_date="2026-10-26"
language="vi"
scope=["ordinary","divided_rural"]
[source_precedence]
qcvn_specific_overrides_user_rule=true
[project_inputs]
layer_names_are_never_reused_as_defaults=true
[priority]
main_route_default="priority"
cross_roads_default="non_priority"
same_level_family="W.205"
non_priority_branch_family="W.207"
[sign_position]
tcvn4054_s1_is_fallback_only_after_qcvn_search=true
[junction_grouping]
group_when_consecutive_station_gap_is_less_than_s1=true
equal_to_s1_starts_new_group=true
all_non_priority_dense_group_codes=["W.207d","W.207e"]
s501_length_from_sign_to_last_junction=true
s501_rounding_m=10
[marking_3_1a]
outer_edge_centerline_offset_m=0.30
median_edge_centerline_offset_m=0.50
[marking_3_1b]
linetype="VACH_3.1B_0.6M"
[marking_4_4]
legacy_writer_allowed=false
[annotation]
archetype_drawing="E:\\TEMPLATE CV\\BINH DO ATGT DU AN MAU\\BD TK ATGT TAY VAN CANH.dwg"
excluded_archetype_drawing="BD TK ATGT DA DT.633.dwg"
[assets]
asset_catalog="C:\\fixture\\atgt-asset-catalog.json"
asset_catalog_id="ATGT-ASSETS-TEST-V1"
sign_code_requires_prefix=true
asset_geometry_review_required_before_insert=true
agent_must_resolve_asset_id_before_import=true
agent_must_not_pass_arbitrary_asset_paths=true
[statistics]
post_type_is_not_inferred=true
post_quantity_is_not_automated=true
[cad_safety]
source_dwg_must_not_be_saved=true
distinct_work_copy_required=true
one_writer_per_drawing=true
readback_required_before_save=true
[agent_behavior]
load_rules_at_start_of_every_task=true
do_not_repeat_rules_in_user_prompt=true
''',encoding='utf-8')
    return dbpath,lin,rules


def edge_request():
    return {'kind':'edge','intervals':[{
        'snapshot_id':'fixture-snapshot','alignment_id':'T1','edge_handle':'A1',
        'road_type':'ordinary','edge_role':'outer_pavement','scenario':'local_access',
        'start_m':'100','end_m':'120','width_m':'0.15','carriageway_width_m':'7',
        'available_paved_width_m':'3.5','boundary_evidence':'fixture edge review',
        'direction_evidence':'fixture direction','outer_edge_matches_running_edge':True,
        'turning_permitted':True,'movement_evidence':'fixture approved access'}]}


def test_stdio_workflow_and_source_drift(sources):
    db,lin,rules=sources
    before=digest(db)
    source_dir=str(Path(__file__).resolve().parents[1]/'src')
    params=StdioServerParameters(command=sys.executable,
        args=['-m','atgt.mcp_server','--db',str(db),'--lin',str(lin),'--lin-sha256',digest(lin),
              '--rules',str(rules)],
        env={**os.environ,'PYTHONPATH':source_dir,'PYTHONUTF8':'1'})

    async def run():
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=15)) as session:
                await session.initialize()
                definitions=(await session.list_tools()).tools
                names={t.name for t in definitions}
                assert names=={'atgt_status','atgt_get_project_rules','atgt_search','atgt_get',
                               'atgt_resolve_asset','atgt_evaluate_rules','atgt_validate_plan'}
                assert all(t.annotations.readOnlyHint and not t.annotations.destructiveHint and t.outputSchema for t in definitions)

                async def call(name,**kwargs):
                    result=await session.call_tool(name,kwargs)
                    assert not result.isError, result.content
                    assert result.structuredContent['cad_execution_allowed'] is False
                    return result.structuredContent

                status=await call('atgt_status')
                assert status['counts']['pages']==3 and status['sources']['knowledge_sha256']==before
                loaded_rules=await call('atgt_get_project_rules',section='priority')
                assert loaded_rules['ruleset_id']=='ATGT-TEST-RULES-V1'
                assert loaded_rules['rules']['main_route_default']=='priority'
                assert status['sources']['project_rules_sha256']==digest(rules)
                first=await call('atgt_search',query='P.102',limit=1)
                second=await call('atgt_search',query='P.102',limit=1,offset=first['next_offset'])
                assert first['total_count']==2 and first['has_more'] and not second['has_more']
                assert first['items'][0]['page'] != second['items'][0]['page']
                text=await call('atgt_get',kind='page',key='80',limit=9)
                assert text['record']['text']=='Synthetic' and text['record']['next_offset']==9
                code=await call('atgt_get',kind='sign',key='P.102')
                assert code['record']['pages']==[80,81] and code['record']['status']=='source_text_only'
                asset=await call('atgt_resolve_asset',sign_code='P.102')
                assert asset['resolution']=='blocked' and asset['items'][0]['status']=='unverified'
                # SQL/FTS punctuation stays data; no operator expansion or SQL execution.
                assert (await call('atgt_search',query='" OR * --'))['total_count']==0
                invalid=await session.call_tool('atgt_get',{'kind':'page','key':'../../secret'})
                assert invalid.isError

                request=edge_request()
                plan=await call('atgt_evaluate_rules',request=request)
                assert plan['sources']['project_ruleset_id']=='ATGT-TEST-RULES-V1'
                assert plan['sources']['project_rules_sha256']==digest(rules)
                assert plan['proposals'][0]['marking_code']=='3.1b'
                assert plan['proposals'][0]['centerline_offset_m']=='0.30'
                checked=await call('atgt_validate_plan',request=request,candidate=plan)
                assert checked['ready_for_geometry_review'] and checked['validation_level']=='proposal_consistency_only'
                changed=deepcopy(plan);changed['proposals'][0]['centerline_offset_m']='0.50'
                assert not (await call('atgt_validate_plan',request=request,candidate=changed))['matches_recomputed_plan']
                request['intervals'][0]['turning_permitted']=None
                blocked=await call('atgt_evaluate_rules',request=request)
                assert blocked['blocked_count']==1 and blocked['proposals'][0]['marking_code'] is None
                request['intervals'][0]['turning_permitted']='true'
                assert (await session.call_tool('atgt_evaluate_rules',{'request':request})).isError
                request=edge_request()
                request['intervals'].append(deepcopy(request['intervals'][0]))
                request['intervals'][1]['snapshot_id']='other-drawing'
                assert (await session.call_tool('atgt_evaluate_rules',{'request':request})).isError
                request=edge_request()
                request['intervals'] *= 51
                assert (await session.call_tool('atgt_evaluate_rules',{'request':request})).isError
                box=json.loads((Path(__file__).resolve().parents[1]/'examples/box44-contexts.json').read_text(encoding='utf-8'))
                box_request={'kind':'box44','junctions':box['junctions']}
                boxes=await call('atgt_evaluate_rules',request=box_request)
                assert boxes['blocked_count']==0 and len(boxes['proposals'][0]['boxes'])==1
                box_request['junctions'][0]['physical_median_present']=True
                assert (await call('atgt_evaluate_rules',request=box_request))['blocked_count']==1
                sign_request={'kind':'sign_placement','signs':[{
                    'snapshot_id':'fixture-snapshot','alignment_id':'T1','target_id':'hazard-1',
                    'sign_code':'W.201a','road_type':'ordinary','travel_direction':'increasing',
                    'design_speed_kmh':60,'alignment_start_m':'0','alignment_end_m':'1000',
                    'target_station_m':'500','qcvn_search_evidence':'fixture reviewed search',
                    'qcvn_no_numeric_distance_confirmed':True}]}
                sign_plan=await call('atgt_evaluate_rules',request=sign_request)
                assert sign_plan['blocked_count']==1
                assert 'tcvn4054_source_not_configured_or_verified' in sign_plan['proposals'][0]['issues']
                assert digest(db)==before  # All preceding calls preserve source bytes.
                with sqlite3.connect(db) as writer:
                    writer.execute("UPDATE pages SET text='external modification' WHERE page=80")
                drift=await session.call_tool('atgt_status',{})
                assert drift.isError and 'sources changed' in str(drift.content)
    asyncio.run(run())


def test_source_binding_rejects_wrong_pdf_and_missing_db(sources,tmp_path):
    db,lin,_=sources
    with sqlite3.connect(db) as writer:
        writer.execute("UPDATE metadata SET value=? WHERE key='qcvn_pdf_sha256'",('0'*64,))
    with pytest.raises(ValueError,match='locked QCVN'):
        ATGTService(db,lin,digest(lin))
    missing=tmp_path/'missing.sqlite'
    with pytest.raises(FileNotFoundError):ATGTService(missing,lin,digest(lin))
    assert not missing.exists()
    fake_tcvn=tmp_path/'tcvn4054.pdf'
    fake_tcvn.write_bytes(b'not the locked TCVN 4054 source')
    with pytest.raises(ValueError,match='TCVN 4054 checksum mismatch'):
        ATGTService(db,lin,digest(lin),fake_tcvn)


def test_project_rules_are_required_for_evaluation_and_bound_for_the_session(sources):
    db,lin,rules=sources
    unconfigured=ATGTService(db,lin,digest(lin))
    with pytest.raises(ValueError,match='Project rules are not configured'):
        unconfigured.evaluate(edge_request())

    service=ATGTService(db,lin,digest(lin),project_rules_path=rules)
    assert service.get_project_rules('priority')['rules']['main_route_default']=='priority'
    original=rules.read_text(encoding='utf-8')
    rules.write_text(original.replace('main_route_default="priority"',
                                      'main_route_default="equal"'),encoding='utf-8')
    with pytest.raises(ValueError,match='Configured project rules changed'):
        service.status()
    with pytest.raises(ValueError,match='incompatible with the executable rules'):
        ATGTService(db,lin,digest(lin),project_rules_path=rules)
