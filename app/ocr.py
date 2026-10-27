import threading
import numpy as np


class OCRModel:
    backend = "CPU · ONNX Runtime"
    model = "RapidOCR 1.4.4 / PP-OCRv4 detection + recognition"
    hardware_verified = False

    def __init__(self):
        self._engine = None
        self._lock = threading.RLock()

    @property
    def loaded(self):
        return self._engine is not None

    def recognize(self, frame: np.ndarray) -> list[dict]:
        """Input is BGR uint8 pixels; output coordinates stay in source pixels."""
        with self._lock:
            if self._engine is None:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR(det_use_cuda=False, cls_use_cuda=False, rec_use_cuda=False,
                                        det_limit_side_len=1280, det_limit_type="max", rec_batch_num=16,
                                        intra_op_num_threads=2, inter_op_num_threads=1)
            result, _ = self._engine(frame, use_cls=False)
        lines = []
        height, width = frame.shape[:2]
        for polygon, value, confidence in result or []:
            points = np.asarray(polygon)
            box = [max(0, int(np.floor(points[:, 0].min())) - 3),
                   max(0, int(np.floor(points[:, 1].min())) - 3),
                   min(width, int(np.ceil(points[:, 0].max())) + 4),
                   min(height, int(np.ceil(points[:, 1].max())) + 4)]
            lines.append({"text": str(value), "confidence": float(confidence), "box": box})
        return lines


class HailoOCRAdapter:
    """Explicit future integration point. This is not an implemented HEF backend."""
    backend = "UGen300 / Hailo-10H (unavailable)"
    hardware_verified = False

    def recognize(self, frame):
        raise RuntimeError("UGen300 integration is not implemented or hardware-verified. Select CPU explicitly.")


OCR = OCRModel()
