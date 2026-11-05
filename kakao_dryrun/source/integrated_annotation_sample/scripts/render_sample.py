#!/usr/bin/env python3
"""Render the annotation viewer from current package JSON; no network requests."""
import argparse
import base64
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def esc(value):
    return html.escape(str(value), quote=True)


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def json_script(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def box_pixels(item):
    if item.get('bbox_xyxy_pixels') is not None:
        return item['bbox_xyxy_pixels']
    box = item.get('bbox_xyxy_norm')
    if box is not None:
        return [box[0]*1920, box[1]*1080, box[2]*1920, box[3]*1080]
    return None


def rect(box, attrs=''):
    x1,y1,x2,y2=box
    return f'<rect x="{x1:.2f}" y="{y1:.2f}" width="{x2-x1:.2f}" height="{y2-y1:.2f}" {attrs}/>'


def layers(a):
    chunks=[]
    for region in a.get('regions', []):
        layer='c' if region['type']=='driving_area' else 'regions'
        shapes=''
        if region.get('polygon_xy_norm'):
            points=' '.join(f'{x*1920:.2f},{y*1080:.2f}' for x,y in region['polygon_xy_norm'])
            shapes=f'<polygon points="{points}"/>'
        elif box_pixels(region):
            shapes=rect(box_pixels(region))
        if shapes:
            chunks.append(f'<g class="layer layer-{layer}" data-layer="{layer}"><title>{esc(region["region_id"])} · {esc(region.get("geometry_status"))}</title>{shapes}</g>')
    for o in a['objects']:
        kind='added' if '_added_' in o['object_id'] else 'source'
        oid=esc(o['object_id']); b=box_pixels(o)
        chunks.append(f'<g class="layer object-box layer-{kind}" data-layer="{kind}" data-object="{oid}" tabindex="0" role="button" aria-label="{oid}: {esc(o["class"])}"><title>{oid} · {esc(o["observation"])}</title>{rect(b)}<text class="box-label" x="{max(6,min(b[0]+4,1730)):.2f}" y="{max(24,b[1]-7):.2f}">{oid}</text></g>')
        points=o.get('footprint_evidence',{}).get('contact_points_xy_norm',[])
        for x,y in points:
            chunks.append(f'<g class="layer layer-contact" data-layer="contact"><title>{oid} · 관측 접지점</title><circle cx="{x*1920:.2f}" cy="{y*1080:.2f}" r="7"/><path d="M {x*1920-13:.2f} {y*1080:.2f} h 26 M {x*1920:.2f} {y*1080-13:.2f} v 26"/></g>')
    for candidate in a.get('review_candidates',[]):
        box=box_pixels(candidate)
        if box:
            chunks.append(f'<g class="layer layer-candidates" data-layer="candidates"><title>{esc(candidate["candidate_id"])} · {esc(candidate["reason"])}</title>{rect(box)}</g>')
    return ''.join(chunks)


def view_card(a, standalone):
    v=a['view']; objects=a['objects']; added=sum('_added_' in o['object_id'] for o in objects)
    img='data:image/png;base64,'+base64.b64encode((ROOT/a['image_path']).read_bytes()).decode('ascii') if standalone else a['image_path']
    title={'F':'Front · 기본 Track 1 입력','B':'Back · 보조 시야','L':'Left · 보조 시야','R':'Right · 보조 시야'}[v]
    controls=[]
    for key,name,checked in [('source','원본 Box',True),('added','추가 Box',True),('c','C 초안',True),('regions','출입구 후보',True),('contact','접지점',True),('candidates','미확정 후보',False)]:
        if v!='F' and key in ['c','regions','contact']:continue
        controls.append(f'<label class="control {key}"><input type="checkbox" data-toggle="{key}" {"checked" if checked else ""}> {name}</label>')
    controls.append('<label class="control"><input type="checkbox" data-labels> ID 표시</label>')
    rows=[]
    for o in objects:
        kind='추가' if '_added_' in o['object_id'] else '원본'
        rows.append(f'<tr id="row-{esc(o["object_id"])}" data-row-object="{esc(o["object_id"])}"><td><button class="text-button" data-object-select="{esc(o["object_id"])}">{esc(o["object_id"])}</button><span class="mini {"new" if kind=="추가" else "imported"}">{kind}</span></td><td>{esc(o["class"])}</td><td>{esc(o.get("semantic_role",""))}<br><span class="muted">{esc(o.get("placement",""))}</span></td><td>{esc(o.get("truncated","U"))}</td><td><span class="mini">{esc(o.get("annotation_status","Draft"))}</span></td><td>{esc(o.get("observation",""))}</td></tr>')
    candidates=''.join(f'<li><code>{esc(c["candidate_id"])}</code> — {esc(c["reason"])}</li>' for c in a.get('review_candidates',[]))
    special=''
    if v=='F':
        special='''<div class="focus-grid"><div class="focus-frame"><svg viewBox="490 325 140 140" role="img" aria-label="추가한 보행자 확대"><use href="#image-F"/><rect x="540" y="353" width="27" height="76" fill="none" stroke="#00f1b8" stroke-width="1.5"/></svg><p><code>F_added_001</code> · 별도 사람 instance를 추가했습니다. 발·하체와 출입구 경계 관계는 미확정입니다.</p></div><div class="focus-notes"><h3>F에서 달라진 근거</h3><ul><li>R1: sedan 외 187·189·190의 관측 바퀴 접지점을 추가했습니다.</li><li>R2: 사람을 추가했지만 출입구 경계·C 연결이 불명확해 U를 유지했습니다.</li><li>R4: 186은 영향 구간 검수 후보로 분리했습니다. C 비중첩만으로 제외한 것은 아닙니다.</li><li>라바콘 의심 부분은 후미등과 구분하기 어려워 객체 수에 포함하지 않았습니다.</li></ul></div></div>'''
    return f'''<article class="view-card" id="view-{v}" data-view="{v}">
      <div class="section-heading"><div><span class="eyebrow">VIEW {v}</span><h2>{title}</h2></div><span class="count">원본 {len(objects)-added} + 추가 {added} = {len(objects)}</span></div>
      <p class="muted">{esc(a.get('summary',''))}</p>
      <div class="toolbar">{''.join(controls)}<label class="zoom-control">확대 <select data-zoom aria-label="{v} 이미지 확대"><option value="1">100%</option><option value="1.5">150%</option><option value="2">200%</option><option value="3">300%</option></select></label></div>
      <div class="canvas-scroll"><svg class="scene-svg" viewBox="0 0 1920 1080" role="img" aria-label="{v} 원본과 수정 Annotation"><defs><image id="image-{v}" width="1920" height="1080" href="{img}"/></defs><use href="#image-{v}"/>{layers(a)}</svg></div>
      <div class="selection" aria-live="polite" data-selection>Box 또는 아래 목록의 ID를 누르면 해당 객체를 확인할 수 있습니다. 노란 출입구 후보는 확정 경계가 아닙니다.</div>
      {special}
      <details class="object-details"><summary>객체 {len(objects)}개 · 역할·배치·잘림·근거 보기</summary><div class="table-scroll"><table class="object-table"><thead><tr><th>ID / 출처</th><th>Class</th><th>역할 / 배치</th><th>잘림</th><th>상태</th><th>관측 근거</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>
      <details><summary>미확정 검수 후보 {len(a.get('review_candidates',[]))}개</summary><p class="muted">이 목록은 Object 정답 수와 구분합니다. 그림의 보라색 후보 표시를 켜서 위치를 확인할 수 있습니다.</p><ul>{candidates}</ul></details>
      <details><summary>전체 Reference Annotation JSON · {v}</summary><p class="muted">속성별 Source/Evidence/Status, Object, Region, 대상별 관계와 검수 목록을 포함합니다. 모델 입력에 넣지 않습니다.</p><button class="download" data-download="annotation-{v}" data-filename="view_{v}.json">Annotation JSON 다운로드</button><pre>{esc(dump(a))}</pre></details>
    </article>'''


CSS='''
:root{--ink:#172c45;--blue:#255b9e;--muted:#607087;--line:#dce5ee;--paper:#fff;--source:#ffb454;--added:#00dca3;--c:#00d8ef;--region:#ffec50;--candidate:#d68cff}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#eef3f8;color:var(--ink);font-family:system-ui,-apple-system,BlinkMacSystemFont,"Noto Sans KR","Malgun Gothic",sans-serif;font-size:15px;line-height:1.7}main{max-width:1240px;margin:auto;padding:32px 28px 64px}h1,h2,h3{color:var(--blue);line-height:1.35}h1{font-size:32px;letter-spacing:-.7px;margin:12px 0}h2{font-size:24px;margin:2px 0 8px}h3{font-size:18px;margin:0 0 10px}p{margin:10px 0}button,input,select{font:inherit}button,select{cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #477eb9;outline-offset:3px}.tag{display:inline-block;padding:4px 11px;background:#fff0c7;color:#73520f;border-radius:6px;font-size:13px}.lead{max-width:930px;color:#425770;font-size:16px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}.stat{padding:15px 18px;background:#fff;border:1px solid var(--line);border-radius:12px}.stat span{display:block;color:var(--muted);font-size:13px}.stat strong{font-size:24px;color:var(--blue);font-weight:650}.overview,.view-card,.output-section{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:24px;margin:24px 0;min-width:0}.overview-grid{display:grid;grid-template-columns:1.1fr 1fr;gap:26px}.overview ul{margin:0;padding-left:22px}.note{padding:13px 16px;border-radius:8px;background:#edf5ff;color:#2a507c;border-left:4px solid #578ac6}.caution{background:#fff7e7;color:#775a25;border-left-color:#d0a34d}.tabs{position:sticky;top:0;z-index:10;display:flex;gap:8px;background:#eef3f8ee;backdrop-filter:blur(8px);padding:10px 0;flex-wrap:wrap}.tabs a{padding:7px 16px;border:1px solid #cddbea;border-radius:20px;background:white;text-decoration:none;color:var(--blue);font-size:14px}.tabs a:hover{background:#dfeefd}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:15px}.eyebrow{font-size:12px;color:#7b8ba0;letter-spacing:1.3px}.count{padding:6px 12px;background:#edf4fb;border-radius:8px;color:#3d5e83;font-size:13px;white-space:nowrap}.muted{color:var(--muted)}.toolbar{display:flex;align-items:center;gap:10px 16px;flex-wrap:wrap;background:#f6f9fc;border:1px solid var(--line);padding:10px 13px;border-radius:10px 10px 0 0;font-size:13px}.control{display:flex;align-items:center;gap:3px;cursor:pointer}.control input{accent-color:#3976b8}.control.source{border-bottom:2px solid var(--source)}.control.added{border-bottom:2px solid var(--added)}.control.c{border-bottom:2px solid var(--c)}.control.regions{border-bottom:2px solid #c0a000}.control.candidates{border-bottom:2px solid #b45deb}.zoom-control{margin-left:auto;white-space:nowrap}.zoom-control select{padding:2px 4px;border:1px solid #ccd9e8;border-radius:4px;background:white}.canvas-scroll{overflow:auto;background:#152130;border-radius:0 0 10px 10px}.scene-svg{display:block;width:100%;height:auto;max-width:none}.layer-source{stroke:var(--source);fill:none;stroke-width:3}.layer-added{stroke:var(--added);fill:none;stroke-width:4}.layer-c{stroke:var(--c);stroke-width:4;fill:#00d8ef0d;stroke-dasharray:17 10;pointer-events:none}.layer-regions{stroke:var(--region);stroke-width:4;fill:none;stroke-dasharray:10 8;pointer-events:none}.layer-contact{stroke:#fff;fill:#e83e68;stroke-width:2;pointer-events:none}.layer-candidates{stroke:var(--candidate);stroke-width:4;fill:none;stroke-dasharray:9 8;pointer-events:none;display:none}.object-box{cursor:pointer}.object-box rect{pointer-events:all;fill:transparent}.object-box:hover rect,.object-box.selected rect{stroke:white;stroke-width:6;fill:#fff2}.box-label{display:none;font-size:22px;stroke:#122232;stroke-width:3;paint-order:stroke;fill:white;font-family:monospace}.labels-on .box-label{display:block}.object-box.selected .box-label{display:block}.selection{min-height:53px;background:#f2f6fb;padding:11px 14px;border-radius:8px;margin-top:10px;font-size:13px}.selection.has-selection{border-left:4px solid #27ac8c}.focus-grid{display:grid;grid-template-columns:320px 1fr;gap:25px;margin:20px 0;align-items:center}.focus-frame{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#f6f9fc}.focus-frame svg{display:block;width:100%;height:auto;max-height:290px;background:#102030}.focus-frame p{padding:0 12px;font-size:12px}.focus-notes ul{padding-left:20px;margin:0}.focus-notes li{margin:8px 0}.table-scroll{overflow-x:auto;max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:11px 10px;vertical-align:top;border-bottom:1px solid var(--line)}th{background:#f3f7fb;color:#3c5c80;font-weight:600}td{overflow-wrap:anywhere}.object-table{min-width:800px}.object-table th:nth-child(1){width:165px}.object-table th:nth-child(2){width:150px}.object-table th:nth-child(3){width:120px}.object-table th:nth-child(6){min-width:280px}.object-table tr.selected{background:#eaf8f3}.text-button{border:0;background:none;color:var(--blue);text-align:left;padding:0;font-family:monospace;font-size:12px}.mini{display:inline-block;padding:0 6px;border:1px solid #d7e1eb;border-radius:4px;font-size:11px;color:#7b6527;white-space:nowrap}.mini.new{background:#e5f8f0;color:#12775a;margin-left:5px}.mini.imported{background:#fff1de;color:#8b5924;margin-left:5px}.download{border:1px solid #a8c2df;color:var(--blue);background:#f2f7fd;padding:6px 11px;border-radius:6px;font-size:13px}.download:hover{background:#dfeefd}details{margin-top:12px;border-top:1px solid #e4eaf0;padding-top:12px}summary{cursor:pointer;color:#2f5e95;font-weight:550}details ul{padding-left:22px}details li{margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;max-height:570px;overflow:auto;padding:18px;background:#14283f;color:#e5eef8;border-radius:9px;font-size:12px;line-height:1.6}code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.9em;background:#edf3f9;padding:1px 4px;border-radius:3px}pre code{background:none;padding:0}.relation-table{min-width:680px}.relation-table td:first-child{white-space:nowrap}.relation-table .state{font-size:20px;color:var(--blue)}.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:13px}.legend i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:5px}.footer{color:#718199;font-size:12px;margin-top:25px}article{scroll-margin-top:75px}
@media(max-width:760px){main{padding:18px 12px 40px}h1{font-size:27px}h2{font-size:21px}.overview,.view-card,.output-section{padding:17px 13px;margin:18px 0}.stats{grid-template-columns:repeat(2,1fr);gap:8px}.stat{padding:11px 13px}.overview-grid{grid-template-columns:1fr;gap:18px}.section-heading{align-items:flex-start;flex-direction:column;gap:4px}.count{font-size:12px}.toolbar{gap:8px 12px}.zoom-control{margin-left:0}.focus-grid{grid-template-columns:1fr;gap:16px}.focus-frame{max-width:360px}.tabs{gap:6px}.tabs a{padding:5px 12px}.selection{font-size:12px}.lead{font-size:14px}}
'''

JS='''
const dataset=JSON.parse(document.getElementById('viewer-data').textContent);
const objectMap=Object.fromEntries(dataset.annotations.flatMap(a=>a.objects.map(o=>[o.object_id,o])));
function selectObject(article,id,fromTable=false){
 const object=objectMap[id]; if(!object)return;
 article.querySelectorAll('[data-object]').forEach(el=>el.classList.toggle('selected',el.dataset.object===id));
 article.querySelectorAll('[data-row-object]').forEach(el=>el.classList.toggle('selected',el.dataset.rowObject===id));
 const out=article.querySelector('[data-selection]');out.classList.add('has-selection');
 out.textContent=id+' · '+object.class+' · '+object.semantic_role+' / '+object.placement+' · 잘림 '+object.truncated+' · '+object.observation;
 if(fromTable){const layer=article.querySelector('[data-object="'+id+'"]');if(layer){const checkbox=article.querySelector('[data-toggle="'+layer.dataset.layer+'"]');if(checkbox){checkbox.checked=true;checkbox.dispatchEvent(new Event('change'));}article.querySelector('.canvas-scroll').scrollIntoView({behavior:'smooth',block:'center'});}}
}
document.querySelectorAll('[data-view]').forEach(article=>{
 article.querySelectorAll('[data-toggle]').forEach(input=>input.addEventListener('change',()=>{article.querySelectorAll('[data-layer="'+input.dataset.toggle+'"]').forEach(el=>el.style.display=input.checked?'':'none');if(input.dataset.toggle==='candidates'&&input.checked)article.querySelectorAll('[data-layer="candidates"]').forEach(el=>el.style.display='inline');}));
 article.querySelector('[data-labels]').addEventListener('change',e=>article.classList.toggle('labels-on',e.target.checked));
 article.querySelector('[data-zoom]').addEventListener('change',e=>article.querySelector('.scene-svg').style.width=(Number(e.target.value)*100)+'%');
 article.querySelectorAll('[data-object]').forEach(el=>{el.addEventListener('click',()=>selectObject(article,el.dataset.object));el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectObject(article,el.dataset.object);}})});
 article.querySelectorAll('[data-object-select]').forEach(el=>el.addEventListener('click',()=>selectObject(article,el.dataset.objectSelect,true)));
});
document.querySelectorAll('[data-download]').forEach(button=>button.addEventListener('click',()=>{
 const key=button.dataset.download;const value=key==='prediction'?dataset.prediction:dataset.annotations.find(a=>'annotation-'+a.view===key);
 const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)+'\\n'],{type:'application/json;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download=button.dataset.filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}));
'''


def render(annotations,prediction,standalone):
    total=sum(len(a['objects']) for a in annotations)
    added=sum('_added_' in o['object_id'] for a in annotations for o in a['objects'])
    front=next(a for a in annotations if a['view']=='F')
    relrows=[]
    names={'R1':'Occupancy','R2':'Entrance','R3':'Occlusion','R4':'Restriction'}
    for rid,rel in front['track1']['relations'].items():
        ids=', '.join(rel['object_ids'])
        relrows.append(f'<tr><td>{rid} {names[rid]}</td><td class="state">{rel["state"]}</td><td><code>{esc(ids)}</code><br>{esc(rel["reason"])}</td></tr>')
    cards=''.join(view_card(a,standalone) for a in annotations)
    body=f'''<header><span class="tag">AI Draft · Human Review 0 · v0.2</span><h1>통합 Annotation · 수정 샘플</h1><p class="lead">누락한 가시 객체와 접지 근거를 보완하고, 원본 Annotation과 모델 출력 예시를 구분했습니다. 모든 Box·관계는 검수 전 초안입니다. 실제 모델을 호출한 결과가 아닙니다.</p></header>
    <div class="stats"><div class="stat"><span>방향별 원본</span><strong>4 views</strong></div><div class="stat"><span>전체 Draft 객체</span><strong>{total}</strong></div><div class="stat"><span>누락 보완</span><strong>+{added}</strong></div><div class="stat"><span>독립 검수 완료</span><strong>0</strong></div></div>
    <section class="overview"><div class="overview-grid"><div><h2>적용한 수정</h2><ul><li>원본 18개를 보존하고 가시 객체 17개를 추가했습니다.</li><li>Object 역할·배치·화면 잘림과 필드별 근거를 구조화했습니다.</li><li>모델 출력에 Region·근거 역할을 포함하고 Time of Day를 제외했습니다.</li><li>위치·Class·역할로 근거를 대조하며 ID 문자열은 정답으로 채점하지 않습니다.</li></ul></div><div><h2>아직 확정하지 않은 것</h2><ul><li>C의 좌우 경계·먼 쪽 종료 지점</li><li>출입구 경계·C 연결과 사람의 Footprint</li><li>라바콘 의심 부분과 일부 원거리 대상</li><li>숨은 영역의 정확한 Geometry와 전체 객체 목록의 완전성</li></ul></div></div><p class="note caution">C는 v0.1 Polygon을 비교용 Draft로 보존했습니다. 도로 전체 폭·자차 차선으로 확정한 영역이 아닙니다. 정식 V3/V4 점수는 산출하지 않으며, 관측 불가능한 숨은 Geometry의 근거 비교는 <code>deferred</code>로 남깁니다.</p><details><summary>F의 Relation과 수정 근거</summary><div class="table-scroll"><table class="relation-table"><thead><tr><th>Relation</th><th>Draft</th><th>근거</th></tr></thead><tbody>{''.join(relrows)}</tbody></table></div></details><details><summary>도로 속성·세 Track 처리</summary><p>Traffic Direction과 Direction Match는 Unknown입니다. 전체 측면의 Sidewalk는 차량 가림과 관측 범위 때문에 좌·우 U로 유지했습니다. 오른쪽 녹색 노면은 관측되지만 보행 전용 용도는 미확정입니다. Time of Day는 분석용 Annotation에만 보존합니다.</p><p>F만 기본 Track 1 입력입니다. B/L/R의 R1–R4는 null입니다. 네 이미지는 한 Source Group이며 시간 순서 Frame이 아닙니다. Track 2·3은 <code>missing_input</code>을 유지합니다.</p><p>도로 가장자리 배치인 <code>roadside</code>는 정차 상태를 뜻하지 않으며 R1 대응을 면제하지 않습니다. <code>speed_bump</code>는 Object로 보존하되 <code>road_feature</code>로 분류하여 R1 Actor/Obstacle에서 제외합니다.</p></details></section>
    <nav class="tabs" aria-label="시야 바로가기"><a href="#view-F">F · 전방</a><a href="#view-B">B · 후방</a><a href="#view-L">L · 좌측</a><a href="#view-R">R · 우측</a><a href="#model-output">출력 예시</a></nav>
    <div class="legend"><span><i style="background:var(--source)"></i>원본 Source Box</span><span><i style="background:var(--added)"></i>추가 AI Draft Box</span><span><i style="background:var(--c)"></i>C 초안</span><span><i style="background:var(--region)"></i>출입구 후보 ROI</span><span><i style="background:var(--candidate)"></i>미확정 검수 후보</span></div>
    {cards}
    <section class="output-section" id="model-output"><h2>모델 출력 형식 예시</h2><p>위의 전체 Reference Annotation과 별도입니다. 예시는 <code>expected/prediction.example.json</code>과 동일하며 실제 모델 응답이 아닙니다. Region 선언과 역할을 포함하고, 분석용 Time of Day·정답 C Geometry·검수 Metadata는 제외합니다.</p><button class="download" data-download="prediction" data-filename="prediction.example.json">출력 예시 JSON 다운로드</button><details><summary>출력 예시 JSON 펼치기</summary><pre>{esc(dump(prediction))}</pre></details><details><summary>ZIP에서 실행하기</summary><pre>python scripts/validate.py\npython scripts/test_evaluation.py\npython scripts/evaluate.py --prediction expected/prediction.example.json --allow-draft</pre><p class="muted">형식·참조·매칭 동작의 시험입니다. 예시가 자기 Reference와 일치하는 결과를 모델 성능으로 해석하지 않습니다. 독립 검수와 평가 범위 확정 후 Benchmark를 구성해야 합니다.</p></details></section>
    <p class="footer">Source 이미지·JSON은 보존했습니다. 모든 수정 라벨은 AI Draft이며, 이 문서는 관측 근거와 보완 상태를 검수하기 위한 자료입니다.</p>'''
    return '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Integrated Annotation Sample · v0.2</title><style>'+CSS+'</style></head><body><main>'+body+'</main><script type="application/json" id="viewer-data">'+json_script({'annotations':annotations,'prediction':prediction})+'</script><script>'+JS+'</script></body></html>\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--standalone',type=Path,help='Optional standalone HTML path with embedded original PNGs')
    args=parser.parse_args()
    annotations=[json.loads((ROOT/f'annotations/view_{v}.json').read_text(encoding='utf-8')) for v in ['F','B','L','R']]
    prediction=json.loads((ROOT/'expected/prediction.example.json').read_text(encoding='utf-8'))
    (ROOT/'sample.html').write_text(render(annotations,prediction,False),encoding='utf-8')
    if args.standalone:
        args.standalone.parent.mkdir(parents=True,exist_ok=True)
        args.standalone.write_text(render(annotations,prediction,True),encoding='utf-8')
    print(json.dumps({'sample':str(ROOT/'sample.html'),'standalone':str(args.standalone) if args.standalone else None,'objects':sum(len(a['objects']) for a in annotations)},ensure_ascii=False))


if __name__=='__main__':
    main()
