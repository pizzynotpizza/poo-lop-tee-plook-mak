# Tree Hand Tracking — MediaPipe (Python) → TouchDesigner

ต้นไม้ 2D ที่ “เติบโต” เหนือฝ่ามือ ตรวจจับมือด้วย MediaPipe ใน Python ภายนอก แล้วส่งตำแหน่งเข้า TouchDesigner ผ่าน UDP

## 1. Environment ที่ตรวจแล้วบนเครื่องนี้ (2026-10-18)

| รายการ | ค่า |
|---|---|
| OS | Windows 11 Home (TouchDesigner รายงานว่า Windows 10) |
| TouchDesigner | 099 build 2025.33230 (Non-Commercial: จำกัดภาพไม่เกิน 1280×1280) |
| Python ใน TouchDesigner | 3.11.15 |
| Python ที่ใช้สร้าง venv | 3.11.15 ตัวเดียวกัน (`C:\Program Files\Derivative\TouchDesigner\bin\python.exe`) |
| venv | `%USERPROFILE%\.venvs\tree_hand_tracking` |
| MediaPipe / OpenCV / NumPy | 1.1.1 / 5.0.0.93 / 2.4.6 |
| กล้อง | ACER HD User Facing (index 0) ได้ประมาณ 15 FPS ทั้งที่ 1280×720 และ 640×480 |

ทำไมไม่ `pip install mediapipe` เข้า TouchDesigner โดยตรง: MediaPipe/OpenCV มี DLL และ numpy เวอร์ชันของตัวเอง ซึ่งชนกับไลบรารีที่ TouchDesigner โหลดอยู่ได้ และการประมวลผลภาพจะไปถ่วง main thread ของ TD การแยกเป็นโปรเซสภายนอกจึงปลอดภัยกว่า

เครื่องนี้ไม่มี Python ติดตั้งแยก (`python` ใน PATH เป็นแค่ตัวเรียก Microsoft Store) จึงสร้าง venv จาก Python ที่มากับ TouchDesigner ซึ่งใช้งานได้

## 2. สถาปัตยกรรม

```
hand_tracker.py (โปรเซสภายนอก)
  OpenCV Webcam → MediaPipe Hand Landmarker (Tasks API, VIDEO mode)
  → เลือกมือหลักด้วยความต่อเนื่องของตำแหน่ง
  → JSON ผ่าน UDP 127.0.0.1:5005 (ส่งทุกเฟรมเป็น heartbeat แม้ไม่มีมือ)
        │
TouchDesigner  /project1/tree_interaction
  tracking_input    udp_hand_in (UDP In DAT) → hand_json_callbacks (ตรวจ JSON, เก็บ packet ล่าสุด)
  frame_tick        Execute DAT เรียก animation_controller.tick() ทุกเฟรม บน main thread
  tracking_process  hand_coords → Lag CHOP → hand_smooth_out
  growth_controller state machine → growth_out (growth, opacity, anchor ...)
  tree_assets       PNG 4 ระยะ → จัดลง canvas 1024×1024 (โคนต้นกึ่งกลางล่าง)
  tree_animation    crossfade 2 ระยะ + reveal mask + sway + วางตาม anchor
  output            OUT_TREE_RGBA (โปร่งใส), OUT_FINAL (มีพื้นหลัง), output_window
  debug             สถานะทั้งหมดบนจอ
```

### นโยบายพิกัด (กันการกลับซ้ายขวาซ้ำ)
- Python ส่งพิกัด **ดิบจากกล้อง ไม่ mirror**: `palm_x`, `palm_y` อยู่ในช่วง 0–1 โดยจุดกำเนิดอยู่มุมบนซ้าย
- TouchDesigner เป็นที่เดียวที่ mirror: `hand_x = 1 - palm_x` เมื่อ `Mirrorx = On` (ค่าเริ่มต้น เหมือนส่องกระจก)
- แกน Y: `hand_y = 1 - palm_y` เพราะใน TD ค่า 0 อยู่ล่าง 1 อยู่บน
- หน้าต่าง preview ของ OpenCV flip ภาพเพื่อการแสดงผลเท่านั้น ไม่กระทบข้อมูลที่ส่ง

