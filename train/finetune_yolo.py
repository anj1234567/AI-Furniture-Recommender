"""
Fine-tune YOLOv8 on HomeObjects-3K (bed, sofa, chair, table, lamp, tv, ... ).
Run this on a machine with a GPU (Google Colab's free GPU is fine):

    pip install ultralytics
    python finetune_yolo.py

The dataset (about 390 MB) downloads automatically. Training takes roughly
30-60 minutes on a Colab T4. The result is saved to
runs/detect/homeobjects/weights/best.pt

Then in backend/perception/interface.py:
  1. set YOLO_MODEL to the path of best.pt
  2. update FURNITURE_CLASSES to the class names printed by this script
     (and DETECTION_TO_CATEGORY in recommender/interface.py to match).
NOT yet run or tested by me. Check the class names it prints before editing.
"""
from ultralytics import YOLO

model = YOLO("yolov8n.pt")                      # start from the COCO-pretrained weights
model.train(data="HomeObjects-3K.yaml", epochs=50, imgsz=640, batch=16, name="homeobjects")
metrics = model.val()
print("mAP50:", metrics.box.map50, " mAP50-95:", metrics.box.map)
print("Classes:", model.names)
