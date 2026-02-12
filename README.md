# Ads Dashboard (Streamlit)

Multi-page Streamlit app for ad performance analysis (Executive, Optimization, Keywords, Sales).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy free on Streamlit Community Cloud

1. Push this project to a public GitHub repo.
2. Go to https://share.streamlit.io/
3. Click **New app**.
4. Select your repo/branch.
5. Set **Main file path** to `app.py`.
6. Click **Deploy**.

The app uses:
- `requirements.txt` for Python dependencies
- `runtime.txt` to pin Python version
- `.streamlit/config.toml` for Streamlit config

## Notes

- Keep `data/ads_data.csv` in the repo so the app has data on first load.
- Do not commit local virtual environments (`venv/`, `streamlit/`).
