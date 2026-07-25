import base64
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / ".viewer_builder" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from viewer_builder.build import (  # noqa: E402
    NOTARIZATION_ACCOUNT_ID,
    fetch_notarized_hashes,
    main,
    notar_stamp_transform,
)


def encode_data(value: bytes | str) -> str:
    raw_value = value.encode("utf-8") if isinstance(value, str) else value
    return base64.b64encode(raw_value).decode("ascii")


def make_response(payload: object) -> io.BytesIO:
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class FetchNotarizedHashesTests(unittest.TestCase):
    def test_decodes_hashes_and_ignores_other_account_data(self) -> None:
        expected_hash = "a" * 64
        payload = {
            "account_id": NOTARIZATION_ACCOUNT_ID,
            "data": {
                "hash-uppercase": encode_data(expected_hash.upper()),
                "hash-duplicate": encode_data(expected_hash),
                "ordinary-text": encode_data("Montelibero notarization account"),
                "binary": encode_data(b"\xff\x00"),
            },
        }

        with patch("viewer_builder.build.urlopen", return_value=make_response(payload)):
            result = fetch_notarized_hashes(fail_on_error=True)

        self.assertEqual(result, {expected_hash})

    def test_transport_failure_is_best_effort_by_default(self) -> None:
        with (
            patch("viewer_builder.build.urlopen", side_effect=URLError("offline")),
            self.assertLogs("viewer_builder", level="WARNING") as captured,
        ):
            result = fetch_notarized_hashes()

        self.assertEqual(result, set())
        self.assertIn("Unable to fetch valid notarization data", captured.output[0])

    def test_transport_failure_is_fatal_in_strict_mode(self) -> None:
        with (
            patch("viewer_builder.build.urlopen", side_effect=URLError("offline")),
            self.assertRaisesRegex(RuntimeError, "Unable to fetch valid notarization data"),
        ):
            fetch_notarized_hashes(fail_on_error=True)

    def test_strict_mode_rejects_invalid_responses(self) -> None:
        invalid_responses = (
            io.BytesIO(b"not-json"),
            make_response([]),
            make_response({"account_id": "GUNEXPECTED", "data": {}}),
            make_response({"account_id": NOTARIZATION_ACCOUNT_ID}),
            make_response({"account_id": NOTARIZATION_ACCOUNT_ID, "data": []}),
        )

        for response in invalid_responses:
            with self.subTest(response=response.getvalue()):
                response.seek(0)
                with (
                    patch("viewer_builder.build.urlopen", return_value=response),
                    self.assertRaisesRegex(RuntimeError, "Unable to fetch valid notarization data"),
                ):
                    fetch_notarized_hashes(fail_on_error=True)

    def test_strict_mode_accepts_valid_response_without_hashes(self) -> None:
        data_values = ({}, {"ordinary-text": encode_data("not a SHA-256 hash")})

        for data in data_values:
            with self.subTest(data=data):
                payload = {
                    "account_id": NOTARIZATION_ACCOUNT_ID,
                    "data": data,
                }
                with patch("viewer_builder.build.urlopen", return_value=make_response(payload)):
                    result = fetch_notarized_hashes(fail_on_error=True)

                self.assertEqual(result, set())

    def test_malformed_field_is_fatal_only_in_strict_mode(self) -> None:
        expected_hash = "b" * 64
        for malformed_value in ("not valid base64%", "snowman: ☃", 123):
            with self.subTest(malformed_value=malformed_value):
                payload = {
                    "account_id": NOTARIZATION_ACCOUNT_ID,
                    "data": {
                        "valid": encode_data(expected_hash),
                        "malformed": malformed_value,
                    },
                }

                with (
                    patch("viewer_builder.build.urlopen", return_value=make_response(payload)),
                    self.assertLogs("viewer_builder", level="WARNING"),
                ):
                    self.assertEqual(fetch_notarized_hashes(), {expected_hash})

                with (
                    patch("viewer_builder.build.urlopen", return_value=make_response(payload)),
                    self.assertRaisesRegex(RuntimeError, "Unable to decode notarization data field"),
                ):
                    fetch_notarized_hashes(fail_on_error=True)


class NotarStampTransformTests(unittest.TestCase):
    def test_maps_hash_segments_to_full_position_and_rotation_ranges(self) -> None:
        self.assertEqual(
            notar_stamp_transform("0" * 64),
            {"x": -20.0, "y": -20.0, "rotation": -30.0},
        )
        self.assertEqual(
            notar_stamp_transform("f" * 64),
            {"x": 20.0, "y": 20.0, "rotation": 30.0},
        )

    def test_is_stable_and_varies_between_document_hashes(self) -> None:
        first_hash = "0123456789abcdef13579bdf" + "0" * 40
        second_hash = "fedcba9876543210eca86420" + "0" * 40

        self.assertEqual(
            notar_stamp_transform(first_hash),
            notar_stamp_transform(first_hash),
        )
        self.assertNotEqual(
            notar_stamp_transform(first_hash),
            notar_stamp_transform(second_hash),
        )


class StrictNotarizationCliTests(unittest.TestCase):
    def test_returns_one_before_resetting_output(self) -> None:
        with (
            patch(
                "viewer_builder.build.fetch_notarized_hashes",
                side_effect=RuntimeError("notarization unavailable"),
            ) as fetch,
            patch("viewer_builder.build.reset_output_directory") as reset_output,
            self.assertLogs("viewer_builder", level="ERROR"),
        ):
            result = main(["--require-notarization-data"])

        self.assertEqual(result, 1)
        fetch.assert_called_once_with(fail_on_error=True)
        reset_output.assert_not_called()


if __name__ == "__main__":
    unittest.main()
