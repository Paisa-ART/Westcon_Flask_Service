from flask import Flask, request, send_file, jsonify
import os
import shutil
import base64
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import tempfile
from pydub import AudioSegment

app = Flask(__name__)

AUTOMATION_PROFILE = os.path.expanduser("~/.chrome_automation_profile/Profile_automation")
RUN_BUTTON_XPATH = '/html/body/app-root/ms-app/div/div/div[3]/div/span/ms-speech-prompt/section/div[2]/div/div[2]/ms-run-button/button'
RUN_LABEL_XPATH = "//ms-run-button//span[contains(@class, 'label')]"
TEXTAREA_XPATH = '/html/body/app-root/ms-app/div/div/div[3]/div/span/ms-speech-prompt/section/div[1]/div/textarea'
TITULO_XPATH = "/html/body/app-root/ms-app/div/div/div[3]/div/span/ms-speech-prompt/section/div[1]/div/ms-autosize-textarea/textarea"

def preparar_perfil():
    if not os.path.exists(AUTOMATION_PROFILE):
        os.makedirs(AUTOMATION_PROFILE, exist_ok=True)
    else:
        print("perfil ya existente")

def configurar_driver():
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={os.path.expanduser('~/.chrome_automation_profile')}")
    options.add_argument("--profile-directory=Profile_automation")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")
    return uc.Chrome(version_main=140, options=options)

def esperar_y_click(driver, xpath, timeout=10):
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    driver.execute_script("arguments[0].click();", element)

def generar_audio(driver, texto):
    try:
        textarea = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, TEXTAREA_XPATH))
        )
        textarea.clear()
        textarea.send_keys(texto)
        driver.find_element(By.XPATH, RUN_BUTTON_XPATH).click()
        WebDriverWait(driver, 60).until(
            EC.text_to_be_present_in_element((By.XPATH, RUN_LABEL_XPATH), "Run")
        )
        audio_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "audio[src^='data:audio/wav;base64,']"))
        )
        audio_src = audio_element.get_attribute("src")
        base64_data = audio_src.split(",")[1]
        audio_bytes = base64.b64decode(base64_data)

        return audio_bytes

    except (TimeoutException, NoSuchElementException) as e:
        print(f"Error generando audio: {e}")
        return None


@app.route("/generateAudio", methods=["POST"])
def generate_speech_combined():
    data = request.json
    if not data or "textos" not in data or not isinstance(data["textos"], list):
        return jsonify({"error": "Falta el campo 'textos' en forma de lista mandarlo por favor en JSON"}), 400
    textos = data["textos"]
    preparar_perfil()
    driver = configurar_driver()
    temp_dir = tempfile.mkdtemp()
    combined_audio_path = os.path.join(temp_dir, "combined_audio.wav")
    try:
        driver.get("https://aistudio.google.com/generate-speech")
        esperar_y_click(driver, "//*[contains(text(), 'Single-speaker audio')]")
        esperar_y_click(driver, '//*[@id="mat-select-4"]')
        esperar_y_click(driver, "//*[contains(text(), 'Algenib')]")
        esperar_y_click(driver, "//*[contains(text(), 'Model settings')]")
        slider = driver.find_element(By.CSS_SELECTOR, 'input[type="range"]')
        driver.execute_script("arguments[0].value = 1.35;", slider)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input'));", slider)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", slider)
        titulo = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, TITULO_XPATH))
        )
        titulo.clear()
        titulo.send_keys("Read aloud in a warm, friendly, and exciting tone:")
        combined = AudioSegment.silent(duration=500)
        
        for i, texto in enumerate(textos, start=1):
            print(f"el texto {i}/{len(textos)} se procesando")
            audio_bytes = generar_audio(driver, texto)
            if audio_bytes:
                temp_file_path = os.path.join(temp_dir, f"audio_{i}.wav")
                with open(temp_file_path, "wb") as f:
                    f.write(audio_bytes)
                audio_segment = AudioSegment.from_wav(temp_file_path)
                combined += audio_segment + AudioSegment.silent(duration=500)

        combined.export(combined_audio_path, format="wav")
        return send_file(combined_audio_path, mimetype="audio/wav", as_attachment=True, download_name="combined_audio.wav")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)