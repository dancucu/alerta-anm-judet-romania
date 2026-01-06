"""Script pentru verificarea culorii județului pe harta ANM."""
import sys
import requests
import json
import xml.etree.ElementTree as ET
import re


def normalize_color(color_str):
    """Transformă orice cod de culoare în standardul nostru."""
    if not color_str:
        return None
    
    s = color_str.lower().replace(" ", "")
    
    # Culori AVERTIZARE
    if '#ffff00' in s or 'rgb(255,255,0)' in s:
        return 'galben'
    if '#ff6600' in s or '#ff9900' in s or '#e67e22' in s or 'rgb(255,102,0)' in s or 'rgb(255,127,0)' in s:
        return 'portocaliu'
    if '#ff0000' in s or 'rgb(255,0,0)' in s:
        return 'rosu'
    
    # Culori INFORMARE (Gri-uri folosite de ANM)
    if '#b4b4b4' in s or '#cccccc' in s or '#999999' in s or 'rgb(180,180,180)' in s:
        return 'informare'
    
    # Dacă e 'none' sau alb, e verde (fără nimic)
    if 'none' in s or '#ffffff' in s or 'rgb(255,255,255)' in s:
        return 'verde'
    
    return None


def check_map(map_id, judet_cod='GL'):
    """Verifică culoarea județului pe harta ANM."""
    url = f"https://www.meteoromania.ro/wp-content/plugins/meteo/harti/harta.svg.php?id_avertizare={map_id}"
    try:
        response = requests.get(url, timeout=10, verify=False)
        if response.status_code != 200:
            return "eroare_http"

        content = response.text
        
        # 1. PARSARE CSS
        css_map = {}
        matches = re.findall(r'\.([a-zA-Z0-9_\-]+)[^{]*\{[^}]*fill:\s*([^;}]+)', content)
        for cls, color in matches:
            css_map[cls] = color.strip()

        # 2. CURĂȚENIE XML
        content = re.sub(r'\sxmlns="[^"]+"', '', content, count=1)
        content = re.sub(r'\sxmlns:xlink="[^"]+"', '', content, count=1)
        
        try:
            root = ET.fromstring(content)
        except:
            return "eroare_xml"

        # 3. CĂUTARE JUDEȚ
        target_id = f'conturJudet{judet_cod}'
        found_element = None
        for element in root.iter():
            if element.get('id') == target_id:
                found_element = element
                break
        
        if not found_element:
            return "verde"

        # 4. DETERMINARE CULOARE
        # A. Style inline
        style = found_element.get('style', '')
        if 'fill:' in style:
            match = re.search(r'fill:\s*([^;]+)', style)
            if match:
                detected = normalize_color(match.group(1))
                if detected:
                    return detected

        # B. Clase
        class_str = found_element.get('class', '')
        classes = class_str.split(' ')
        
        for cls in classes:
            cls = cls.strip()
            if cls in css_map:
                raw_color = css_map[cls]
                detected = normalize_color(raw_color)
                if detected:
                    return detected
        
        return "verde"

    except Exception as e:
        return "eroare_script"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"date_harti": {}}))
        sys.exit()

    ids_input = sys.argv[1]
    judet_cod = sys.argv[2] if len(sys.argv) > 2 else 'GL'
    
    id_list = [x.strip() for x in ids_input.split(',') if x.strip()]
    
    results = {}
    for m_id in id_list:
        val = check_map(m_id, judet_cod)
        results[m_id] = val
        
    print(json.dumps({"date_harti": results}))
