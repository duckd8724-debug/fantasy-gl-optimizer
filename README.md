# Fantasy GL Optimizer V1

A Streamlit starter app for manually entering fantasy cricket player data, generating varied candidate teams, and extracting player names/selection percentages from screenshots using OCR.

## Run locally

1. Install Python 3.10 or newer.
2. In a terminal, run:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. OCR additionally requires the Tesseract OCR engine installed on your operating system. For Streamlit Community Cloud, `packages.txt` requests `tesseract-ocr`.

## Deploy on Streamlit Community Cloud

1. Upload all project files to the root of a GitHub repository.
2. In Streamlit Community Cloud, create/select the app and set the main file path to `app.py`.
3. Deploy and test with a clear screenshot.

## Important

- The bundled sample players are fictional.
- OCR is best-effort. Always review names and selection percentages.
- OCR does not fill all fields needed for team generation.
- Predictions are not live and no team or outcome is guaranteed.
