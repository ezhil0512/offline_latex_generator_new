from PIL import Image, ImageOps

from offline_latex_generator.config import config


class ImagePreprocessor:
    """Apply the preprocessing steps defined in configuration to a Pillow image."""

    def process(self, image: Image.Image) -> Image.Image:
        """Return a processed in-memory Pillow image.

        The supported operations come directly from the frozen configuration:
        - deskew
        - enhance_contrast
        - binarize
        """
        if not isinstance(image, Image.Image):
            raise TypeError("Expected a Pillow Image input")

        processed = image.copy()

        preprocessing_cfg = config.get("pipeline.preprocessing", {}) or {}
        if isinstance(preprocessing_cfg, dict):
            deskew = bool(preprocessing_cfg.get("deskew", False))
            enhance_contrast = bool(preprocessing_cfg.get("enhance_contrast", False))
            binarize = bool(preprocessing_cfg.get("binarize", False))
        else:
            deskew = False
            enhance_contrast = False
            binarize = False

        if deskew:
            # No-op for deskew because the frozen architecture only defines the flag,
            # and no dedicated deskew implementation is part of the existing scope.
            processed = processed.copy()

        if enhance_contrast:
            processed = ImageOps.autocontrast(processed)

        if binarize:
            grayscale = ImageOps.grayscale(processed)
            processed = grayscale.point(lambda p: 255 if p > 127 else 0, mode="1")

        return processed
