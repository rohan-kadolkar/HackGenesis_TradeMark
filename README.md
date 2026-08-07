# 🐄 Karnataka Biosecurity Network

### Protecting Livestock. Empowering Farmers. Securing Karnataka's Food Future.

## 🚨 The Problem

Every year, livestock diseases like **FMD, PPR, HS, Avian Influenza, and ASF** rip through rural Karnataka, wiping out farmer incomes and threatening food security — often because early warning signs go unreported until it's too late. Farmers lack a fast way to flag outbreaks, veterinarians struggle to prioritize cases across sprawling districts, and state officials are left reacting to crises instead of preventing them. Disconnected, paper-based reporting means disease spreads faster than the response.

**Karnataka Biosecurity Network** closes that gap — a real-time, role-based platform that connects **farmers, veterinarians, district heads, and state heads** into a single command chain for disease detection and response.

## ✨ What Makes This Different

- 🌾 **Farmer-First Design** — A bilingual (English + Kannada) dashboard so language is never a barrier to reporting an emergency.
- 🤖 **AI-Powered Triage** — Gemini API integration delivers instant, AI-generated interim guidance the moment a farmer reports a case, with a smart rule-based fallback when offline from AI.
- 🩺 **Streamlined Vet Workflows** — Vets see live, district-filtered case queues, schedule visits, and resolve cases without ever touching a phone tree.
- 🗺️ **Risk Zone Intelligence** — District and state heads get color-coded Red/Yellow/Green outbreak maps (Leaflet) and vaccination coverage visualizations (Chart.js) for data-driven decisions.
- 📊 **State-Wide Command View** — Cross-district performance comparisons and AI-generated insights turn scattered reports into a coherent state biosecurity strategy.
- 🇮🇳 **Built on Real Karnataka Data** — Seeded with authentic data from all 15 districts, real talukas and villages, and actual vaccination/outbreak statistics — not dummy placeholders.

## 💥 Impact

By compressing the time between "a cow gets sick" and "a vet is on the way," this platform can help contain outbreaks before they become epidemics — protecting rural livelihoods, animal welfare, and Karnataka's agricultural economy at scale.

## 🛠️ Tech Stack

`Flask` · `SQLAlchemy` · `Flask-Login` · `Bootstrap 5` · `Chart.js` · `Leaflet Maps` · `Google Gemini API` · `SQLite`

## 🚀 Installation

```bash
# 1. Clone and enter the project
cd biosecurity_karnataka

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Enable AI-powered suggestions
export GEMMA_API_KEY="your_gemma_api_key_here"

# 4. Launch — database auto-creates and seeds with Karnataka data
python app.py
```

Then visit **`http://localhost:5000`** 🎉

## 🔑 Try It Now — Demo Accounts

| Role | Username | Password |
|------|----------|----------|
| Farmer | `farmer_bengaluru_urban_1` | `farmer123` |
| Vet | `vet_bengaluru_urban_1` | `vet123` |
| District Head | `district_bengaluru_urban` | `district123` |
| State Head | `karnataka_state` | `state123` |

## 📖 Usage

1. **Farmers** log in, report emergencies with photo evidence, and instantly receive AI-generated interim guidance while help is on the way.
2. **Vets** review incoming cases by district, accept and schedule visits, then close the loop with resolution notes.
3. **District Heads** monitor active cases, vaccination coverage, and broadcast alerts to their network.
4. **State Heads** track cross-district risk zones and issue state-wide advisories backed by AI insights.

## 🤝 Contributing

We'd love your help extending the network's reach:

1. Fork the repo and create a feature branch
2. Follow existing code structure (`models.py`, `data.py`, `templates/`)
3. Test against the seeded demo accounts before submitting
4. Open a PR describing your change and its real-world impact

Ideas welcome: SMS alerts (Twilio/Exotel), Firebase push notifications, a Flutter companion app, PWA offline mode, and expanded multilingual support (Telugu, Tamil, Marathi).

## 📜 License

Developed for the **Animal Husbandry & Veterinary Services Department, Karnataka**.

---

*Built to give every farmer a voice — and every outbreak a faster response.*
