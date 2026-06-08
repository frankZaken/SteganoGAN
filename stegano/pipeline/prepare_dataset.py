# pipeline/prepare_dataset.py

import torch
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

SD_BATCH_SIZE = 4   # images generated per SD call; reduce to 1 if VRAM is tight


# ── Step 1: Caption the image with BLIP ───────────────────────────────────────

def caption_image(image: Image.Image) -> str:
    """
    Use BLIP to automatically generate a text description of the image.
    This description guides Stable Diffusion when generating variations.

    Example old_testing_output: "a young man with glasses smiling at the camera"
    """
    from transformers import BlipProcessor, BlipForConditionalGeneration

    print("  Loading BLIP captioning model...")
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained(
        "Salesforce/blip-image-captioning-base"
    )

    inputs = processor(image, return_tensors="pt")
    output = model.generate(**inputs, max_new_tokens=50)
    caption = processor.decode(output[0], skip_special_tokens=True)

    print(f"  Caption: '{caption}'")
    return caption


# ── Step 2: Resize image for Stable Diffusion ─────────────────────────────────

def prepare_image_for_sd(image: Image.Image, size: int = 512) -> Image.Image:
    """
    Resize so the SHORT side = size, keeping the original aspect ratio.
    No cropping — SD will process the full portrait/landscape image.
    """
    w, h   = image.size
    scale  = size / min(w, h)
    new_w  = int(w * scale)
    new_h  = int(h * scale)

    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)

# ── Step 3: Generate a batch of variations with Stable Diffusion ──────────────

def generate_variation_batch(
    pipe:     object,          # the loaded SD pipeline
    image:    Image.Image,     # the source image (already resized)
    prompt:   str,             # text description of the image
    batch_n:  int   = 1,       # how many images to generate in one call
    strength: float = 0.35,   # how much to change (0=same, 1=ignore original)
    guidance: float = 7.5,    # how closely to follow the prompt
) -> list[Image.Image]:
    """
    Generate batch_n variations in a single SD inference pass.
    Batching amortises the fixed per-call overhead across multiple outputs.
    Reduce SD_BATCH_SIZE at the top of this file if VRAM is tight.
    """
    result = pipe(
        prompt=              [prompt] * batch_n,
        image=               [image]  * batch_n,
        strength=            strength,
        guidance_scale=      guidance,
        num_inference_steps= 30,
    )
    return result.images


# ── Step 4: Load the Stable Diffusion pipeline ────────────────────────────────

def load_sd_pipeline(device: torch.device):
    """
    Load the Stable Diffusion img2img pipeline.
    Downloads the model on first run (~4GB).
    """
    from diffusers import StableDiffusionImg2ImgPipeline

    print("  Loading Stable Diffusion img2img pipeline...")
    print("  (this may take a few minutes on first run — downloads ~4GB)")

    pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
        safety_checker=None,
    ).to(device)

    # speed up inference
    pipe.enable_attention_slicing()

    return pipe


# ── Step 5: Crop the real target image ────────────────────────────────────────

def extract_real_crops(
    image:     Image.Image,
    output_dir: Path,
    num_crops:  int = 50,
    crop_size:  int = 512,
):
    """
    Extract random crops from the real target image.
    Each crop is saved as-is and horizontally flipped, giving 2× the images.
    These anchor the fine-tuned model to the actual pixel statistics of the
    target image, complementing the SD-generated style variations.
    """
    import random

    w, h = image.size
    if w < crop_size or h < crop_size:
        print(f"  Image too small for {crop_size}×{crop_size} crops — skipping")
        return

    existing = len(list(output_dir.glob("crop_*.jpg")))
    already_done = existing // 2
    if already_done >= num_crops:
        print(f"  Real crops: {existing} already exist, skipping")
        return

    print(f"\n  Extracting {num_crops} real crops from original image...")

    for i in tqdm(range(already_done, num_crops), desc="Cropping"):
        x = random.randint(0, w - crop_size)
        y = random.randint(0, h - crop_size)
        crop = image.crop((x, y, x + crop_size, y + crop_size))
        crop.save(output_dir / f"crop_{i+1:04d}a.jpg", quality=95)
        crop.transpose(Image.FLIP_LEFT_RIGHT).save(
            output_dir / f"crop_{i+1:04d}b.jpg", quality=95
        )

    print(f"  ✓ {num_crops * 2} real crops saved")


# ── Step 6: Generate the full dataset ─────────────────────────────────────────

def prepare_dataset(
    image_path:    str,
    output_dir:    str,
    num_images:    int   = 200,
    num_real_crops: int  = 50,
    sd_size:       int   = 512,
    strength_min:  float = 0.25,
    strength_max:  float = 0.45,
):
    """
    Generate a mixed dataset for fine-tuning:
      - SD img2img variations  → style diversity, uses external BLIP + diffusers APIs
      - Crops of the real image → exact pixel statistics of the target image

    Args:
        image_path:     path to the target image
        output_dir:     where to save all generated images
        num_images:     number of SD variations to generate
        num_real_crops: number of real crops to extract (each is saved + flipped = 2×)
        sd_size:        Stable Diffusion input resolution
        strength_min:   minimum img2img variation strength
        strength_max:   maximum img2img variation strength
    """
    import random

    device = torch.device(
        "cuda" if torch.cuda.is_available() else
        "mps"  if torch.backends.mps.is_available() else
        "cpu"
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nPreparing dataset")
    print(f"  Source image : {image_path}")
    print(f"  Output dir   : {out_dir}")
    print(f"  SD variations: {num_images}  |  Real crops: {num_real_crops}×2")
    print(f"  Device       : {device}")

    original = Image.open(image_path).convert("RGB")
    print(f"  Image size   : {original.size[0]}×{original.size[1]}")

    # Step 1: caption
    caption = caption_image(original)

    # Step 2: resize for SD
    sd_image = prepare_image_for_sd(original, size=sd_size)

    # Step 3: load SD pipeline
    pipe = load_sd_pipeline(device)

    # Step 4: generate SD variations (resume-safe — count only variation files)
    print(f"\n  Generating {num_images} variations...")
    existing_variations = len(list(out_dir.glob("variation_*.jpg")))

    pbar = tqdm(range(existing_variations, num_images, SD_BATCH_SIZE), desc="Generating")

    if existing_variations > 0:
        print(f"  Resuming from {existing_variations} existing variations")

    for i in pbar:
        current_batch_size = min(SD_BATCH_SIZE, num_images - i)
        strength = random.uniform(strength_min, strength_max)

        variations = generate_variation_batch(
            pipe=pipe,
            image=sd_image,
            prompt=caption,
            batch_n=current_batch_size,
            strength=strength,
        )

        for j, variation in enumerate(variations):
            variation.save(out_dir / f"variation_{i + j + 1:04d}.jpg", quality=95)

    # Step 5: real crops from the original image
    if num_real_crops > 0:
        extract_real_crops(original, out_dir, num_crops=num_real_crops, crop_size=sd_size)

    total = len(list(out_dir.glob("*.jpg")))
    print(f"\n✓ Dataset ready: {total} images in {out_dir}")


# ── Run ────────────────────────────────────────────────────────────────────────

def main():
    base = Path(__file__).parent.parent   # SteganoGAN2/

    prepare_dataset(
        image_path=     str(base / "input" / "photo.jpg"),
        output_dir=     str(base / "input" / "variations"),
        num_images=     200,
        num_real_crops= 50,
        sd_size=        512,
    )


if __name__ == "__main__":
    main()