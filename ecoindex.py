from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_encode_score(url_test):


    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 30)

    # 1. Aller sur EcoIndex
    driver.get("https://www.ecoindex.fr/")

    # 2. Récupérer l’input #siteurl
    champ = wait.until(
        EC.presence_of_element_located((By.ID, "siteurl"))
    )

    # 3. Saisir l’URL
    champ.clear()
    champ.send_keys(url_test)

    # 4. Valider avec ENTER
    champ.send_keys(Keys.ENTER)

    # 5. Attendre la popup de chargement (classe .loader ou .loading)
    try:
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".loader, .loading"))
        )
    except:
        pass

    # 6. Attendre la disparition du loader (si présent)
    try:
        wait.until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".loader, .loading"))
        )
    except:
        pass

    # 7. Attendre la redirection vers /resultat/?id=
    wait.until(lambda d: "/resultat/?" in d.current_url)

    print("URL résultat :", driver.current_url)

    # 8. Attendre l’apparition du score
    score_span = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "span[data-int='score']"))
    )

    score = score_span.text

    driver.quit()
    return score