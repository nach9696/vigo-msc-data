"""
MSC Vigo Scraper — adaptado para GitHub Actions
Guarda el resultado en barcos_msc.json
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
import time
import json
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIGURACIÓN HEADLESS para GitHub Actions
# ---------------------------------------------------------------------------
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/122.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=options)
wait   = WebDriverWait(driver, 30)
barcos = []

try:
    print("🌐 Cargando MSC Schedule...")
    driver.get("https://www.msc.com/en/search-a-schedule")
    time.sleep(4)

    # 1. Aceptar cookies
    try:
        cookie_btn = wait.until(EC.element_to_be_clickable((By.XPATH,
            "//button[contains(translate(., 'ACEPTAR', 'aceptar'), 'ceptar') "
            "or contains(translate(., 'ACCEPT', 'accept'), 'ccept')]"
        )))
        cookie_btn.click()
        print("✅ Cookies aceptadas")
        time.sleep(1)
    except:
        print("⚠️  Sin aviso de cookies")

    # 2. Cerrar popup
    try:
        close_popup = driver.find_element(By.XPATH,
            "//button[@aria-label='Close' or @aria-label='close' "
            "or contains(@class, 'close')]"
        )
        driver.execute_script("arguments[0].click();", close_popup)
        print("✅ Popup cerrado")
        time.sleep(1)
    except:
        print("⚠️  Sin popup")

    # 3. Pestaña Arrivals/Departures
    print("🔍 Buscando pestaña Arrivals/Departures...")
    xpath_tab = ("//*[translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                 "'abcdefghijklmnopqrstuvwxyz') = 'arrivals/departures' "
                 "or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                 "'abcdefghijklmnopqrstuvwxyz'), 'arrivals/departures')]")
    arrivals_tab = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_tab)))
    driver.execute_script("arguments[0].click();", arrivals_tab)
    print("✅ Pestaña seleccionada")
    time.sleep(3)

    # 4. Campo de puerto
    campo_puerto = None
    for placeholder in ["Enter a port", "Port", "From", "Origen", "Puerto"]:
        try:
            xpath_input = (f"//input[contains(translate(@placeholder, "
                           f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                           f"'{placeholder.lower()}')]")
            campo_puerto = wait.until(EC.presence_of_element_located((By.XPATH, xpath_input)))
            print(f"✅ Campo encontrado: '{placeholder}'")
            break
        except:
            continue

    if not campo_puerto:
        campo_puerto = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@type='text' and not(@hidden)]")
        ))

    # 5. Escribir Vigo
    driver.execute_script("arguments[0].click();", campo_puerto)
    time.sleep(0.5)
    campo_puerto.clear()
    campo_puerto.send_keys("Vigo")
    driver.execute_script(
        "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
        campo_puerto
    )
    print("✅ Escrito 'Vigo'")
    time.sleep(3)

    # 6. Seleccionar sugerencia VIGO / ESVGO
    seleccionado = False
    try:
        todos = driver.find_elements(By.XPATH,
            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'vigo')]"
        )
        for el in todos:
            rect = driver.execute_script(
                "return arguments[0].getBoundingClientRect();", el
            )
            if rect['width'] > 0 and rect['height'] > 0:
                ActionChains(driver).move_to_element(el).pause(0.3).click().perform()
                print("✅ Sugerencia seleccionada")
                seleccionado = True
                time.sleep(3)
                break
    except Exception as e:
        print(f"⚠️  Estrategia sugerencia fallida: {e}")

    if not seleccionado:
        campo_puerto.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.5)
        campo_puerto.send_keys(Keys.RETURN)
        print("✅ Sugerencia via Arrow Down + Enter")
        time.sleep(3)

    # 7. Pulsar lupa
    try:
        lupa = driver.execute_script("""
            const btns = document.querySelectorAll('button');
            for (let btn of btns) {
                let rect = btn.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && btn.querySelector('svg')) {
                    if (rect.top > 200 && rect.top < 700) return btn;
                }
            }
            return null;
        """)
        if lupa:
            ActionChains(driver).move_to_element(lupa).pause(0.3).click().perform()
            print("✅ Lupa pulsada")
        else:
            campo_puerto.send_keys(Keys.RETURN)
    except:
        campo_puerto.send_keys(Keys.RETURN)

    # 8. Esperar resultados
    print("⏳ Esperando tabla de resultados...")
    try:
        wait.until(EC.presence_of_element_located((By.XPATH,
            "//*[contains(text(),'Vessel') and contains(text(),'Voyage')]"
        )))
        print("✅ Tabla detectada")
    except:
        print("⚠️  Timeout esperando tabla, continuando...")
    time.sleep(5)

    # 9. Extraer y parsear
    try:
        main    = driver.find_element(By.XPATH, "//main")
        texto   = main.text
    except:
        texto   = driver.find_element(By.TAG_NAME, "body").text

    basura = {
        'schedules', 'point-to-point', 'vessel', 'arrivals/departures',
        'find a schedule', 'sort by', 'arrivals', 'port',
        'estimated time of arrival', 'service',
        'direct integrations solutions', 'country-location / local office',
        'doing business together', 'solutions', 'local information',
        'e-business', 'sustainability', 'get to know us', 'newsroom',
        'events', 'blog', 'careers', 'contact us', 'headquarters:',
        'chemin rieu 12, 1208 geneva', 'switzerland',
        'personal data request', "carrier's terms & conditions",
        'eu commitments', 'code of conduct', 'certifications',
        'speak up line', 'very poor', 'excellent', 'next', 'mymsc',
        'search', 'tracking', 'en', 'office details',
        'vigo, spain (esvgo)', '+34 963359100', '+41 227038888'
    }

    lineas        = [l.strip() for l in texto.split('\n') if l.strip()]
    lineas_limpias = [l for l in lineas if l.lower() not in basura and len(l) > 2]

    # Formatos de fecha que usa MSC
    formatos_eta = [
        "%a, %d %b %Y %H:%M",
        "%d %b %Y %H:%M",
        "%a, %d %b %Y",
        "%d %b %Y",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M",
    ]

    def parsear_eta(eta_str):
        eta_clean = re.sub(r'\s+', ' ', eta_str.strip())
        eta_clean = re.sub(r'^[A-Za-z]{3},?\s*', '', eta_clean).strip()
        for fmt in formatos_eta:
            try:
                return datetime.strptime(eta_clean, fmt)
            except:
                continue
        m = re.search(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', eta_str)
        if m:
            try:
                return datetime.strptime(
                    f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y"
                )
            except:
                pass
        return None

    ahora = datetime.now()
    i = 0
    while i < len(lineas_limpias):
        if lineas_limpias[i] == 'Vigo':
            try:
                j = i + 1
                if j < len(lineas_limpias) and 'ESVGO' in lineas_limpias[j]:
                    j += 1
                nombre   = lineas_limpias[j]     if j     < len(lineas_limpias) else ''
                codigo   = lineas_limpias[j + 1] if j + 1 < len(lineas_limpias) else ''
                eta_str  = lineas_limpias[j + 2] if j + 2 < len(lineas_limpias) else ''
                servicio = ''
                if j + 3 < len(lineas_limpias) and lineas_limpias[j + 3] != 'Vigo':
                    servicio = lineas_limpias[j + 3]
                    i = j + 4
                else:
                    i = j + 3

                if nombre and eta_str:
                    f_obj = parsear_eta(eta_str)
                    if f_obj and f_obj >= ahora:
                        barcos.append({
                            'nombre':   nombre.strip().upper(),
                            'dwt':      'N/A',
                            'ano':      'N/A',
                            'llegada':  f_obj.strftime("%d/%m/%Y %H:%M"),
                            'eta_raw':  eta_str,
                            'servicio': servicio,
                            'estado':   'PROGRAMADO (MSC)'
                        })
            except:
                i += 1
        else:
            i += 1

    # 10. Guardar JSON
    output = {
        'ultima_actualizacion': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        'total':   len(barcos),
        'barcos':  barcos
    }
    with open('barcos_msc.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(barcos)} barcos MSC guardados en barcos_msc.json")
    for b in barcos:
        print(f"  🚢 {b['nombre']} — {b['llegada']}")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    # Guardar JSON vacío para que el servidor no falle al leerlo
    with open('barcos_msc.json', 'w') as f:
        json.dump({
            'ultima_actualizacion': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            'total':  0,
            'barcos': [],
            'error':  str(e)
        }, f)

finally:
    driver.quit()
