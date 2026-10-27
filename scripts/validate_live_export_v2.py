"""Read-only verification of a completed fictional UI export. Never prints credentials."""
from __future__ import annotations
import argparse, hashlib, json, platform, subprocess, sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import cv2, httpx, imageio_ffmpeg, numpy as np

ROOT=Path(__file__).resolve().parents[1]
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--launch-info",type=Path,required=True)
    p.add_argument("--job-id",required=True)
    p.add_argument("--manual-box",nargs=4,type=int,required=True)
    args=p.parse_args()
    assert len(args.job_id)==32 and all(c in "0123456789abcdef" for c in args.job_id)
    info=json.loads(args.launch_info.read_text(encoding="utf-8-sig"))
    origin=info["origin"]
    token=parse_qs(urlsplit(info["url"]).fragment)["bootstrap"][0]
    client=httpx.Client(base_url=origin,trust_env=False,timeout=20)
    auth=client.post("/api/session",headers={"Origin":origin},json={"credential":token})
    token=None
    auth.raise_for_status()
    path=f"/api/jobs/{args.job_id}"
    job=client.get(path).json()
    assert job["status"]=="done" and not job["worker_active"]
    report=client.get(path+"/report").json()
    sample=ROOT/"data/samples/demo_workspace.mp4"
    expected=digest(sample)
    original=client.get(path+"/media/original");original.raise_for_status()
    assert hashlib.sha256(original.content).hexdigest()==expected
    export=client.get(path+"/media/redacted");export.raise_for_status()
    destination=ROOT/"artifacts/film-v2/verified-ui-export.mp4"
    destination.write_bytes(export.content)
    forbidden=[e["text"] for e in json.loads((ROOT/"data/benchmark_truth/demo_workspace.json").read_text(encoding="utf-8"))["events"]]
    serialized=json.dumps(job)+json.dumps(report)
    assert all(text not in serialized for text in forbidden)
    unauth=httpx.Client(base_url=origin,trust_env=False,timeout=5)
    denied={kind:unauth.get(path+suffix).status_code for kind,suffix in [("job",""),("report","/report"),("original","/media/original"),("redacted","/media/redacted")]}
    assert all(value==401 for value in denied.values())
    cap=cv2.VideoCapture(str(destination))
    width,height,fps=(cap.get(prop) for prop in [cv2.CAP_PROP_FRAME_WIDTH,cv2.CAP_PROP_FRAME_HEIGHT,cv2.CAP_PROP_FPS])
    count,covered=0,0
    x1,y1,x2,y2=args.manual_box
    while True:
        ok,frame=cap.read()
        if not ok:break
        covered+=int(np.mean(np.all(frame[y1:y2,x1:x2]<=16,axis=2))>=.995)
        count+=1
    cap.release()
    assert (width,height,fps,count)==(1280,720,10,120)
    assert covered==120
    probe=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-hide_banner","-i",str(destination)],capture_output=True,text=True,errors="replace")
    assert "Audio:" not in probe.stderr and "Video: h264" in probe.stderr
    result={"scope":"Completed real-browser fictional hero flow; read-only API/pixel verification",
            "python":platform.python_version(),"job_id":args.job_id,"backend":job.get("backend"),
            "status":job["status"],"worker_active":job["worker_active"],
            "analysis":report["analysis"],"export_seconds":report["export_seconds"],
            "decisions":report["decisions"],"manual_mask_count":report["manual_mask_count"],
            "manual_mask_box":args.manual_box,"manual_mask_covered_frames":covered,
            "output":{"width":width,"height":height,"fps":fps,"decoded_frames":count,"audio_tracks":0,"sha256":digest(destination)},
            "source_sha256":expected,"original_unchanged":True,"public_api_and_report_omit_detected_plaintext":True,
            "unauthenticated_statuses":denied,"rescan":report["rescan"],
            "limits":"One fictional sample. Same-model rescan is not a privacy guarantee; manual mask verification is separate from automatic recall."}
    (ROOT/"reports/validation_ui_export_v2.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"artifacts/film-v2/ui-export-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()

