# Alertă ANM Județ România

Integrare Home Assistant pentru alertele meteorologice ANM (Administrația Națională de Meteorologie) pe județe. Afișează alerte meteo în timp real cu suport pentru toate cele 42 de județe din România plus București.

## Caracteristici

✅ **5 Senzori Automați:**
- `sensor.avertizari_meteo_anm` - Status alertelor (active/inactive)
- `sensor.anm_avertizare_id` - ID-uri hărți active
- `sensor.mesaj_meteo_{judet}` - Mesaj alert filtrat pe județ
- `sensor.harta_meteo_activa` - URL hartă proxy
- `sensor.culoare_harta_{judet}` - Culoare detectată (galben/portocaliu/roșu)

✅ **Configurare Simplă:**
- Selector de județ cu toate 43 de opțiuni (42 județe + București)
- Interval de actualizare configurable (5-60 minute)
- Configurare via UI Home Assistant

✅ **Card Lovelace Avansat:**
- Titlu colorat dinamic pe baza alertei
- Mesaje formatate cu COD-uri evidențiate
- Hărți SVG interactive
- Detectare automată a senzorilor

## Instalare

### Metoda 1: HACS (Recomandat)

1. Deschide HACS în Home Assistant
2. Click pe **Repositories** (iconă cu trei puncte)
3. Selectează **Custom repositories**
4. Adaugă URL: `https://github.com/dancucu/alerta-anm-judet-romania`
5. Categoria: `Integration`
6. Caută "Alertă ANM Județ România" și instalează

### Metoda 2: Instalare Manuală

1. Copiază directorul `custom_components/alerta_anm_judet_romania` din acest repository în directorul `custom_components` din Home Assistant:
   ```bash
   # Navighează la Home Assistant
   cd /root/homeassistant/
   # sau pe sistem standard
   cd ~/.homeassistant/
   
   # Clonează repository-ul temporar
   git clone https://github.com/dancucu/alerta-anm-judet-romania.git temp_alerta
   
   # Copiază integrarea
   cp -r temp_alerta/custom_components/alerta_anm_judet_romania custom_components/
   
   # Șterge fișierele temporare
   rm -rf temp_alerta
   ```

2. Restart Home Assistant

## Configurare

### Pasul 1: Adăugare Integrare

1. Mergi la **Settings** → **Devices & Services** → **Integrations**
2. Click pe **+ Create Integration**
3. Caută și selectează **"Alertă ANM Județ România"**

### Pasul 2: Selectare Județ

4. Alege județul din dropdown (ex: Galați, Cluj, București, etc.)
5. Setează intervalul de actualizare (implicit 10 minute, range 5-60)
6. Click **Submit**

### Pasul 3: Verificare Senzori

După configurare, verifică că toți senzorii s-au creat:
- **Settings** → **Devices & Services** → **Entities**
- Caută "Alertă ANM" sau "mesaj_meteo"

**⏱️ Notă importantă:** API-ul ANM poate dura între 1-60 minute să răspundă la pornire sau după restart Home Assistant. Senzorul mesaj meteo va afișa "Se încarcă datele meteo..." până când datele sunt preluate cu succes. Acest lucru este normal și depinde de disponibilitatea serverelor ANM.

## Automatizări și Card Lovelace

### Exemple Gata de Folosit

**📁 Directorul [`examples/`](examples/)** conține fișiere de configurare opționale care NU sunt instalate automat cu integrarea:

1. **[automation_notificare_inceput_avertizare.yaml](examples/automation_notificare_inceput_avertizare.yaml)** - Notificări când apar alerte meteo noi
2. **[automation_notificare_sfarsit_avertizare.yaml](examples/automation_notificare_sfarsit_avertizare.yaml)** - Notificări când alertele se termină
3. **[lovelace_card.yaml](examples/lovelace_card.yaml)** - Card Lovelace complet configurat
4. **[README.md](examples/README.md)** - Ghid detaliat de instalare și personalizare

**📝 Notă:** Aceste fișiere sunt exemple care trebuie instalate manual. Vezi instrucțiuni detaliate în [`examples/README.md`](examples/README.md).

