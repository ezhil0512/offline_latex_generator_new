import os
from pathlib import Path
from typing import List
from PIL import Image
import pdf2image
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError, PDFInfoNotInstalledError

from offline_latex_generator.cleanup.manager import workspace_manager
from offline_latex_generator.config import config
from offline_latex_generator.utils.logger import logger


class DocumentLoaderError(ValueError):
    """Custom exception raised when document loading fails."""
    pass


class PDFLoader:
    """Loader to convert PDF documents into in-memory Pillow Images."""

    def load_pdf(self, job_id: str, filename: str) -> List[Image.Image]:
        """Converts each page of a PDF file inside the workspace into Pillow Image objects.

        Preserves original page order and does not save the images to disk.
        All temporary files created during conversion are restricted to the job workspace.
        """
        try:
            # Resolve safe workspace file path
            pdf_path = workspace_manager.get_workspace_file_path(job_id, filename)
            workspace_path = pdf_path.parent
        except (ValueError, FileNotFoundError) as e:
            raise DocumentLoaderError(f"Failed to locate file in workspace: {e}") from e

        # Read DPI from config (default 300)
        dpi = int(config.get("pipeline.target_dpi", 300))

        try:
            logger.info(f"Loading PDF {filename} for job {job_id} at {dpi} DPI")
            # Specify output_folder as workspace_path so pdf2image temp files stay in workspace
            images = pdf2image.convert_from_path(
                str(pdf_path),
                dpi=dpi,
                output_folder=str(workspace_path)
            )
            
            loaded_images = []
            for img in images:
                # Force loading pixels into memory
                img.load()
                # Create independent copy
                loaded_images.append(img.copy())
                # Close original image to release file lock on the temp PPM file on Windows
                img.close()

            # Clean up temporary PPM files created by pdf2image in the workspace
            for temp_file in workspace_path.glob("*.ppm"):
                try:
                    temp_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temporary PPM file {temp_file}: {e}")

            return loaded_images
        except (PDFPageCountError, PDFSyntaxError, PDFInfoNotInstalledError) as e:
            logger.error(f"Failed to convert PDF {filename} for job {job_id}: {e}")
            raise DocumentLoaderError(f"Failed to process PDF file: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error while loading PDF {filename} for job {job_id}: {e}")
            raise DocumentLoaderError(f"Unexpected error during PDF load: {e}") from e


class ImageLoader:
    """Loader to load image files into in-memory Pillow Images."""

    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

    def load_image(self, job_id: str, filename: str) -> Image.Image:
        """Loads a supported image file from the workspace into a Pillow Image object.

        Loads the image exactly as stored on disk without modifying its pixel data
        or color mode.
        """
        try:
            # Resolve safe workspace file path
            image_path = workspace_manager.get_workspace_file_path(job_id, filename)
        except (ValueError, FileNotFoundError) as e:
            raise DocumentLoaderError(f"Failed to locate file in workspace: {e}") from e

        # Validate extension
        suffix = image_path.suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise DocumentLoaderError(f"Unsupported image format: '{suffix}'")

        try:
            logger.info(f"Loading image {filename} for job {job_id}")
            # Open the image and force loading pixels into memory to close the file handle safely
            with Image.open(image_path) as img:
                img.load()
                # Return a copy to ensure it remains fully loaded in memory after the file handle is closed
                return img.copy()
        except Exception as e:
            logger.error(f"Failed to load image {filename} for job {job_id}: {e}")
            raise DocumentLoaderError(f"Failed to load image file: {e}") from e
