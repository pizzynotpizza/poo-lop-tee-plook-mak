# NODE GUIDE — /project1/tree_interaction

ใน Network Editor ทุก COMP ย่อยมีคำอธิบายแบบเดียวกันนี้อยู่แล้ว ได้แก่ Network Box (`box_*`), กล่องสรุปส่วนงาน (`note_section`) และกล่องรายการ Node ทุกตัว (`note_nodes`) ส่วนแต่ละ Node มีข้อความสั้นใน `comment`
ระดับบนสุดมี `note_overview` ซึ่งเป็นภาพรวมเส้นทางข้อมูล และ `box_*` กับ `note_*` ของทั้ง 8 ส่วน เรียงจากซ้ายไปขวา

สีของแต่ละส่วน: controls = เหลือง, tracking_input = น้ำเงิน, tracking_process = เขียวอมฟ้า, growth_controller = ส้ม, tree_assets = เขียว, tree_animation = ม่วง, output = แดง, debug = เทา

## /project1/MediaPipe_Python (แทน MediaPipe แบบเว็บ)

| Node | ชนิด | ทำหน้าที่ | ค่าสำคัญ |
|---|---|---|---|
| process_manager | Text DAT (module, sync `mediapipe_process.py`) | start/stop/restart Python, watchdog, เขียนค่า hand_values และ status | – |
| process_exec | Execute DAT | เริ่ม Python ตอนเปิดโปรเจกต์ ปิดตอนออกจาก TD อัปเดต output ทุกเฟรม และเรียก watchdog ทุก 15 เฟรม | Start / Exit / Frame Start |
| par_exec | Parameter Execute DAT | ปุ่ม Start/Stop/Restart/Openlog และรีสตาร์ตเมื่อเปลี่ยนค่ากล้องหรือพอร์ต | Pars = * |
| hand_udp → hand_callbacks | UDP In DAT → Text DAT (sync `tracking_callbacks.py`) | รับและตรวจ JSON ข้อมูลมือ | Port = Handport 5005 |
| preview_udp → preview_callbacks | UDP In DAT → Text DAT (sync `preview_callbacks.py`) | รับภาพ JPEG แล้วถอดรหัสด้วย OpenCV ของ TD | Port = Previewport 5006 |
| preview_top (+ preview_top_callbacks) | Script TOP | แสดงภาพกล้องล่าสุด | copyNumpyArray |
| status_text → preview_view → preview_out | Text / Over / Null TOP | ภาพกล้องพร้อมสถานะ ใช้เป็น Background ของหน้า Node | Container `top` = preview_out |
| hand_values → hand_null → out_hands | Constant / Null / Out CHOP | ค่ามือในพิกัด TD (y ขึ้น = มาก) ส่งเข้า `/project1/hand_y` | h1/h2:middle_finger_mcp:y, hand_present, palm_x/y, hands, tracking_alive, process_running ... |

## ระดับบน

| Node | ชนิด | หน้าที่ | parameter สำคัญ |
|---|---|---|---|
| tree_interaction | Base COMP | เก็บ Custom Parameters ทั้งหมด (Parent Shortcut = `TI`) | ดู README_TH.md ข้อ 6 |
| frame_tick | Execute DAT | เรียก `animation_controller.tick()` ทุกเฟรมบน main thread หากเกิด error จะ print แค่ครั้งเดียวต่อข้อความ | Frame Start = On |

## 1. controls
| Node | ชนิด | ทำหน้าที่ | รับจาก | ส่งไปที่ | ค่าสำคัญ |
|---|---|---|---|---|---|
| param_handler | Parameter Execute DAT | Reset → `reset()`; Reanalyze / เปลี่ยน Stage path → `analyze_assets()` | Custom Parameters | animation_controller | Pars = Reset Reanalyze Stage1-4path |

## 2. tracking_input
| Node | ชนิด | ทำหน้าที่ | รับจาก | ส่งไปที่ | ค่าสำคัญ |
|---|---|---|---|---|---|
| udp_hand_in | UDP In DAT | รับ JSON ทีละ message | hand_tracker.py | hand_json_callbacks | Port = `parent.TI.par.Udport`, Format = One Per Message, Max Lines = 20 |
| hand_json_callbacks | Text DAT (sync file) | ตรวจ JSON, ค่าตัวเลขต้องเป็นค่าจำกัด (finite), ตรวจลำดับ seq แล้วเก็บ `last_packet` (เวลาจาก time.monotonic) และ `udp_stats` | udp_hand_in | storage → animation_controller | ไฟล์ `tracking_callbacks.py` |

## 3. tracking_process
| Node | ชนิด | ทำหน้าที่ | รับจาก | ส่งไปที่ | ค่าสำคัญ |
|---|---|---|---|---|---|
| hand_coords | Constant CHOP | ค่ามือดิบหลัง mirror และกลับแกน Y เมื่อมือหายจะค้างค่าล่าสุด | animation_controller | hand_raw_out, select_position | hand_present, hand_x, hand_y, hand_scale, tracking_alive, packet_age |
| hand_raw_out | Null CHOP | จุดเชื่อมต่อค่าดิบ | hand_coords | ภายนอก | – |
| select_position | Select CHOP | ส่งเฉพาะตำแหน่งและขนาดไป smooth | hand_coords | hand_smooth | hand_x hand_y hand_scale |
| hand_smooth | Lag CHOP | ทำให้ตำแหน่งเคลื่อนลื่น | select_position | hand_smooth_out | Lag = Positionsmooth (วินาที) จะ reset ทันทีตอนเริ่มจาก IDLE |
| hand_smooth_out | Null CHOP | ตำแหน่งที่ smooth แล้ว | hand_smooth | anchor | – |

