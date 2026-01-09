# Exemple de Configurare

Acest director conține fișiere gata configurate pentru integrarea **Alertă ANM Județ România**.

## 📋 Fișiere Disponibile

### 1. Automatizări

#### `automation_notificare_inceput_avertizare.yaml`
**Notificări la Început de Alertă**

Trimite notificări detaliate pe telefon când apare o alertă meteorologică nouă pentru județul tău.

**Caracteristici:**
- ✅ Funcționează automat pentru toate județele (42 + București)
- ✅ Mesaje cu intervale și fenomene meteo
- ✅ Notificări pe iPhone și HTML5
- ✅ Include URL către harta ANM

**Cum se instalează:**
1. Copiază tot conținutul fișierului
2. Mergi în Home Assistant: **Settings** → **Automations & Scenes**
3. Click **+ Create Automation** → butonul **⋮** (trei puncte) → **Edit in YAML**
4. Lipește conținutul copiat
5. Click **Save**

---

#### `automation_notificare_sfarsit_avertizare.yaml`
**Notificări la Încheierea Alertei**

Trimite notificare când alerta meteo s-a terminat și revine starea "liniște".

**Caracteristici:**
- ✅ Notificare clară când alerta expiră
- ✅ Elimină îngrijorările inutile
- ✅ Funcționează pentru toate județele

**Cum se instalează:**
1. Copiază tot conținutul fișierului
2. Mergi în Home Assistant: **Settings** → **Automations & Scenes**
3. Click **+ Create Automation** → butonul **⋮** (trei puncte) → **Edit in YAML**
4. Lipește conținutul copiat
5. Click **Save**

---

### 2. Card Lovelace

#### `lovelace_card.yaml`
**Card Interactiv pentru Dashboard**

Un card complet configurat cu:
- ✅ Titlu colorat dinamic (galben/portocaliu/roșu) pe baza gravității alertei
- ✅ Mesaj meteo formatat cu COD-uri evidențiate
- ✅ Hărți SVG interactive cu detectare automată
- ✅ Design responsive și profesional

**Dependințe necesare:**
Trebuie instalate aceste custom cards prin HACS:
- [custom:button-card](https://github.com/custom-cards/button-card)
- [custom:fold-entity-row](https://github.com/thomasloven/lovelace-fold-entity-row)

**Cum se instalează:**
1. Instalează dependințele din HACS (vezi mai sus)
2. Copiază tot conținutul fișierului `lovelace_card.yaml`
3. Deschide dashboard-ul în Home Assistant
4. Click **Edit Dashboard** (butonul ✏️ din colțul dreapta-sus)
5. Click **+ Add Card** → derulează până jos → **Manual**
6. Lipește conținutul copiat
7. Click **Save**

**📌 Notă:** Cardul nu detectează automat județul configurat în integrare. Trebuie sa modifici numele judetului in toate locurile unde il gasesti in codul cardului. Cel mai simplu o faci cu un editor de text, apeland functia find and replace, slecatand ”galati”.

---

## ⚙️ Personalizare

### Automatizări

Dacă vrei să primești notificări doar pe telefon sau printr-un alt serviciu, editează secțiunea `actions:` din automatizări:

```yaml
actions:
  - action: notify.mobile_app_iphone_tău  # Schimbă cu ID-ul dispozitivului tău
    data:
      title: "🌪️ AVERTIZARE METEO"
      message: "{{ mesaj_formatat }}"
```

### Card Lovelace

Poți modifica culorile în secțiunea `card_mod` editând valorile RGB:

```yaml
# Exemplu pentru galben
{% elif is_state('sensor.culoare_harta_galati', 'galben') %}
  rgb(255, 220, 0)  # Schimbă aceste valori pentru altă nuanță
{% endif %}
```

---

## 🆘 Suport

Dacă întâmpini probleme:
1. Verifică că integrarea este instalată corect
2. Asigură-te că ai selectat județul corect în configurare
3. Pentru automatizări, verifică că serviciul de notificare există
4. Pentru card, confirmă că custom cards sunt instalate

Pentru bug-uri sau întrebări, deschide un [issue pe GitHub](https://github.com/dancucu/alerta-anm-judet-romania/issues).
