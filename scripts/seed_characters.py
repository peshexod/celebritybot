import asyncio
import json
from pathlib import Path
import sys

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bot.db.database import SessionLocal
from bot.db.models import Character, CharacterCreative


def _resolve_path(path_value: str, project_root: Path) -> str:
    path = Path(path_value)
    if path.is_absolute():
        return str(path)
    return str((project_root / path).resolve())


async def seed_from_catalog(catalog_path: Path) -> None:
    project_root = catalog_path.parent.parent
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    characters = payload.get("characters", [])

    async with SessionLocal() as session:
        for item in characters:
            name = item["name"].strip()
            existing = await session.scalar(select(Character).where(Character.name == name))

            creatives_payload = item.get("creatives", [])
            preview_source = item.get("preview_image_path")
            if not preview_source and creatives_payload:
                preview_source = creatives_payload[0].get("image_path")
            if not preview_source:
                raise ValueError(f"Character '{name}' must have preview_image_path or at least one creative")

            preview_path = _resolve_path(preview_source, project_root)
            if not Path(preview_path).exists():
                raise FileNotFoundError(f"Preview image not found: {preview_path}")

            if existing:
                character = existing
                character.description = item.get("description", "")
                character.preview_image_path = preview_path
                character.elevenlabs_voice_id = item["elevenlabs_voice_id"]
                character.sort_order = int(item.get("sort_order", 0))
                character.is_active = bool(item.get("is_active", True))
            else:
                character = Character(
                    name=name,
                    description=item.get("description", ""),
                    preview_image_path=preview_path,
                    elevenlabs_voice_id=item["elevenlabs_voice_id"],
                    sort_order=int(item.get("sort_order", 0)),
                    is_active=bool(item.get("is_active", True)),
                )
                session.add(character)
                await session.flush()

            existing_creatives = await session.scalars(
                select(CharacterCreative).where(CharacterCreative.character_id == character.id)
            )
            existing_by_label = {creative.label or "": creative for creative in existing_creatives}

            for creative_item in creatives_payload:
                label = (creative_item.get("label") or "").strip()
                image_path = _resolve_path(creative_item["image_path"], project_root)
                if not Path(image_path).exists():
                    raise FileNotFoundError(f"Creative image not found: {image_path}")

                creative = existing_by_label.get(label)
                if creative:
                    creative.image_path = image_path
                    creative.sort_order = int(creative_item.get("sort_order", 0))
                    creative.is_active = bool(creative_item.get("is_active", True))
                else:
                    session.add(
                        CharacterCreative(
                            character_id=character.id,
                            image_path=image_path,
                            label=label or None,
                            sort_order=int(creative_item.get("sort_order", 0)),
                            is_active=bool(creative_item.get("is_active", True)),
                        )
                    )

        await session.commit()


def main() -> None:
    catalog_path = Path("media/characters/catalog.json").resolve()
    if not catalog_path.exists():
        raise FileNotFoundError(
            "Create media/characters/catalog.json first. "
            "You can copy media/characters/catalog.example.json"
        )
    asyncio.run(seed_from_catalog(catalog_path))
    print("Characters and creatives were synced successfully")


if __name__ == "__main__":
    main()
