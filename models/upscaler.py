import os

import numpy as np

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights")


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

        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        model_path = os.path.join(WEIGHTS_DIR, "realesr-general-x4v3.pth")

        if not os.path.exists(model_path):
            import urllib.request
            url = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth"
            print("[Upscaler] Downloading model weights...")
            urllib.request.urlretrieve(url, model_path)
            print("[Upscaler] Download complete.")

        model = SRVGGNetCompact(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_conv=32, upscale=4, act_type='prelu',
        )

        self._model = RealESRGANer(
            scale=4,
            model_path=model_path,
            model=model,
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