### ข้อมูลใน packet
```json
{"seq": 120, "t": 4.02, "hand_present": true, "hand_id": 0, "hands": 1,
 "palm_x": 0.52, "palm_y": 0.41, "hand_scale": 0.18,
 "handedness": "Right", "handedness_score": 0.97, "mirrored": false, "fps": 15.1}
```
- `palm_x/palm_y` = ค่าเฉลี่ยของ landmark 0, 5, 9, 13, 17
- `hand_scale` = ระยะระหว่าง landmark 5 กับ 17 ในพิกัด normalized (ใช้ประมาณขนาดในภาพ ไม่ใช่เมตร)
- `handedness` = ซ้าย/ขวาจริงของมือ: MediaPipe สมมติว่าภาพที่รับเป็นภาพกระจก แต่เราส่งภาพดิบเข้าไป จึงสลับ label ให้
- `handedness_score` = คะแนนความมั่นใจของ **การจำแนกซ้าย/ขวา** ไม่ใช่ความมั่นใจว่าตรวจพบมือ
  การกรองว่าพบมือหรือไม่ใช้ `--min-detection`, `--min-presence`, `--min-tracking` ของ HandLandmarker (Tasks API ไม่ได้ให้คะแนน detection ต่อมือออกมา)
- เมื่อปิดโปรแกรม Python จะส่ง `"shutdown": true` หนึ่งครั้ง ถ้าโปรแกรมค้างหรือถูก kill TD จะรู้เองจาก `Trackingtimeout`

## 3. ติดตั้ง (ทำแล้วบนเครื่องนี้ ใช้ซ้ำเมื่อย้ายเครื่อง)

```bash
"C:\Program Files\Derivative\TouchDesigner\bin\python.exe" -m venv "%USERPROFILE%\.venvs\tree_hand_tracking"
```
```bash
"%USERPROFILE%\.venvs\tree_hand_tracking\Scripts\python.exe" -m pip install -r project\python\requirements.txt
```
โมเดล (ประมาณ 7.8 MB) อยู่ที่ `project/models/hand_landmarker.task` แล้ว ถ้าหายให้ดาวน์โหลดใหม่จาก
`https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task`

> หมายเหตุ: native loader ของ MediaPipe เปิดไฟล์ใน path ที่มีอักษรไทยไม่ได้ (เช่น `งานTouchDesign`) โค้ดจึงอ่านไฟล์โมเดลเป็น bytes เองแล้วส่งเข้าไป

## 4. วิธีรัน

### แบบหลัก: ทุกอย่างอยู่ใน TouchDesigner (`/project1/MediaPipe_Python`)
`MediaPipe_Python` วางอยู่ตำแหน่งเดียวกับ MediaPipe แบบเว็บเดิม
- เปิดโปรเจกต์แล้ว Python จะเริ่มทำงานเอง (เมื่อ `Active = On`) ไม่ต้องรัน .bat และเมื่อปิด TD ก็จะปิด Python ให้ด้วย
- หน้า Node แสดงภาพกล้องแบบกระจก มีเส้นโครงมือ (มือหลักเป็นสีเขียว มืออื่นเป็นสีส้ม) และบรรทัดสถานะ `RUNNING / STOPPED`, fps, จำนวนมือ, error
- หน้า parameter **MediaPipe** มีปุ่ม Start / Stop / Restart / Openlog และค่า Camera, Max Hands, Min Detection, Mirror X, Show Camera Preview
- ถ้า Python หยุดทำงานเอง (crash) จะเริ่มใหม่อัตโนมัติทุก 3 วินาทีตราบที่ Active = On ดูสาเหตุได้ที่ `project/python/tracker_log.txt`
- ช่องออก `out_hands` ต่อเข้า `hand_y` ของ network เดิม ทำให้ `switch1 → null1` ทำงานเหมือนตอนใช้แบบเว็บ (ยกมือสูงขึ้น ต้นไม้ก็โตขึ้น)
- `tree_interaction` อ่านข้อมูลจาก COMP นี้ผ่าน parameter `Trackingsource` (โตตามเวลา 12 วินาที ตามที่ระบุใน Code.txt) ผลอยู่ที่ `tree_interaction/output/OUT_FINAL`

สร้าง `MediaPipe_Python` ใหม่ได้จาก Textport:
```python
exec(open(project.folder + '/project/touchdesigner/build_mediapipe_python.py', encoding='utf-8').read())
```

