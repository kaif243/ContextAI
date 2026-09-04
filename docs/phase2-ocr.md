# Phase 2 — OCR Provider Notes

## Default (development): `mock`

The default OCR provider in Phase 2 is **`mock`** (`OCR_PROVIDER=mock` in
`.env` or unset). It is **not a real OCR engine** — it is a deterministic
stand-in so the rest of the system can be developed and tested on machines
where the user has not installed Tesseract or PaddleOCR.

Behaviour:

* If a sidecar file `<filename>.txt` exists next to the image, the
  contents are returned verbatim with `confidence=1.0`.
* If a sidecar file `<filename>.ocr.json` exists, it is parsed as JSON
  and the `text`, `confidence`, and `regions` fields are used.
* Otherwise a stub string is returned that encodes the image dimensions
  and a SHA-256 hash of the image bytes. The stub is deterministic
  (identical bytes produce identical stubs), so it is safe for tests.

This is the only provider that ships with hard dependencies in Phase 2.

## Production option: `tesseract`

To run real OCR locally:

1. Install the Tesseract binary on the host:
   * **Windows:** download the installer from
     <https://github.com/UB-Mannheim/tesseract/wiki>.
   * **macOS:** `brew install tesseract`.
   * **Linux:** `apt install tesseract-ocr` (or the package manager of
     the distro).
2. `pip install pytesseract Pillow`.
3. Set `OCR_PROVIDER=tesseract` in `.env`.

The provider is detected lazily — if pytesseract or the binary is
missing, `is_available()` returns `False` and the API reports the
provider as unavailable via `/api/v1/screen/ocr/info`. No crash.

## Future option: `paddle` (not implemented)

PaddleOCR is a strong production OCR choice, but its Python distribution
(`paddleocr` + `paddlepaddle`) has known issues on Windows + Python 3.10:

* Large wheel downloads (often 1 GB+ on first install)
* DLL load failures on certain Windows builds
* Conflicts with the system's pre-installed CUDA runtime
* Slow first-run model download (PaddleOCR fetches its model weights on
  first use)

We therefore **do not** install PaddleOCR automatically in Phase 2.
The `PaddleOCRProvider` is shipped as a clearly-marked placeholder
that raises `RuntimeError` if it is selected. To enable it later, the
implementer must:

1. Verify a clean install on the target Windows + Python 3.10 host
   (`pip install paddlepaddle paddleocr`).
2. Implement `recognize()` in `app/ocr/paddle.py` using
   `PaddleOCR(use_angle_cls=True, lang='en')` or similar.
3. Re-evaluate the dependency in CI before enabling it in production
   builds.

## Activity classifier

The screen classifier in `app/classification/baseline.py` is a
**deterministic, rule-based baseline**. It is **NOT a machine-learning
model**:

* No training step.
* No learned weights — the weights are constants in the source file.
* The "confidence" is a heuristic indicator of how strongly the rules
  fired, not a calibrated probability.

The interface `ActivityClassifier` (`app/classification/base.py`) is
the single contract the rest of the system depends on, so a real ML
model can be dropped in later without touching call sites. Set
`ACTIVITY_CLASSIFIER=ml` and add a new branch in
`app/classification/factory.py` to enable it.
