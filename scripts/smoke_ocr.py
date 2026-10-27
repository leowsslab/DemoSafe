from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json, time, imageio_ffmpeg, subprocess
from rapidocr_onnxruntime import RapidOCR

root=Path(__file__).resolve().parents[1]
out=root/'artifacts'/'smoke'
out.mkdir(parents=True,exist_ok=True)
im=Image.new('RGB',(1000,400),'white')
d=ImageDraw.Draw(im)
f=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',32)
d.text((40,50),'DemoSafe - fictional test data',font=f,fill='black')
d.text((40,130),'Email: alex@example.com',font=f,fill='black')
d.text((40,210),'Phone: 202-555-0142',font=f,fill='black')
im.save(out/'ocr_input.png')
t=time.perf_counter()
ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
result,timing=ocr(str(out/'ocr_input.png'))
report={'backend':'RapidOCR ONNX Runtime CPU','initialization_and_inference_seconds':time.perf_counter()-t,'results':result,'timing':timing}
(out/'ocr_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
ff=imageio_ffmpeg.get_ffmpeg_exe()
print('FFMPEG',ff)
r=subprocess.run([ff,'-hide_banner','-devices'],capture_output=True,text=True)
print(r.stdout)
print(r.stderr)
