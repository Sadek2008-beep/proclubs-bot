from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://proclubs.ea.com/",
    "Origin": "https://proclubs.ea.com",
    "x-requested-with": "XMLHttpRequest",
}

EA_BASE = "https://proclubs.ea.com/api/fc"

PLATFORM_MAP = {
    "ps5":            "common-gen5",
    "xbox":           "common-gen5",
    "xbox-series-xs": "common-gen5",
    "pc":             "common-gen5",
    "ps4":            "common-gen4-cross",
    "xboxone":        "common-gen4-cross",
    "common-gen5":    "common-gen5",
    "common-gen4-cross": "common-gen4-cross",
}

def get_platform(p):
    return PLATFORM_MAP.get(p, "common-gen5")

def search_club(club_name, platform):
    url = f"{EA_BASE}/clubs/search"
    params = {"platform": platform, "clubName": club_name}
    r = requests.get(url, params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()

@app.route("/stats")
def stats():
    club_name = request.args.get("club", "").strip()
    platform  = get_platform(request.args.get("platform", "ps5"))

    if not club_name:
        return jsonify({"erreur": "Parametre 'club' manquant"}), 400

    try:
        search_data = search_club(club_name, platform)
    except Exception as e:
        return jsonify({"erreur": f"Recherche impossible: {str(e)}"}), 500

    clubs = search_data.get("clubs", [])
    if not clubs:
        return jsonify({"erreur": f"Club '{club_name}' introuvable"}), 404

    club = list(clubs.values())[0] if isinstance(clubs, dict) else clubs[0]
    club_id = club.get("clubId", club.get("id", "?"))

    try:
        stats_r = requests.get(
            f"{EA_BASE}/clubs/seasonalStats",
            params={"platform": platform, "clubIds": club_id},
            headers=HEADERS, timeout=10
        )
        stats_r.raise_for_status()
        stats_data = stats_r.json()
    except Exception as e:
        return jsonify({"erreur": f"Stats impossible: {str(e)}"}), 500

    clubs_stats = stats_data.get("clubs", {})
    s = list(clubs_stats.values())[0] if isinstance(clubs_stats, dict) and clubs_stats else {}

    wins   = int(s.get("wins", 0))
    losses = int(s.get("losses", 0))
    ties   = int(s.get("ties", 0))
    total  = wins + losses + ties
    winrate = round((wins / total) * 100, 1) if total > 0 else 0

    return jsonify({
        "nom":           club.get("name", club_name),
        "club_id":       club_id,
        "skill":         s.get("skillRating", "?"),
        "division":      s.get("divisionOffset", "?"),
        "wins":          wins,
        "losses":        losses,
        "ties":          ties,
        "total_matchs":  total,
        "winrate":       f"{winrate}%",
        "buts_pour":     s.get("goals", "?"),
        "buts_contre":   s.get("goalsAgainst", "?"),
        "plateforme":    platform,
    })

@app.route("/membres")
def membres():
    club_name = request.args.get("club", "").strip()
    platform  = get_platform(request.args.get("platform", "ps5"))

    if not club_name:
        return jsonify({"erreur": "Parametre 'club' manquant"}), 400

    try:
        clubs = search_club(club_name, platform).get("clubs", [])
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

    if not clubs:
        return jsonify({"erreur": f"Club '{club_name}' introuvable"}), 404

    club = list(clubs.values())[0] if isinstance(clubs, dict) else clubs[0]
    club_id = club.get("clubId", club.get("id"))

    try:
        r = requests.get(
            f"{EA_BASE}/members/stats",
            params={"platform": platform, "clubId": club_id},
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        members_data = r.json()
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

    members = members_data.get("members", [])
    result = []
    for m in members[:10]:
        result.append({
            "pseudo":   m.get("name", "?"),
            "buts":     m.get("goals", 0),
            "passes":   m.get("assists", 0),
            "note_moy": m.get("ratingAve", "?"),
            "matchs":   m.get("gamesPlayed", 0),
        })
    result.sort(key=lambda x: int(x["buts"]) if str(x["buts"]).isdigit() else 0, reverse=True)

    return jsonify({"club": club.get("name", club_name), "membres": result})

@app.route("/matchs")
def matchs():
    club_name = request.args.get("club", "").strip()
    platform  = get_platform(request.args.get("platform", "ps5"))

    if not club_name:
        return jsonify({"erreur": "Parametre 'club' manquant"}), 400

    try:
        clubs = search_club(club_name, platform).get("clubs", [])
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

    if not clubs:
        return jsonify({"erreur": f"Club '{club_name}' introuvable"}), 404

    club = list(clubs.values())[0] if isinstance(clubs, dict) else clubs[0]
    club_id = club.get("clubId", club.get("id"))

    try:
        r = requests.get(
            f"{EA_BASE}/clubs/matches",
            params={"platform": platform, "matchType": "leagueMatch", "clubIds": club_id},
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        matches_data = r.json()
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

    matchs_list = []
    for match in matches_data[:5]:
        clubs_in = match.get("clubs", {})
        mon = clubs_in.get(str(club_id), {})
        adv_ids = [k for k in clubs_in if k != str(club_id)]
        adv = clubs_in.get(adv_ids[0], {}) if adv_ids else {}

        bp = mon.get("goals", "?")
        bc = adv.get("goals", "?")

        if str(bp).isdigit() and str(bc).isdigit():
            if int(bp) > int(bc):   res = "Victoire"
            elif int(bp) < int(bc): res = "Defaite"
            else:                   res = "Nul"
        else:
            res = "?"

        matchs_list.append({
            "resultat":    res,
            "score":       f"{bp} - {bc}",
            "adversaire":  adv.get("details", {}).get("name", "Inconnu"),
        })

    return jsonify({
        "club":               club.get("name", club_name),
        "matchs":             matchs_list,
        "dernier_resultat":   matchs_list[0]["resultat"] if matchs_list else "?",
        "dernier_score":      matchs_list[0]["score"] if matchs_list else "?",
        "dernier_adversaire": matchs_list[0]["adversaire"] if matchs_list else "?",
    })

@app.route("/debug")
def debug():
    club_name = request.args.get("club", "Rising Stars XI")
    platform  = get_platform(request.args.get("platform", "ps5"))
    try:
        r = requests.get(
            f"{EA_BASE}/clubs/search",
            params={"platform": platform, "clubName": club_name},
            headers=HEADERS, timeout=10
        )
        return jsonify({"status": r.status_code, "body": r.text[:2000]})
    except Exception as e:
        return jsonify({"erreur": str(e)})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
