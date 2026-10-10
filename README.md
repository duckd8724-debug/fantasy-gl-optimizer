# Fantasy GL Optimizer V1

A free, beginner-friendly Streamlit starter dashboard for manually entering an IPL player pool, configuring team rules, generating up to 20 candidate teams, choosing captain/vice-captain, validating teams, and exporting CSV reports.

## Important
The sample players are fictional. This app does not fetch live data, predict real player scores, or guarantee a winning team. `expected_points` and `ceiling` are manual estimates. Confirm current My11Circle rules and scoring in the official app.

## Run from Android for free
You do not need to install Python on your phone. Use Chrome and a free cloud deployment.

1. Download and extract this ZIP.
2. Open https://github.com and sign in or create a free account.
3. Create a **public** repository named `fantasy-gl-optimizer`.
4. Upload `app.py`, `requirements.txt`, and `sample_players.csv` into the repository root. Upload `.streamlit/config.toml` too, preserving its folder path if possible.
5. Open https://share.streamlit.io and sign in with GitHub.
6. Choose **Create app**, select your repository, branch `main`, and main file path `app.py`.
7. Deploy and wait for the app URL to appear.

Free service interfaces/limits can change; follow the current prompts on the hosting site. Do not put passwords, private keys, or personal information in a public repository.

## Use
- Open **Enter players**.
- Replace fictional sample rows with the actual match player pool.
- Role values must be `WK`, `BAT`, `AR`, or `BOWL`.
- Enter credits, expected points, ceiling, selection percentage and `yes`/`no` for playing XI.
- Confirm budget, role limits and squad limit in the sidebar.
- Open **Generate teams**, click **Generate teams**, inspect the validation table and download CSV files.

## CSV fields
`player,team,role,credits,expected_points,ceiling,selection_pct,playing_xi`

`ceiling` is a high-end estimate, not a guaranteed achievable score. Use selection percentage only if you have a credible source; otherwise enter 0 and understand that ownership adjustment will be limited.

## Files
- `app.py`: Streamlit app.
- `requirements.txt`: dependencies.
- `sample_players.csv`: fictional example rows.
- `.streamlit/config.toml`: theme settings.

## Roadmap
Next add persistent match history, versioned scoring rules, real historical data, two-innings simulation and chronological backtesting. Only adopt more complex models when testing shows repeatable improvement.
