from __future__ import annotations

from revenueos.config import Settings
from revenueos.visual_storage import (
    VisualGrantSigner,
    VisualObjectMissingError,
    VisualStorage,
    VisualStorageError,
    create_visual_storage,
)

# WO-014 introduced the first private object-storage adapter. Recording reuses that
# exact security boundary; these aliases avoid a second storage implementation while
# preserving the existing visual module's public names.
PrivateObjectStorage = VisualStorage
PrivateObjectStorageError = VisualStorageError
PrivateObjectMissingError = VisualObjectMissingError
PrivateObjectGrantSigner = VisualGrantSigner


def create_recording_storage(settings: Settings) -> PrivateObjectStorage:
    return create_visual_storage(settings)
