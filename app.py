from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Headers pour imiter un vrai navigateur et éviter les blocages EA
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (HTML, KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.ea.com/",
    "Origin": "https://www.ea.com",
}

EA_BASE = "https://proclubs.ea.com/api/fc"

# ----------------------------------------------------------------
# ROUTE : /stats?club=NomDuClub&platform=ps5
# Retourne les stats du club directement lisibles par BotGhost
# ----------------------------------------------------------------
@app.route("/stats")
def stats():
    club_name = request.args.get("club", "").strip()
    platform  = request.args.get("platform", "common-gen5")

    # Conversion des noms de plateforme BotGhost → EA
    platform_map = {
        "ps5":          "common-gen5",
        "xbox":         "common-gen5",
        "xbox-series-xs": "common-gen5",
        "pc":           "common-gen5",
        "ps4":          "common-gen4-cross",
        "xboxone":      "common-gen4-cross",
    }
    ea_platform = platform_map.get(platform, platform)

    if not club_name:
        return jsonify({"erreur": "Parametre 'club' manquant"}), 400

    # --- Étape 1 : Recherche du club ---
    try:
        search_resp = requests.get(
            f"{EA_BASE}/clubs/search",
            params={"platform": ea_platform, "clubName": club_name},
            headers=HEADERS,
            timeout=10
        )
        search_data = search_resp.json()
    except Exception as e:
        return jsonify({"erreur": f"Erreur recherche club: {str(e)}"}), 500

    clubs = search_data.get("clubs", [])
    if not clubs:
        return jsonify({"erreur": f"Club '{club_name}' introuvable sur {platform}"}), 404

    # On prend le premier résultat
    if isinstance(clubs, dict):
        club = list(clubs.values())[0]
    else:
        club = clubs[0]

    club_id   = club.get("clubId", club.get("id", "?"))
    club_name_real = club.get("name", club_name)

    # --- Étape 2 : Stats saisonnières ---
    try:
        stats_resp = requests.get(
            f"{EA_BASE}/clubs/seasonalStats",
            params={"platform": ea_platform, "clubIds": club_id},
            headers=HEADERS,
            timeout=10
        )
        stats_data = stats_resp.json()
    except Exception as e:
        return jsonify({"erreur": f"Erreur stats club: {str(e)}"}), 500

    clubs_stats = stats_data.get("clubs", {})
    if isinstance(clubs_stats, dict):
        s = list(clubs_stats.values())[0] if clubs_stats else {}
    elif isinstance(clubs_stats, list):
        s = clubs_stats[0] if clubs_stats else {}
    else:
        s = {}

    # --- Calcul du win rate ---
    wins   = int(s.get("wins", 0))
    losses = int(s.get("losses", 0))
    ties   = int(s.get("ties", 0))
    total  = wins + losses + ties
    winrate = round((wins / total) * 100, 1) if total > 0 else 0

    # --- Retour JSON propre pour BotGhost ---
    return jsonify({
        "nom":          club_name_real,
        "club_id":      club_id,
        "skill":        s.get("skillRating", "?"),
        "division":     s.get("divisionOffset", "?"),
        "wins":         wins,
        "losses":       losses,
        "ties":         ties,
        "total_matchs": total,
        "winrate":      f"{winrate}%",
        "buts_pour":    s.get("goals", "?"),
        "buts_contre":  s.get("goalsAgainst", "?"),
        "plateforme":   platform,
    })