**Instalare rapidă - Automatizări:**
1. Deschide fișierul dorit din [`examples/`](examples/) pe GitHub
2. Copiază tot conținutul
3. În Home Assistant: **Settings** → **Automations & Scenes** → **+ Create Automation** → **⋮** → **Edit in YAML**
4. Lipește conținutul și salvează

**Instalare rapidă - Card Lovelace:**
1. **Instalează dependențele** prin HACS:
   - `custom:button-card`
   - `custom:fold-entity-row`
2. Copiază conținutul din [`examples/lovelace_card.yaml`](examples/lovelace_card.yaml)
3. În dashboard: **Edit Dashboard** → **+ Add Card** → **Manual** → lipește conținutul

## Utilizare

### Monitorizare în Lovelace

**📋 Card Lovelace complet** se găsește în [`examples/lovelace_card.yaml`](examples/lovelace_card.yaml)

Acest card oferă:
- ✅ Titlu colorat dinamic pe baza gravității alertei (galben/portocaliu/roșu)
- ✅ Mesaje formatate cu COD-uri evidențiate
- ✅ Hărți SVG interactive
- ✅ Detectare automată a senzorilor

**Pentru instalare:** Vezi instrucțiuni detaliate în [`examples/README.md`](examples/README.md)

### Automatizări Incluse

Integrarea vine cu **2 automatizări gata configurate** pentru notificări intelligent:

#### 1. **Notificare Inceput Alertă** (`automation_notificare_inceput_avertizare.yaml`)

Se declanșează când o **nouă alertă meteo apare** pe senzorul județului selectat.

**Funcționalități:**
- Titlu colorat dinamic (🚨 COD ROȘU / 🟠 COD PORTOCALIU / ⚠️ COD GALBEN)
- Extrage și formatează **Interval de valabilitate** și **Fenomene vizate**
- Trimite notificări pe **iPhone** și **HTML5** (browser)
- Sound diferit pentru cod roșu/portocaliu vs galben

**Ce face:**
```
Trigger: Senzor mesaj_meteo_{judet} merge în stare "alerta"
         ↓
Variables: Extrage cod_judet și mesaj_complet din atribute
         ↓
Conditions: Verifică validitate senzor și disponibilitate ANM
         ↓
Actions: Trimite notificări cu Interval și Fenomene formatate
```

**Exemplu mesaj iPhone:**
```
🚨 COD ROȘU GALAȚI
🕒 Luni 6 ianuarie 2025, 08:00 - Marți 6 ianuarie 2025, 20:00

💨 Fenomene vizate:
- Vânt puternic
- Viscol
```

#### 2. **Notificare Sfarsit Alertă** (`automation_notificare_sfarsit_avertizare.yaml`)

Se declanșează când alerta **se termină** (stare revine la `liniste`).

**Funcționalități:**
- Mesaj de confirmare: ✅ Alertă Meteo Finalizată
- Notificări pe **iPhone** și **HTML5**
- Validări pentru a preveni déclanșări false

**Ce face:**
```
Trigger: Senzor mesaj_meteo_{judet} merge în stare "liniste"
         ↓
Conditions: Verifică că trecerea de stare e validă
         ↓
Actions: Trimite notificare de confirmare
```

**Exemplu mesaj:**
```
✅ Alertă Meteo Finalizată
Nu mai sunt avertizări meteo active. Vremea s-a liniștit. ☀️
```

#### Notificări Configurate

Automatizările trimit notificări pe:
- **iPhone** - `notify.mobile_app_iphone` (trebuie să existe în Home Assistant)
- **HTML5** - `notify.html5` (notificări browser desktop)

**Pentru a configura notificări pe alte dispozitive**, editează fișierele YAML și înlocuiește serviciile notify cu ale tale (ex: `notify.telegram`, `notify.discord`, etc.).

### Exemplu Notificare Personalizată

Pentru a adăuga o notificare suplimentară (ex: Telegram):

