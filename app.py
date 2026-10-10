import random
import re
from io import StringIO

import pandas as pd
import streamlit as st
from PIL import Image

try:
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

st.set_page_config(page_title="Fantasy GL Optimizer V1", page_icon="🏏", layout="wide")
ROLES = ["WK", "BAT", "AR", "BOWL"]
COLUMNS = ["player", "team", "role", "credits", "expected_points", "ceiling", "selection_pct", "playing_xi"]
SAMPLE = """player,team,role,credits,expected_points,ceiling,selection_pct,playing_xi
Sample Batter A,Team A,BAT,9,48,90,72,yes
Sample Allrounder A,Team A,AR,9,52,105,64,yes
Sample Bowler A,Team A,BOWL,8.5,38,82,45,yes
Sample Keeper A,Team A,WK,8.5,42,78,55,yes
Sample Batter B,Team A,BAT,8,32,70,30,yes
Sample Allrounder B,Team A,AR,8,34,76,22,yes
Sample Bowler B,Team A,BOWL,8,35,75,28,yes
Sample Batter C,Team A,BAT,7.5,25,60,12,yes
Sample Bowler C,Team A,BOWL,7.5,27,65,18,yes
Sample Batter D,Team A,BAT,7,20,52,6,yes
Sample Bowler D,Team A,BOWL,7,18,48,5,yes
Sample Batter E,Team B,BAT,9.5,56,110,80,yes
Sample Allrounder C,Team B,AR,9.5,55,108,70,yes
Sample Bowler E,Team B,BOWL,9,44,92,58,yes
Sample Keeper B,Team B,WK,8.5,39,80,48,yes
Sample Batter F,Team B,BAT,8.5,40,85,42,yes
Sample Allrounder D,Team B,AR,8,36,80,32,yes
Sample Bowler F,Team B,BOWL,8,33,78,25,yes
Sample Batter G,Team B,BAT,7.5,28,68,20,yes
Sample Bowler G,Team B,BOWL,7.5,29,70,16,yes
Sample Batter H,Team B,BAT,7,19,50,7,yes
Sample Bowler H,Team B,BOWL,7,17,46,4,yes
"""