# ----------------------------------------------------------------
# ROUTE : /membres?club=NomDuClub&platform=ps5
# Retourne les stats des joueurs du club
# ----------------------------------------------------------------
@app.route("/membres")
def membres():
    club_name = request.args.get("club", "").strip()
    platform  = request.args.get("platform", "common-gen5")

    platform_map = {
        "ps5": "common-gen5", "xbox": "common-gen5",
        "xbox-series-xs": "common-gen5", "pc": "common-gen5",
        "ps4": "common-gen4-cross", "xboxone": "common-gen4-cross",
    }
    ea_platform = platform_map.get(platform, platform)

    if not club_name:
        return jsonify({"erreur": "Parametre 'club' manquant"}), 400

    # Recherche du club
    try:
        search_resp = requests.get(
            f"{EA_BASE}/clubs/search",
            params={"platform": ea_platform, "clubName": club_name},
            headers=HEADERS, timeout=10
        )
        clubs = search_resp.json().get("clubs", [])
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

    if not clubs:
        return jsonify({"erreur": f"Club '{club_name}' introuvable"}), 404

    if isinstance(clubs, dict):
        club = list(clubs.values())[0]
    else:
        club = clubs[0]

    club_id = club.get("clubId", club.get("id"))

    # Stats des membres
    try:
        members_resp = requests.get(
            f"{EA_BASE}/members/stats",
            params={"platform": ea_platform, "clubId": club_id},
            headers=HEADERS, timeout=10
        )
        members_data = members_resp.json()
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

    members = members_data.get("members", [])
    result = []
    for m in members[:10]:  # Max 10 joueurs pour éviter les messages trop longs
        result.append({
            "pseudo":       m.get("name", "?"),
            "buts":         m.get("goals", 0),
            "passes":       m.get("assists", 0),
            "note_moy":     m.get("ratingAve", "?"),
            "matchs":       m.get("gamesPlayed", 0),
            "pass_pct":     m.get("passSuccessRate", "?"),
        })

    # Trier par buts
    result.sort(key=lambda x: int(x["buts"]) if str(x["buts"]).isdigit() else 0, reverse=True)

    return jsonify({
        "club":    club.get("name", club_name),
        "membres": result
    })


# ----------------------------------------------------------------
# ROUTE : /matchs?club=NomDuClub&platform=ps5
# Retourne les derniers matchs du club
# ----------------------------------------------------------------
@app.route("/matchs")
def matchs():
    club_name = request.args.get("club", "").strip()
    platform  = request.args.get("platform", "common-gen5")

    platform_map = {
        "ps5": "common-gen5", "xbox": "common-gen5",
        "xbox-series-xs": "common-gen5", "pc": "common-gen5",
        "ps4": "common-gen4-cross", "xboxone": "common-gen4-cross",
    }
    ea_platform = platform_map.get(platform, platform)

    # Recherche du club
    try:
        search_resp = requests.get(
            f"{EA_BASE}/clubs/search",
            params={"platform": ea_platform, "clubName": club_name},
            headers=HEADERS, timeout=10
        )
        clubs = search_resp.json().get("clubs", [])
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

    if not clubs:
        return jsonify({"erreur": f"Club '{club_name}' introuvable"}), 404

    if isinstance(clubs, dict):
        club = list(clubs.values())[0]
    else:
        club = clubs[0]

    club_id = club.get("clubId", club.get("id"))

    # Derniers matchs
    try:
        matches_resp = requests.get(
            f"{EA_BASE}/clubs/matches",
            params={"platform": ea_platform, "matchType": "leagueMatch", "clubIds": club_id},
            headers=HEADERS, timeout=10
        )
        matches_data = matches_resp.json()
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500

    matchs_list = []
    for match in matches_data[:5]:  # 5 derniers matchs
        clubs_in_match = match.get("clubs", {})
        mon_club = clubs_in_match.get(str(club_id), {})
        adversaire_id = [k for k in clubs_in_match if k != str(club_id)]
        adversaire = clubs_in_match.get(adversaire_id[0], {}) if adversaire_id else {}

        buts_pour   = mon_club.get("goals", "?")
        buts_contre = adversaire.get("goals", "?")

        if str(buts_pour).isdigit() and str(buts_contre).isdigit():
            if int(buts_pour) > int(buts_contre):
                resultat = "✅ Victoire"
            elif int(buts_pour) < int(buts_contre):
                resultat = "❌ Défaite"
            else:
                resultat = "🤝 Nul"
        else:
            resultat = "?"

        matchs_list.append({
            "resultat":     resultat,
            "score":        f"{buts_pour} - {buts_contre}",
            "adversaire":   adversaire.get("details", {}).get("name", "Inconnu"),
        })

    return jsonify({
        "club":   club.get("name", club_name),
        "matchs": matchs_list,
        "dernier_resultat":  matchs_list[0]["resultat"] if matchs_list else "?",
        "dernier_score":     matchs_list[0]["score"] if matchs_list else "?",
        "dernier_adversaire": matchs_list[0]["adversaire"] if matchs_list else "?",
    })


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