### แบบสำรอง: รัน tracker เองนอก TD
ต้องตั้ง `MediaPipe_Python` เป็น `Active = Off` ก่อน (กล้องเปิดได้ทีละโปรเซส)
1. เปิด `Tree Hand Tracking.2.toe`
2. รัน tracker: ดับเบิลคลิก `project/python/run_tracker.bat` หรือ
```bash
"%USERPROFILE%\.venvs\tree_hand_tracking\Scripts\python.exe" project\python\hand_tracker.py --camera 0 --port 5005
```
3. ยื่นมือเข้ากล้อง ต้นไม้จะปรากฏเหนือฝ่ามือแล้วโตครบใน 12 วินาที
4. กด `q` หรือ `Esc` ที่หน้าต่าง preview เพื่อหยุด

ตัวเลือกที่ใช้บ่อย: `--no-preview`, `--camera 1`, `--list-cameras`, `--duration 30`, `--num-hands 1`

ทดสอบโดยไม่ใช้กล้อง:
- ใน TD: `tree_interaction` → หน้า Testing → `Testmode = On` แล้วเปิด/ปิด `Testhandpresent`
- ทดสอบเส้นทาง UDP: `python project/python/fake_hand_sender.py` (ใช้ Python ตัวไหนก็ได้ ไม่ต้องลง MediaPipe)

## 5. สร้าง Network ใหม่ (build_network.py)

ใน Textport ของ TouchDesigner (Alt+T):
```python
exec(open(project.folder + '/project/touchdesigner/build_network.py', encoding='utf-8').read())
```
- สร้างเฉพาะ `/project1/tree_interaction` ไม่แตะ node อื่น
- ถ้ามีชื่อนี้อยู่แล้ว จะสร้างเป็น `tree_interaction1`, `2` ... แทน ถ้าต้องการเขียนทับจริง ให้เรียก `build(overwrite=True)` หลังรันคำสั่งด้านบน
- `animation_controller` และ `hand_json_callbacks` sync กับไฟล์ `.py` ในโฟลเดอร์ `project/touchdesigner/` แก้ไฟล์แล้ว TD โหลดใหม่เอง

## 6. Custom Parameters (บน `tree_interaction`)

| หน้า | Parameter | ค่าเริ่มต้น | ความหมาย |
|---|---|---|---|
| Tracking | Udport | 5005 | พอร์ต UDP |
| | Trackingtimeout | 1.0 s | ไม่มี packet นานเกินนี้ = การติดตามขาด |
| | Detectionhold | 0.2 s | ต้องเห็นมือต่อเนื่องเท่านี้ก่อนเริ่ม |
| | Lostgrace | 0.5 s | มือหลุดสั้นกว่านี้ไม่นับว่าหาย (จำกัดไม่ให้เกิน Disappearduration − 0.05) |
| | Mirrorx | On | mirror แกน X (จุดเดียวของระบบ) |
| | Positionsmooth | 0.15 s | ค่า Lag ของตำแหน่งมือ |
| Animation | Growduration | 12 s | เวลาโตจากระยะ 1 ถึง 4 |
| | Disappearduration | 40 s | ต้นไม้ต้องหายสนิทภายในเวลานี้ นับจากข้อมูลมือครั้งล่าสุด (รวม Lostgrace) |
| | Returnfadetime | 0.8 s | เวลา fade-in ตอนปรากฏ และตอนมือกลับมาระหว่างกำลังหาย |
| | Treesize | 0.75 | ความสูง canvas ของต้นไม้ เทียบกับความสูงจอ |
| | Treeoffsety | 0.02 | ระยะโคนต้นเหนือฝ่ามือ (สัดส่วนความสูงจอ) |
| | Swayamount | 1.5° | ความแรงการโยก |
| | Swayspeed | 0.25 | ความเร็วการโยก (period = 1/ค่านี้ วินาที) |
| | Stagescales | 0.5 0.68 0.85 1.0 | ขนาดของระยะ 1–4 เทียบกับระยะโตเต็มที่ |
| Assets | Stage1path..Stage4path | project/assets/tree_stage_0N.png | ภาพ 4 ระยะ |
| | Backgroundpath | project/assets/background.jpg | พื้นหลัง |
| | Reanalyze | (ปุ่ม) | ตรวจ alpha และจัด canvas ใหม่ |
| Output | Outputwidth / Outputheight | 1280 / 720 | ขนาดภาพออก |
| | Showdebug | On | แสดงข้อความ debug บน OUT_FINAL |
| Testing | Testmode, Testhandpresent, Testhandx, Testhandy | Off, Off, 0.5, 0.25 | จำลองมือ (Testhandx/y เป็นพิกัด TD: 0 = ซ้าย/ล่าง) |
| | Reset | (ปุ่ม) | กลับไป IDLE, growth = 0 |