def clean(df):
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))
    df = df[COLUMNS].copy()
    df["player"] = df["player"].fillna("").astype(str).str.strip()
    df["team"] = df["team"].fillna("").astype(str).str.strip()
    df["role"] = df["role"].fillna("").astype(str).str.upper().str.strip()
    for c in ["credits", "expected_points", "ceiling", "selection_pct"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["playing_xi"] = df["playing_xi"].fillna("no").astype(str).str.lower().str.strip().isin(
        ["yes", "y", "true", "1", "confirmed"])
    return df

def input_errors(df, size):
    e = []
    if df.empty: e.append("Add player rows.")
    if df["player"].eq("").any(): e.append("Every player needs a name.")
    if df["player"].duplicated().any(): e.append("Player names must be unique.")
    if not set(df["role"].dropna()).issubset(set(ROLES)): e.append("Roles must be WK, BAT, AR or BOWL.")
    if df[["team","credits","expected_points","ceiling","selection_pct"]].isna().any().any():
        e.append("Team, credits and numeric estimates must be filled.")
    if not df["credits"].dropna().between(0.1,30).all(): e.append("Credits must be between 0.1 and 30.")
    if not df["selection_pct"].dropna().between(0,100).all(): e.append("Selection % must be between 0 and 100.")
    if len(df) < size: e.append(f"Need at least {size} players.")
    if int(df["playing_xi"].sum()) < size: e.append(f"At least {size} players must be marked yes in playing_xi.")
    if df["team"].nunique() < 2: e.append("Assign players to both real-world teams.")
    return e

def valid(team, budget, squad_cap, limits, size):
    if len(team) != size or len({p["player"] for p in team}) != size: return False
    if sum(p["credits"] for p in team) > budget + 1e-8: return False
    for role, (lo, hi) in limits.items():
        n = sum(p["role"] == role for p in team)
        if n < lo or n > hi: return False
    return all(sum(p["team"] == s for p in team) <= squad_cap for s in {p["team"] for p in team})

def make_candidates(players, n, budget, squad_cap, limits, size, seed):
    rng = random.Random(seed)
    weights = [max(1, (p["expected_points"] * .65 + p["ceiling"] * .35)) ** 1.25 for p in players]
    found = {}
    for _ in range(n):
        chosen, remaining = [], list(range(len(players)))
        for __ in range(size):
            possible, pw = [], []
            for j in remaining:
                trial = chosen + [players[j]]
                if sum(p["credits"] for p in trial) > budget: continue
                if any(sum(p["role"] == r for p in trial) > limits[r][1] for r in ROLES): continue
                if sum(p["team"] == players[j]["team"] for p in trial) > squad_cap: continue
                slots = size - len(trial)
                rest = [players[k] for k in remaining if k != j]
                if any(sum(p["role"] == r for p in trial) + min(slots, sum(p["role"] == r for p in rest)) < limits[r][0] for r in ROLES):
                    continue
                possible.append(j); pw.append(weights[j] * rng.uniform(.5, 1.5))
            if not possible: break
            j = rng.choices(possible, weights=pw, k=1)[0]
            chosen.append(players[j]); remaining.remove(j)
        if len(chosen) == size and valid(chosen, budget, squad_cap, limits, size):
            key = tuple(sorted(p["player"] for p in chosen))
            found[key] = {"players": chosen, "base": sum(p["expected_points"] for p in chosen),
                          "ceiling": sum(p["ceiling"] for p in chosen)}
    return sorted(found.values(), key=lambda c: c["base"] + .10*(c["ceiling"]-c["base"]), reverse=True)

def cap_value(p, mode):
    upside = max(0, p["ceiling"] - p["expected_points"])
    ownership = p["selection_pct"]/100
    if mode == "Upside": return .35*p["expected_points"] + .65*upside - 2*ownership
    if mode == "Safer": return .9*p["expected_points"] + .1*upside
    return .7*p["expected_points"] + .3*upside - ownership

def generate(players, count, budget, squad_cap, limits, size, overlap, exposure_pct, mode, attempts, seed):
    candidates = make_candidates(players, attempts, budget, squad_cap, limits, size, seed)
    chosen, exposure = [], {p["player"]:0 for p in players}
    cap = max(1, int(count * exposure_pct/100))
    for idx in range(count):
        best, bestscore = None, -1e99
        for cand in candidates:
            names = {p["player"] for p in cand["players"]}
            if any(names == {p["player"] for p in old["players"]} for old in chosen): continue
            if any(len(names & {p["player"] for p in old["players"]}) > size-overlap for old in chosen): continue
            if any(exposure[n] >= cap for n in names): continue
            value = cand["base"] + .10*(cand["ceiling"]-cand["base"])
            value += sum((100-p["selection_pct"])/100 * max(0,p["ceiling"]-p["expected_points"])*.04 for p in cand["players"])
            value -= sum(exposure[n]*.15 for n in names)
            if value > bestscore: best, bestscore = cand, value
        if best is None:
            for cand in candidates:
                names = {p["player"] for p in cand["players"]}
                if any(names == {p["player"] for p in old["players"]} for old in chosen): continue
                value = cand["base"] + .10*(cand["ceiling"]-cand["base"]) - sum(exposure[n]*.15 for n in names)
                if value > bestscore: best, bestscore = cand, value
        if best is None: break
        ordered = sorted(best["players"], key=lambda p:cap_value(p,mode), reverse=True)
        rng = random.Random(seed + 97*(idx+1))
        cp = ordered[:min(6,len(ordered))]
        captain = cp[(idx + rng.randrange(min(3,len(cp)))) % len(cp)]
        vp = [p for p in ordered if p["player"] != captain["player"]][:min(7,len(ordered)-1)]
        vice = vp[(idx*2 + rng.randrange(min(3,len(vp)))) % len(vp)]
        chosen.append({"players":best["players"],"captain":captain["player"],"vice":vice["player"],
                       "base":best["base"],"ceiling":best["ceiling"],
                       "projected_total":best["base"]+captain["expected_points"]+.5*vice["expected_points"]})
        for p in best["players"]: exposure[p["player"]] += 1
        candidates.remove(best)
    warning = None if len(chosen)==count else f"Only {len(chosen)} unique teams found. Increase candidate search or relax overlap/exposure settings."
    return chosen, warning


def screenshot_ocr_to_text(uploaded_file):
    """Preprocess a mobile screenshot and OCR its two player-list columns separately."""
    if not OCR_AVAILABLE:
        return None, "OCR isn't installed. Check requirements.txt and packages.txt, then reboot the Streamlit app."

    from PIL import ImageOps, ImageEnhance, ImageFilter

    image = Image.open(uploaded_file).convert("RGB")
    width, height = image.size

    # Most fantasy app screenshots are tall. Remove a little browser chrome,
    # though cropping in Gallery to the player list usually gives better results.
    if height > width * 1.15:
        image = image.crop((0, int(height * 0.12), width, int(height * 0.96)))

    width, height = image.size
    midpoint = width // 2
    columns = [
        ("LEFT", image.crop((0, 0, midpoint, height))),
        ("RIGHT", image.crop((midpoint, 0, width, height))),
    ]

    output = []
    for label, column in columns:
        scale = max(1.5, min(4.0, 1100 / max(1, column.width)))
        column = column.resize((int(column.width * scale), int(column.height * scale)))
        column = ImageOps.grayscale(column)
        column = ImageEnhance.Contrast(column).enhance(1.8)
        column = ImageEnhance.Sharpness(column).enhance(1.6)
        column = column.filter(ImageFilter.SHARPEN)
        text = pytesseract.image_to_string(column, config="--psm 6")
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in text.splitlines()
            if line.strip()
        ]
        output.append(f"--- {label} PLAYER COLUMN ---\n" + "\n".join(lines))

    return "\n\n".join(output), None