```yaml
# În automation_notificare_inceput_avertizare.yaml, adaugă după acțiunea HTML5:
  - action: notify.telegram
    data:
      title: "{{ 'COD ROȘU' if 'rosu' in mesaj_complet | lower else 'Avertizare Meteo' }}"
      message: "{{ mesaj_complet }}"
```

## Dependințe

### Pentru Integrare (instalate automat):
- Home Assistant 2023.1.0+
- Python 3.10+

### Pentru Card Lovelace (opțional, instalare manuală prin HACS):
- `custom:button-card` - https://github.com/custom-cards/button-card
- `custom:fold-entity-row` - https://github.com/thomasloven/lovelace-fold-entity-row

**Notă:** Custom cards sunt necesare doar dacă folosești cardul Lovelace din [`examples/`](examples/).

## Probleme Frecvente

### "Integrare nu se găsește"
- Restart Home Assistant după instalare
- Verifică că folder-ul `alerta_anm_judet_romania` este în `custom_components`

### "Senzori nu se actualizează"
- Verifică intervalul de actualizare (minim 5 minute)
- Controlează conexiunea la internet și website-ul ANM
- API-ul ANM poate fi lent - așteaptă până la 60 minute pentru primul răspuns după pornire/restart

### "Card Lovelace arată gol"
- Instalează `custom:button-card` și `custom:fold-entity-row` prin HACS
- Reload browser (Ctrl+Shift+R)
- Verifică că ai copiat cardul din [`examples/lovelace_card.yaml`](examples/lovelace_card.yaml)
- Asigură-te că senzorii sunt disponibili (nu 'unavailable')

### "Culoare rămâne portocalie"
- Verifică că senzorul `sensor.culoare_harta_{judet}` are state valid
- Asigură-te că sunt alerte active în ANM API

## Dezvoltare

### Clonare Repository
```bash
git clone https://github.com/dancucu/alerta-anm-judet-romania.git
cd alerta-anm-judet-romania
```

### Structura Proiect
```
alerta-anm-judet-romania/
├── custom_components/
│   └── alerta_anm_judet_romania/
│       ├── __init__.py           # Setup integrare
│       ├── config_flow.py        # Configurare UI
│       ├── const.py              # Constante (județe, URL-uri)
│       ├── sensor.py             # Definiția senzorilor
│       ├── check_map.py          # Script detecție culoare hartă
│       └── manifest.json         # Metadate integrare
├── examples/
│   ├── automation_notificare_inceput_avertizare.yaml
│   ├── automation_notificare_sfarsit_avertizare.yaml
│   └── lovelace_card.yaml        # Template card Lovelace
├── hacs.json                     # Configurare HACS
└── README.md                     # Acest fișier
```

### Județe Suportate

Toate cele 43 de unități administrative:
- **București (B)** + **42 județe:** Alba, Arad, Argeș, Bacău, Bihor, Bistrița-Năsăud, Botoșani, Brăila, Brașov, Buzău, Călărași, Caraș-Severin, Cluj, Constanța, Covasna, Dâmbovița, Dolj, Galați, Giurgiu, Gorj, Harghita, Hunedoara, Ialomița, Iași, Ilfov, Maramureș, Mehedinți, Mureș, Neamț, Olt, Prahova, Sălaj, Satu Mare, Sibiu, Suceava, Teleorman, Timiș, Tulcea, Vâlcea, Vaslui, Vrancea

## API Resurse

- **JSON API:** https://www.meteoromania.ro/wp-json/meteoapi/v2/avertizari-generale
- **HTML Pagina:** https://www.meteoromania.ro/avertizari/
- **Hărți SVG:** https://www.meteoromania.ro/wp-content/plugins/meteo/harti/harta.svg.php?id_avertizare={ID}

## Contribuții

Contribuțiile sunt binevenite! Pentru bug-uri sau sugestii, deschide issue pe GitHub.

## Licență

MIT License - Vezi LICENSE file pentru detalii

## Disclaimer

Această integrare este o aplicație de terță parte și nu este afiliată oficial cu ANM. Utilizează datele publice disponibile din website-ul ANM.
