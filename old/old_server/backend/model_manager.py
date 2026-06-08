# backend/model_manager.py
# Bridge between the UI and the AI pipeline.
# Runs training in a background thread so the UI stays responsive.

import threading
from pathlib import Path
from typing  import Callable

from SteganoGAN2.app.database.models_table import (
    create_model as db_create_model,
    get_models_by_user, get_model_by_id,
    delete_model as db_delete_model,
    model_belongs_to_user,
)

# Paths
APP_DIR        = Path(__file__).parent.parent          # SteganoGAN2/app/
_STEGANO_ROOT  = APP_DIR.parent                        # SteganoGAN2/
MODELS_DIR    = _STEGANO_ROOT / "data" / "models"
IMAGES_DIR    = _STEGANO_ROOT / "data" / "images"
CREATIONS_DIR = _STEGANO_ROOT / "data" / "creations"
_CHECKPOINTS  = _STEGANO_ROOT / "stegano2" / "training" / "checkpoints"


def _latest_base_checkpoint() -> Path:
    """
    Return the highest-epoch checkpoint file from the checkpoints folder.
    Only files named 'checkpoint_epoch_NNNN.pt' are considered —
    finetuned.pt and any other file are ignored.
    """
    candidates = sorted(
        _CHECKPOINTS.glob("checkpoint_epoch_*.pt"),
        key=lambda p: int(p.stem.rsplit("_", 1)[-1]),
    )
    if not candidates:
        raise FileNotFoundError(f"No base checkpoints found in {_CHECKPOINTS}")
    return candidates[-1]


# ── Encode / decode ────────────────────────────────────────────────────────────

def encode_with_model(
    model_id:    int,
    image_path:  str,
    message:     str,
    output_path: str,
) -> str:
    """Hide a message in an image using the specified model."""
    from stegano2.pipeline.encoder import encode

    model = get_model_by_id(model_id)
    if model is None:
        raise ValueError(f"Model {model_id} not found")

    encode(
        image_path=      image_path,
        message=          message,
        checkpoint_path=  model["model_path"],
        output_path=      output_path,
    )
    return output_path


def decode_with_model(model_id: int, image_path: str) -> str:
    """Reveal the hidden message from a stego image."""
    from stegano2.pipeline.decoder import decode

    model = get_model_by_id(model_id)
    if model is None:
        raise ValueError(f"Model {model_id} not found")

    return decode(image_path=image_path, checkpoint_path=model["model_path"])


def get_user_models(user_id: int) -> list[dict]:
    """Return all models belonging to a user."""
    return get_models_by_user(user_id)


def delete_model(model_id: int, user_id: int) -> bool:
    """Delete a model — only the owner can do this."""
    if not model_belongs_to_user(model_id, user_id):
        return False
    db_delete_model(model_id)
    return True


# ── Train (async) ──────────────────────────────────────────────────────────────

def train_model_async(
    user_id:     int,
    name:        str,
    description: str,
    image_path:  str,
    on_progress: Callable[[str, int], None],
    on_done:     Callable[[int], None],
    on_error:    Callable[[str], None],
):
    """
    Train a model for a specific image in a background thread.
    Calls on_progress(step_text, percent) during training.
    Calls on_done(model_id) when finished.
    Calls on_error(message) if something fails.
    """
    def run():
        try:
            from stegano2.pipeline.prepare_dataset import prepare_dataset
            from stegano2.training.finetuner import finetune
            from SteganoGAN2.app.database.datasets_table      import get_or_create_dataset
            from SteganoGAN2.app.backend.training_queue       import GPUSlot

            # ── CPU work: no GPU needed, runs immediately ──────────────────────
            user_model_dir = MODELS_DIR / f"user_{user_id}"
            user_model_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(user_model_dir / f"{name}.pt")

            NUM_IMAGES = 100
            NUM_CROPS  = 50
            dataset    = get_or_create_dataset(
                user_id=    user_id,
                image_path= image_path,
                base_dir=   str(user_model_dir),
                num_images= NUM_IMAGES,
            )
            variations_dir = dataset["dir_path"]

            # ── GPU work: wait for a free slot if another job is training ──────
            with GPUSlot(on_queued=lambda: on_progress("Queued — waiting for GPU slot…", 0)):

                on_progress("Generating image variations...", 10)
                prepare_dataset(
                    image_path=     image_path,
                    output_dir=     variations_dir,
                    num_images=     NUM_IMAGES,
                    num_real_crops= NUM_CROPS,
                )

                base = _latest_base_checkpoint()
                on_progress(f"Fine-tuning from {base.name}…", 35)
                finetune(
                    dataset_dir=     variations_dir,
                    base_checkpoint= str(base),
                    output_path=     output_path,
                    target_image=    image_path,
                    on_epoch=lambda ep, total: on_progress(
                        f"Fine-tuning epoch {ep}/{total}…",
                        35 + int(ep / total * 55),
                    ),
                )

            on_progress("Saving to database...", 95)
            model_id = db_create_model(
                user_id=      user_id,
                name=         name,
                description=  description or "",
                image_path=   image_path,
                model_path=   output_path,
            )

            on_progress("Done!", 100)
            on_done(model_id)

        except Exception as ex:
            on_error(str(ex))

    threading.Thread(target=run, daemon=True).start()