def parse_selection_rows(raw_text):
    """Conservatively pair OCR player names with percentages; mark every row for review."""
    rows = []
    sections = re.split(r"--- (?:LEFT|RIGHT) PLAYER COLUMN ---", raw_text)

    ignore = re.compile(
        r"(?i)(sel\s*by|selected\s*by|points?|avg\.?\s*score|pitch|supports?|"
        r"confirmed|elected|batting|pacers|ind-a|aus-a|team preview|share|"
        r"streamlit|chrome|http|screenshot|playing\s*11)"
    )
    percent_pattern = re.compile(r"(?i)(?:sel\s*by\s*)?(\d{1,3})\s*%")

    for section in sections:
        lines = [
            re.sub(r"\s+", " ", line).strip(" .|:;")
            for line in section.splitlines()
            if line.strip()
        ]
        pending_name = None

        for line in lines:
            matches = list(percent_pattern.finditer(line))
            if matches:
                for match in matches:
                    pct = int(match.group(1))
                    if not 0 <= pct <= 100:
                        continue

                    before = line[:match.start()].strip(" .|:;,-")
                    before = re.sub(r"(?i)\bsel\s*by\b", "", before).strip(" .|:;,-")
                    before = re.sub(r"(?i)\b(?:points?|pts?)\b.*$", "", before).strip(" .|:;,-")
                    letters = re.sub(r"[^A-Za-z]", "", before)
                    name = before if len(letters) >= 4 and not ignore.search(before) else pending_name

                    if name:
                        rows.append({
                            "player": name,
                            "selection_pct": pct,
                            "review_required": True,
                        })
                    pending_name = None
                continue

            if ignore.search(line) or re.search(r"\d", line):
                continue

            candidate = re.sub(r"[^A-Za-z .'-]", "", line).strip(" .'-")
            letters = re.sub(r"[^A-Za-z]", "", candidate)
            if 4 <= len(letters) <= 28 and len(candidate) <= 40:
                pending_name = candidate

    unique, seen = [], set()
    for row in rows:
        name = re.sub(r"\s+", " ", row["player"]).strip(" .'-")
        key = re.sub(r"[^a-z]", "", name.lower())
        signature = (key, int(row["selection_pct"]))
        if len(key) >= 4 and signature not in seen:
            unique.append({
                "player": name,
                "selection_pct": int(row["selection_pct"]),
                "review_required": True,
            })
            seen.add(signature)

    return pd.DataFrame(unique, columns=["player", "selection_pct", "review_required"])