## 7. พฤติกรรมของ state machine

- **IDLE** → เห็นมือต่อเนื่อง ≥ Detectionhold → **GROWING** (ต้นไม้ปรากฏที่ฝ่ามือ, fade-in, reveal จากล่างขึ้นบน)
- **GROWING** → growth ถึง 1 → **MATURE**
- มือหลุดสั้นกว่า Lostgrace: โตต่อ ตำแหน่งค้างไว้
- มือหายเกิน Lostgrace → **DISAPPEARING**: หยุดโต, ล็อกตำแหน่ง, ลด opacity และหดลง 8% แบบนุ่มนวล จนหายสนิทที่เวลา `last_seen + Disappearduration` แล้ว reset เป็น **IDLE**
- มือกลับมาระหว่าง DISAPPEARING: fade กลับขึ้นจากค่า opacity ปัจจุบัน, โตต่อจาก growth เดิม, anchor ค่อย ๆ เคลื่อนจากตำแหน่งที่ล็อกไว้ไปหามือภายใน Returnfadetime
- มือกลับมาหลังหายสนิท: เริ่มจากระยะ 1 ใหม่

การเติบโตใช้ภาพ 2D แบบ crossfade + reveal ซึ่งเป็น**ภาพลวงตา** ไม่ใช่การ morph กิ่งไม้หรือสร้าง geometry ต้นไม้จริง

## 8. การเปลี่ยนแปลงในงานเดิม

- `MediaPipe` (แบบเว็บ) และ `hand_tracking` ถูกย้ายลงไปด้านล่าง **ปิด Allow Cooking** และตั้ง `webrender1` เป็น Active = Off โดยไม่ได้ลบ วิธีกู้คืนเขียนไว้ในกล่อง `note_old_mediapipe`
- `hand_y` เปลี่ยนจากรับข้อมูลของ `hand_tracking` มารับจาก `MediaPipe_Python/out_hands` แทน ชื่อช่อง `h1:middle_finger_mcp:y` และ `h2:middle_finger_mcp:y` ยังเหมือนเดิม ส่วน node อื่นใน chain เดิมไม่ได้แก้
- ภาพถูก**คัดลอก** (ไม่ได้ย้าย) ไปเป็น `project/assets/tree_stage_01..04.png` และ `background.jpg`

## 9. ปัญหาที่พบบ่อย

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| debug แสดง `tracking NO DATA` | ยังไม่ได้รัน hand_tracker.py, พอร์ตไม่ตรงกับ Udport หรือ Firewall บล็อก (localhost ปกติไม่โดน) |
| FPS ต่ำมาก (~1) | มีโปรแกรมอื่นจับกล้องอยู่ เช่น webrender1 เดิม, Video Device In TOP, Zoom, Teams |
| กล้องได้แค่ ~15 FPS | กล้องโน้ตบุ๊กลด FPS เองเมื่อแสงน้อย ลองเพิ่มแสง |
| `Unable to open file ... hand_landmarker.task` | path มีอักษรไทย ใช้โค้ดเวอร์ชันนี้ซึ่งอ่านเป็น bytes แล้ว หรือไฟล์โมเดลหาย |
| ซ้ายขวากลับ | ปรับ Mirrorx อย่างเดียว อย่า flip ภาพใน Python |
| ต้นไม้สลับไปอีกมือ | ปรับ `--max-jump` / `--reacquire` หรือใช้ `--num-hands 1` |
| ภาพต้นไม้หาย / ขอบแปลก | ดู `tree_assets/asset_info` ว่า status = OK และ png_type = 6 (RGBA) |
| `Resolution limited to max 1280x1280` | ข้อจำกัดของ license Non-Commercial ไม่กระทบการทำงาน |
