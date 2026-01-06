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

1. Accesează directorul `custom_components` din Home Assistant:
   ```bash
   cd /root/homeassistant/custom_components
   # sau pe sistem standard
   cd ~/.homeassistant/custom_components
   ```

2. Clonează repository-ul:
   ```bash
   git clone https://github.com/dancucu/alerta-anm-judet-romania.git alerta_anm_judet_romania
   ```

3. Restart Home Assistant

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

## Utilizare

### Monitorizare în Lovelace

Adaugă cartă YAML cu template Lovelace:

```yaml
type: custom:fold-entity-row
padding: 0
clickable: true
head:
  type: custom:button-card
  entity: sensor.avertizari_meteo_anm
  name: AVERTIZARE METEO
  icon: mdi:alert
  show_name: true
  show_icon: true
  show_state: false
  tap_action:
    action: none
  styles:
    card:
      - background-color: transparent
      - box-shadow: none
      - padding: 0px
      - margin: 0px
      - pointer-events: none
    icon:
      - width: 22px
      - height: 22px
      - color: |
          [[[
            const colorSensors = Object.keys(states).filter(key =>
              key.startsWith('sensor.culoare_harta_') && states[key] && states[key].state !== 'unavailable'
            );
            const colorEntityId = colorSensors.length > 0 ? colorSensors[0] : null;
            let status = colorEntityId ? states[colorEntityId].state : 'portocaliu';
            
            const colorMap = {
              'galben': '#f1c40f',
              'portocaliu': '#e67e22',
              'rosu': '#e74c3c',
              'informare': '#3498db',
              'verde': '#27ae60'
            };
            return colorMap[status] || '#f39c12';
          ]]]
    name:
      - font-weight: 900
      - font-size: 16px
      - text-transform: uppercase
      - color: |
          [[[
            const colorSensors = Object.keys(states).filter(key =>
              key.startsWith('sensor.culoare_harta_') && states[key] && states[key].state !== 'unavailable'
            );
            const colorEntityId = colorSensors.length > 0 ? colorSensors[0] : null;
            let status = colorEntityId ? states[colorEntityId].state : 'portocaliu';
            
            const colorMap = {
              'galben': '#f1c40f',
              'portocaliu': '#e67e22',
              'rosu': '#e74c3c',
              'informare': '#3498db',
              'verde': '#27ae60'
            };
            return colorMap[status] || '#f39c12';
          ]]]
entities:
  - type: custom:button-card
    entity: sensor.mesaj_meteo_galati
    # ... (vezi fișierul lovelace_card.yaml pentru template complet)
```

### Automatizări Exemple

**Notificare la alertă roșu:**
```yaml
automation:
  - alias: "Alertă ANM - Cod Roșu"
    trigger:
      platform: state
      entity_id: sensor.culoare_harta_galati
      to: "rosu"
    action:
      service: notify.mobile_app_telefon
      data:
        title: "⚠️ ALERTĂ METEO COD ROȘU"
        message: "{{ state_attr('sensor.mesaj_meteo_galati', 'mesaj_complet') }}"
```

## Dependințe

- Home Assistant 2023.11+
- `requests` (instalat automat)
- Custom cards:
  - `custom:button-card` (https://github.com/custom-cards/button-card)
  - `custom:fold-entity-row` (https://github.com/thomasloven/lovelace-fold-entity-row)

## Probleme Frecvente

### "Integrare nu se găsește"
- Restart Home Assistant după instalare
- Verifică că folder-ul `alerta_anm_judet_romania` este în `custom_components`

### "Senzori nu se actualizează"
- Verifică intervalul de actualizare (minim 5 minute)
- Controlează conexiunea la internet și website-ul ANM

### "Card Lovelace arată gol"
- Instalează `custom:button-card` și `custom:fold-entity-row`
- Reload browser (Ctrl+Shift+R)

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
alerta_anm_judet_romania/
├── __init__.py           # Setup integrare
├── config_flow.py        # Configurare UI
├── const.py              # Constante (județe, URL-uri)
├── sensor.py             # Definiția senzorilor
├── check_map.py          # Script detecție culoare hartă
├── manifest.json         # Metadate integrare
├── lovelace_card.yaml    # Template card Lovelace
└── README.md             # Acest fișier
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