st.title("🏏 Fantasy GL Optimizer — V1")
st.caption("Manual-input starter. This does not guarantee a winning team or provide live player predictions.")
with st.sidebar:
    st.header("Configurable rules")
    size = st.number_input("Players per team", 1, 20, 11)
    budget = st.number_input("Credit budget", 1.0, 300.0, 100.0, .5)
    squad_cap = st.number_input("Max players from one real team", 1, 20, 7)
    count = st.number_input("Teams to generate", 1, 20, 20)
    limits = {}
    st.subheader("Role limits")
    for r, dmin, dmax in [("WK",1,4),("BAT",1,6),("AR",1,6),("BOWL",1,6)]:
        a,b=st.columns(2)
        lo=a.number_input(f"{r} min",0,int(size),min(dmin,int(size)),key=r+"lo")
        hi=b.number_input(f"{r} max",0,int(size),min(dmax,int(size)),key=r+"hi")
        limits[r]=(int(lo),int(hi))
    overlap=st.slider("Players that must differ between teams",1,int(size),min(3,int(size)))
    exposure_pct=st.slider("Target max exposure (%)",20,100,75,5)
    mode=st.selectbox("Captaincy approach",["Balanced","Upside","Safer"])
    attempts=st.slider("Candidate search attempts",500,20000,5000,500)
    seed=st.number_input("Random seed",1,999999,42)

t1,t2,t3,t4=st.tabs(["1. Enter players","2. Generate teams","3. Screenshot input","4. Instructions"])
with t1:
    st.write("Required fields: player, team, role, credits, expected_points, ceiling, selection_pct, playing_xi.")
    st.info("The sample players are fictional. Replace them with the real match player pool.")
    upload=st.file_uploader("Upload player CSV",type=["csv"])
    if "players" not in st.session_state: st.session_state.players=pd.read_csv(StringIO(SAMPLE))
    if upload is not None:
        try: st.session_state.players=pd.read_csv(upload); st.success("CSV loaded.")
        except Exception as e: st.error(f"Could not read CSV: {e}")
    edited=st.data_editor(st.session_state.players,num_rows="dynamic",use_container_width=True,key="player_editor")
    st.session_state.players=edited
    st.download_button("Download CSV template",edited.to_csv(index=False).encode(), "players_template.csv","text/csv")
    try:
        d=clean(edited); errs=input_errors(d,int(size))
        if errs: st.warning("Input checks:\n\n- " + "\n- ".join(errs))
        else: st.success(f"{len(d)} rows loaded; {int(d.playing_xi.sum())} marked as playing.")
    except Exception as e: st.error(str(e))