## 4. growth_controller
| Node | ชนิด | ทำหน้าที่ | รับจาก | ส่งไปที่ | ค่าสำคัญ |
|---|---|---|---|---|---|
| animation_controller | Text DAT (module, sync file) | state machine, timer, opacity, anchor, mask, debug, analyze_assets | storage, hand_smooth_out, Custom Parameters | hand_coords, growth_state, blend_keys, appear_keys, debug | ไฟล์ `animation_controller.py` |
| growth_state | Constant CHOP | ผลลัพธ์ของ state machine | animation_controller | growth_out | state (0–3), growth, opacity, anchor_x/y, tree_scale, seg, blend_w, reveal, hand_confirmed, time_left, tracking_alive |
| growth_out | Null CHOP | จุดเชื่อมต่อหลัก | growth_state | tree_animation/growth_in | – |

## 5. tree_assets (ทำซ้ำ 4 ชุด N = 01–04)
| Node | ชนิด | ทำหน้าที่ | ค่าสำคัญ |
|---|---|---|---|
| stage_N_in | Movie File In TOP | โหลด PNG | File = `parent.TI.par.StageNpath`, Pre-Multiply = On |
| stage_N_canvas | Transform TOP | จัดภาพลง canvas 1024×1024 โดยวางโคนต้นที่กึ่งกลางล่าง ทุกระยะสูงเท่ากัน และไม่ตัดพุ่มใบ | sx/sy/px/py/tx/ty คำนวณจาก alpha จริง (pivot วัดจากมุมล่างซ้าย) |
| stage_N_out | Null TOP | จุดเชื่อมต่อ | – |
| asset_info | Table DAT | รายงานผลตรวจ: status, png_type (6 = RGBA), alpha_clear, root_x, bottom, height, width, scale | – |

## 6. tree_animation
| Node | ชนิด | ทำหน้าที่ | ค่าสำคัญ |
|---|---|---|---|
| growth_in | Select CHOP | รับ growth_out | Chops = `../growth_controller/growth_out` |
| select_stage_01..04 | Select TOP | ดึงภาพแต่ละระยะ | – |
| stage_switch_a | Switch TOP | ภาพระยะปัจจุบัน (A) | Index = `int(op('growth_in')['seg'])` |
| stage_switch_b | Switch TOP | ภาพระยะถัดไป (B) | Index = `min(3, seg+1)` |
| blend_keys / blend_mask | Table DAT / Ramp TOP | weight map = smoothstep(t) × reveal ล่าง→บน แบบขอบนุ่ม | Vertical, pos 0 = ล่าง |
| stage_blend | Matte TOP | `B*m + A*(1-m)` น้ำหนักรวมเป็น 1 ทุกพิกเซล | Matte Channel = Red |
| appear_keys / appear_mask | Table DAT / Ramp TOP | reveal ตอนต้นไม้ปรากฏ × opacity (rgba เท่ากัน) | Vertical |
| tree_masked | Multiply TOP | คูณ opacity เพียงครั้งเดียว ข้อมูลเป็น premultiplied จึงไม่มีขอบดำ | – |
| sway_noise | Noise CHOP | ลมแบบช้า ๆ | Hermite, Period = 1/Swayspeed, Amp = Swayamount |
| tree_sway | Transform TOP | หมุนรอบโคนต้น ทำให้โคนไม่ขยับ | Pivot = (0.5, 0), Rotate = sway |
| tree_place | Transform TOP | ขยายจากโคนต้นแล้ววางโคนต้นที่ anchor บนภาพขนาด output | sy = Treesize×tree_scale, sx ชดเชย aspect, tx = anchor_x−0.5, ty = anchor_y+Treeoffsety |
| tree_rgba_out | Null TOP | ต้นไม้พื้นโปร่งใส | – |

## 7. output
| Node | ชนิด | ทำหน้าที่ |
|---|---|---|
| select_tree | Select TOP | ดึง tree_rgba_out |
| OUT_TREE_RGBA | Null TOP | ต้นไม้พื้นโปร่งใส |
| background_in → bg_fit | Movie File In → Fit TOP | พื้นหลังแบบ Fit Outside (เต็มจอ ไม่ยืด) |
| final_over | Over TOP | วางต้นไม้ทับพื้นหลัง (Size = Input 2) |
| select_debug → debug_over | Select / Over TOP | วางข้อความ debug ทับภาพ |
| debug_toggle | Switch TOP | Index = Showdebug |
| OUT_FINAL | Null TOP | ภาพแสดงจริง |
| output_window | Window COMP | หน้าต่างแสดงผล (กด Open เอง) |

## 8. debug
| Node | ชนิด | ทำหน้าที่ |
|---|---|---|
| perform | Perform CHOP | FPS |
| debug_info | Table DAT | state, growth, opacity, source, tracking, hand, hand_xy, packets, time_left, td_fps, last_error |
| debug_text → debug_out | Text TOP → Null TOP | ข้อความ overlay พื้นโปร่งใส |
