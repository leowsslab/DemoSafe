"""Read-only app review probes plus public package/version vulnerability lookup.
No uploaded media, OCR text, keys or machine paths are sent to OSV.
"""
from pathlib import Path
import argparse,json,hashlib,subprocess,sys,urllib.request
from urllib.parse import urlsplit, parse_qs
from datetime import datetime, timezone
from importlib.metadata import distribution,PackageNotFoundError
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import httpx
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--launch-info',type=Path)
parser.add_argument('--output',type=Path,default=ROOT/'reports/security_review_v2.json')
args=parser.parse_args()
report={"date":datetime.now(timezone.utc).isoformat(),"scope":"Local source/API/dependency review; not penetration testing or certification"}
client=httpx.Client(base_url="http://127.0.0.1:8765",timeout=5,trust_env=False)
probes=[]
for label,method,url,headers,body in [
 ("health_without_auth","GET","/api/health",{},None),
 ("unexpected_host","GET","/api/health",{"Host":"outside.invalid"},None),
 ("remote_origin_post","POST","/api/jobs/sample",{"Origin":"https://outside.invalid"},{"sample_id":"audit-nonexistent"}),
 ("different_local_port_post","POST","/api/jobs/sample",{"Origin":"http://localhost:9999"},{"sample_id":"audit-nonexistent"}),
 ("no_origin_post","POST","/api/jobs/sample",{},{"sample_id":"audit-nonexistent"}),
 ("null_origin_post","POST","/api/jobs/sample",{"Origin":"null"},{"sample_id":"audit-nonexistent"}),
 ("missing_job","GET","/api/jobs/audit-nonexistent",{},None)]:
 try:
  res=client.request(method,url,headers=headers,json=body)
  probes.append({"case":label,"status":res.status_code})
  if label=="health_without_auth":report["response_headers"]={k:res.headers.get(k) for k in ["cache-control","x-content-type-options","referrer-policy","content-security-policy","x-frame-options","access-control-allow-origin"]}
 except Exception as e:probes.append({"case":label,"error":type(e).__name__})
report["api_probes"]=probes
if args.launch_info:
 info=json.loads(args.launch_info.read_text(encoding='utf-8-sig'))
 origin=info['origin']
 credential=parse_qs(urlsplit(info['url']).fragment).get('bootstrap',[''])[0]
 authenticated=httpx.Client(base_url=origin,timeout=5,trust_env=False)
 response=authenticated.post('/api/session',headers={'Origin':origin},json={'credential':credential})
 credential=None
 report['session_bootstrap_status']=response.status_code
 if response.status_code==200:
  checks=[]
  for label,method,url,headers,body in [
   ('authorized_health','GET','/api/health',{},None),
   ('authorized_wrong_port','POST','/api/jobs/sample',{'Origin':'http://127.0.0.1:9999'},{'sample_id':'audit-nonexistent'}),
   ('authorized_remote_origin','POST','/api/jobs/sample',{'Origin':'https://outside.invalid'},{'sample_id':'audit-nonexistent'}),
   ('authorized_without_origin','POST','/api/jobs/sample',{}, {'sample_id':'audit-nonexistent'}),
   ('authorized_valid_origin_missing_sample','POST','/api/jobs/sample',{'Origin':origin},{'sample_id':'audit-nonexistent'})]:
   res=authenticated.request(method,url,headers=headers,json=body)
   checks.append({'case':label,'status':res.status_code})
  report['authenticated_probes']=checks
 authenticated.close()
net=subprocess.run(["netstat","-ano","-p","tcp"],capture_output=True,text=True)
report["listener_lines"]=[line.strip() for line in net.stdout.splitlines() if ":8765 " in line and "LISTENING" in line]
files=list((ROOT/"data/jobs").rglob("*"));files=[p for p in files if p.is_file()]
originals=[p for p in files if p.name.startswith("original.")]
known={hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"data/samples").rglob("*") if p.is_file() and p.suffix in {".mp4",".png"}}
report["retained_jobs"]={"files":len(files),"bytes":sum(p.stat().st_size for p in files),"originals":len(originals),"all_originals_match_bundled_synthetic_samples":all(hashlib.sha256(p.read_bytes()).hexdigest() in known for p in originals)}
roots=["fastapi","uvicorn","python-multipart","rapidocr-onnxruntime","onnxruntime","opencv-python","imageio-ffmpeg","Pillow","numpy"]
todo=roots[:];seen={};missing=[]
while todo:
 name=canonicalize_name(todo.pop())
 if name in seen:continue
 try:d=distribution(name)
 except PackageNotFoundError:missing.append(name);continue
 seen[name]={"name":d.metadata["Name"],"version":d.version}
 for raw in d.requires or []:
  req=Requirement(raw)
  if req.marker and not req.marker.evaluate({"extra":""}):continue
  todo.append(req.name)
packages=sorted(seen.values(),key=lambda x:x["name"].lower())
queries=[{"package":{"ecosystem":"PyPI","name":p["name"]},"version":p["version"]} for p in packages]
report["packages"]=packages;report["missing_packages"]=missing
try:
 pending=list(range(len(queries)));results=[[] for _ in queries]
 while pending:
  req=urllib.request.Request("https://api.osv.dev/v1/querybatch",data=json.dumps({"queries":[queries[i] for i in pending]}).encode(),headers={"Content-Type":"application/json"},method="POST")
  with urllib.request.urlopen(req,timeout=45) as response:batch=json.load(response)
  next_pending=[]
  for i,r in zip(pending,batch["results"]):
   results[i].extend(r.get("vulns",[]))
   if r.get("next_page_token"):
    queries[i]["page_token"]=r["next_page_token"];next_pending.append(i)
  pending=next_pending
 report["osv"]={"status":"completed","database":"https://api.osv.dev/v1/querybatch","queried_package_versions":len(packages),"findings":[{**packages[i],"vulnerabilities":r} for i,r in enumerate(results) if r],"limits":"Python package/version database matching only. Does not cover bundled FFmpeg/OpenCV native library builds, unknown vulnerabilities, code-level authorization issues or network egress."}
except Exception as e:
 report["osv"]={"status":"unavailable","error_type":type(e).__name__,"message":str(e)}
report["source_sha256"]={str(p.relative_to(ROOT)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"app").glob("*.py")}
out=args.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps({k:v for k,v in report.items() if k not in {"packages","source_sha256"}},ensure_ascii=False,indent=2))
