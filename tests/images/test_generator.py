# tests/images/test_generator.py
import base64
from unittest.mock import MagicMock

import pytest

from images.generator import ImageGenerationError, generate_background_image


def _make_fake_client(b64_data: "str | None"):
    fake_image = MagicMock()
    fake_image.b64_json = b64_data
    fake_response = MagicMock()
    fake_response.data = [fake_image] if b64_data is not None else []
    fake_client = MagicMock()
    fake_client.images.generate.return_value = fake_response
    return fake_client


def test_generate_background_image_returns_decoded_bytes():
    original_bytes = b"fake png bytes"
    b64_data = base64.b64encode(original_bytes).decode("ascii")
    fake_client = _make_fake_client(b64_data)

    image_bytes = generate_background_image("cozy living room at dusk", client=fake_client)

    assert image_bytes == original_bytes
    call_kwargs = fake_client.images.generate.call_args.kwargs
    assert call_kwargs["prompt"].startswith("cozy living room at dusk, ")
    assert "no text" in call_kwargs["prompt"]
    assert call_kwargs["model"] == "black-forest-labs/FLUX.1-schnell-Free"
    assert call_kwargs["width"] == 1024
    assert call_kwargs["height"] == 576


def test_generate_background_image_raises_on_client_error():
    fake_client = MagicMock()
    fake_client.images.generate.side_effect = RuntimeError("API down")

    with pytest.raises(ImageGenerationError):
        generate_background_image("a scene", client=fake_client)


def test_generate_background_image_raises_on_missing_data():
    fake_client = _make_fake_client(None)

    with pytest.raises(ImageGenerationError):
        generate_background_image("a scene", client=fake_client)