with t2:
    st.write("Generate a portfolio of valid, varied candidate teams.")
    if st.button("Generate teams",type="primary",use_container_width=True):
        try:
            d=clean(st.session_state.players); errs=input_errors(d,int(size))
            if any(limits[r][0]>limits[r][1] for r in ROLES): errs.append("Role minimum cannot exceed maximum.")
            if any(sum((d.playing_xi)&(d.role==r))<limits[r][0] for r in ROLES): errs.append("Not enough playing players to meet role minimums.")
            if errs: st.error("Fix these issues:\n\n- " + "\n- ".join(errs))
            else:
                result,warning=generate(d[d.playing_xi].to_dict("records"),int(count),float(budget),int(squad_cap),limits,int(size),int(overlap),int(exposure_pct),mode,int(attempts),int(seed))
                st.session_state.result=result; st.session_state.warning=warning
        except Exception as e: st.error(f"Could not generate teams: {e}")
    teams=st.session_state.get("result",[])
    warning=st.session_state.get("warning")
    if warning: st.warning(warning)
    if teams:
        st.success(f"Generated {len(teams)} teams. Verify final XI and current contest rules.")
        summary=[]; details=[]
        for i,t in enumerate(teams,1):
            summary.append({"Team":i,"Projected total*":round(t["projected_total"],1),"Base estimate":round(t["base"],1),
                            "Captain":t["captain"],"Vice-captain":t["vice"],"Players":", ".join(p["player"] for p in t["players"])})
            for p in t["players"]:
                details.append({"team_number":i,"player":p["player"],"real_team":p["team"],"role":p["role"],
                                "credits":p["credits"],"expected_points":p["expected_points"],"ceiling":p["ceiling"],
                                "selection_pct":p["selection_pct"],"captain":p["player"]==t["captain"],
                                "vice_captain":p["player"]==t["vice"]})
        sdf=pd.DataFrame(summary); ddf=pd.DataFrame(details)
        st.dataframe(sdf,use_container_width=True,hide_index=True)
        st.caption("*Uses manually entered estimates and captain multipliers. Not a predicted rank or guarantee.")
        st.download_button("Download generated teams CSV",ddf.to_csv(index=False).encode(),"generated_teams.csv","text/csv",use_container_width=True)
        exposure=ddf.groupby(["player","real_team","role"],as_index=False).agg(appearances=("team_number","count"),captain_count=("captain","sum"),vice_captain_count=("vice_captain","sum"))
        exposure["exposure_pct"]=(100*exposure.appearances/len(teams)).round(1)
        st.subheader("Player exposure")
        st.dataframe(exposure.sort_values("appearances",ascending=False),use_container_width=True,hide_index=True)
        st.download_button("Download exposure CSV",exposure.to_csv(index=False).encode(),"player_exposure.csv","text/csv")
        checks=[]
        for i,t in enumerate(teams,1):
            checks.append({"Team":i,"Valid":valid(t["players"],float(budget),int(squad_cap),limits,int(size)),
                           "Credits":round(sum(p["credits"] for p in t["players"]),1),"Player count":len(t["players"]),
                           "C and VC different":t["captain"]!=t["vice"]})
        st.subheader("Validation")
        st.dataframe(pd.DataFrame(checks),use_container_width=True,hide_index=True)
with t3:
    st.subheader("Screenshot OCR — automatic player names + selection %")
    st.write("Upload the screen where the fantasy app shows player names and ‘Sel By (%)’. OCR reads visible text; verify every extracted row before using it.")
    shots = st.file_uploader("Upload one or more screenshots", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key="screenshot_upload")
    if not OCR_AVAILABLE:
        st.warning("OCR is not active in this deployment yet. The updated project needs both pytesseract in requirements.txt and tesseract-ocr in packages.txt.")
    if shots:
        for ix, shot in enumerate(shots, 1):
            st.markdown(f"**Screenshot {ix}: {shot.name}**")
            st.image(shot, use_container_width=True)
        if st.button("Extract names and selection %", type="primary", key="try_ocr"):
            all_rows = []
            all_text = []
            for shot in shots:
                raw_text, err = screenshot_ocr_to_text(shot)
                if err:
                    st.error(err)
                    break
                all_text.append(f"--- {shot.name} ---\n{raw_text}")
                parsed = parse_selection_rows(raw_text)
                if not parsed.empty:
                    parsed["source_screenshot"] = shot.name
                    all_rows.append(parsed)
            else:
                st.session_state["ocr_raw_text"] = "\n\n".join(all_text)
                if all_rows:
                    extracted = pd.concat(all_rows, ignore_index=True)
                    extracted = extracted.drop_duplicates(subset=["player", "selection_pct"], keep="first")
                    st.session_state["ocr_players"] = extracted
                else:
                    st.session_state["ocr_players"] = pd.DataFrame(columns=["player", "selection_pct", "source_screenshot"])
        if "ocr_raw_text" in st.session_state:
            st.subheader("1. Extracted player table — edit OCR mistakes")
