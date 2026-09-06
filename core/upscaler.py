"""Optional Real-ESRGAN pre-upscaling of frames before detection.

Note before using this: the detector resizes whatever it is given down to its
own input size (Ultralytics defaults to 640), so upscaling a 720p frame and
then letting the model shrink it again spends seconds per frame on pixels
that are immediately discarded. Raise the detector's imgsz first and measure
before concluding anything about super-resolution.
"""
import os
import urllib.request

import numpy as np

from core.paths import WEIGHTS_DIR, ensure_weights_dir

WEIGHTS_FILE = "realesr-general-x4v3.pth"
WEIGHTS_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
    "realesr-general-x4v3.pth"
)


class RealESRGANUpscaler:
    def __init__(self, scale=2, tile_size=512):
        self._scale = scale
        self._tile_size = tile_size
        self._model = None

    @property
    def name(self) -> str:
        return f"RealESRGAN {self._scale}x"

    def load(self):
        if self._model is not None:
            return

        from realesrgan import RealESRGANer
        from realesrgan.archs.srvgg_arch import SRVGGNetCompact

        ensure_weights_dir()
        model_path = os.path.join(WEIGHTS_DIR, WEIGHTS_FILE)

        if not os.path.exists(model_path):
            print("[Upscaler] Downloading model weights...")
            urllib.request.urlretrieve(WEIGHTS_URL, model_path)
            print("[Upscaler] Download complete.")

        # The checkpoint is a 4x network; outscale in upscale() resamples its
        # output down to the requested scale.
        architecture = SRVGGNetCompact(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_conv=32, upscale=4, act_type="prelu",
        )

        self._model = RealESRGANer(
            scale=4,
            model_path=model_path,
            model=architecture,
            tile=self._tile_size,
            tile_pad=10,
            pre_pad=0,
            half=False,
            device="cpu",
        )

    def upscale(self, frame: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Upscaler not loaded. Call load() first.")

        try:
            output, _ = self._model.enhance(frame, outscale=self._scale)
            return output
        except Exception as e:
            print(f"[Upscaler] Warning: upscale failed, using original frame: {e}")
            return frame
