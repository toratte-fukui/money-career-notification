import logging
import re
import tempfile
import time
import traceback

import requests
import yaml
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ロガー設定
logger = logging.getLogger(__name__)

for handler in logger.handlers:
    logger.removeHandler(handler)

handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s (%(levelname)s) %(message)s", datefmt="[%Y/%m/%d %H:%M:%S]"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def send_chatwork_message(api_token, room_id, message):
    headers = {"X-ChatWorkToken": api_token}
    payload = {"body": message}
    response = requests.post(
        f"https://api.chatwork.com/v2/rooms/{room_id}/messages",
        headers=headers,
        data=payload,
    )

    if response.status_code == 200:
        logger.info(f"ChatWorkメッセージ送信: {message}")
    else:
        logger.error(
            f"ChatWorkメッセージ失敗: {response.status_code} - {response.text}"
        )


def upload_screenshot_to_chatwork(api_token, room_id):
    # スクリーンショット保存
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        tmppath = tmpfile.name
        if not driver.save_screenshot(tmppath):
            send_chatwork_message(
                api_token,
                ROOM_ID,
                "!!!ERROR!!! 想定外のエラーでスクリーンショットの保存に失敗しました。",
            )

        # ChatWorkにスクリーンショットをアップロード
        headers = {"X-ChatWorkToken": api_token}
        files = {"file": open(tmppath, "rb")}
        response = requests.post(
            f"https://api.chatwork.com/v2/rooms/{room_id}/files",
            headers=headers,
            files=files,
        )
        if response.status_code == 200:
            logger.info("スクリーンショットのアップロードに成功しました。")
        else:
            raise Exception(
                f"スクリーンショットのアップロードに失敗しました: {response.status_code} - {response.text}\n"
            )


def save_error_log():
    """エラーメッセージをログファイルに保存"""
    with open(f"{time.strftime('%Y%m%d%H%M%S_log.txt')}", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    print(traceback.format_exc())


def find_element_in_all_iframes(xpath, max_depth=5, current_depth=0):
    def condition(driver: webdriver.Chrome):
        if current_depth >= max_depth:
            return None

        # 現在のフレームで要素を検索
        try:
            elem = driver.find_element(By.XPATH, xpath)
            if elem:
                return elem
        except Exception:
            pass

        # 現在のフレーム内のiframeを取得
        iframes = driver.find_elements(By.TAG_NAME, "iframe")

        for iframe in iframes:
            logger.info(f"探索中のiframe: {iframe.get_attribute('src') or 'N/A'}")
            try:
                driver.switch_to.frame(iframe)
                elem = find_element_in_all_iframes(
                    driver, xpath, max_depth, current_depth + 1
                )
                if elem:
                    return elem
            except Exception:
                logger.error("iframe探索失敗")
            finally:
                driver.switch_to.default_content()  # ネスト対応のため、再帰のたびにトップに戻す

        return False

    return condition


def find_new_jobs_element(driver: webdriver.Chrome, new_job_text: str) -> int | None:
    """新着案件の数を返す"""
    logger.info("新着案件の要素を検索")
    body_text = ""
    try:
        elem = WebDriverWait(driver, 5).until(
            find_element_in_all_iframes(f"//p[contains(text(), '{new_job_text}')]")
        )
    except Exception:
        logger.info("XPATHで検索")
        elem = driver.find_element(
            By.XPATH,
            '//*[@id="app"]/div/div/div[1]/div[2]/div[2]/div/div[3]/div[2]/div/div/div/div/div/p',
        )

    try:
        # 調査用にDOM構造を保存
        with open("logs/dom.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception:
        pass

    body_text = elem.text
    logger.info(body_text)
    match = re.search(rf"{new_job_text}.*(\d+)", body_text)
    if match:
        return int(match.group(1))
    return None


def click_update_button(driver: webdriver.Chrome, update_button_text: str):
    """更新ボタンをクリックする"""
    if not update_button_text:
        raise ValueError("更新ボタンのテキストが指定されていません")

    logger.info("「新規案件を更新」ボタンをクリック")
    elem = None
    try:
        elem = WebDriverWait(driver, 5).until(
            driver.find_element(
                By.XPATH, f"//p[contains(text(), '{update_button_text}')]"
            )
        )
    except Exception:
        elem = driver.find_element(
            By.XPATH,
            '//*[@id="app"]/div/div/div[1]/div[2]/div[2]/div/div[1]/div/button/div/p',
        )

    elem.click()
    logger.info("クリック成功")
    return


if __name__ == "__main__":
    # 設定をsettings.yamlから読み込む
    try:
        with open("settings.yaml", "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
        URL = settings["URL"]  # ログインページURL
        ROOM_ID = settings["ROOM_ID"]  # ChatWorkルームID
        ID = settings["ID"]  # money-careerのID
        PASS = settings["PASSWORD"]  # money-careerのパスワード
        MESSAGE = settings["MESSAGE"]  # 通知メッセージ
        API_KEY = settings["API_KEY"]  # ChatWork APIキー
        INTERVAL_SEC = settings["INTERVAL"]  # 監視間隔（秒）
        NEW_JOB_TEXT = settings["NEW_JOB_TEXT"]  # 新着案件のテキスト
        UPDATE_BUTTON_TEXT = settings["UPDATE_BUTTON_TEXT"]  # 更新ボタンのテキスト
    except Exception:
        logger.error("設定ファイルの読み込みに失敗しました:")
        logger.error(traceback.format_exc())
        input("Enterキーを押して終了...")
        exit(1)

    # chrome起動
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)

    try:
        time.sleep(5)
        logger.info("Chrome起動")
        driver.get(URL)
        time.sleep(1)

        logger.info("ログインボタンクリック")
        button = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.TAG_NAME, "button")
        )
        button.click()

        logger.info("ID入力")
        username_input = WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.ID, "username")
        )
        username_input.clear()
        username_input.send_keys(ID)
        logger.info("パスワード入力")
        password_input = driver.find_element(By.ID, "password")
        password_input.clear()
        password_input.send_keys(PASS)
        logger.info("ログインボタンクリック")
        submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        submit_button.click()

        logger.info("//////////////////////////////////////////////////////////////")
        logger.info("// !!!ユーザー操作待機中!!!")
        logger.info("// 監視対象ページを開いてからEnterキーを押してください")
        logger.info("// 「監視開始」と表示されない場合、再度押してください")
        logger.info("//////////////////////////////////////////////////////////////")
        input()
        logger.info("監視開始")

        time.sleep(1)

        old_jobs = None
        while True:
            try:
                # 新着案件数の確認
                new_jobs = find_new_jobs_element(driver, NEW_JOB_TEXT)

                if old_jobs and new_jobs > old_jobs:
                    logger.info(f"新着案件数が増加: {old_jobs}件 -> {new_jobs}件")
                    # 差分を通知
                    send_chatwork_message(
                        API_KEY, ROOM_ID, f"{MESSAGE} ({str(new_jobs)}件)"
                    )
                    upload_screenshot_to_chatwork(API_KEY, ROOM_ID)

                old_jobs = new_jobs

            except TimeoutException:
                logger.error("新着案件の要素を正しく見つけられませんでした。")
                break

            time.sleep(int(INTERVAL_SEC))

            click_update_button(driver, UPDATE_BUTTON_TEXT)

    except Exception as e:
        # エラーをログに保存
        current_time = time.strftime("%Y%m%d%H%M%S")
        with open(f"logs/{current_time}_log.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print(traceback.format_exc())

        with open(f"logs/{current_time}_dom.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
            logger.error(
                f"エラー発生時のDOM構造をlogs/{current_time}.htmlに保存しました"
            )

        # ChatWorkにエラーメッセージを送信
        send_chatwork_message(
            API_KEY, ROOM_ID, f"!!!ERROR!!! {str(e)}\n{traceback.format_exc()}"
        )

    finally:
        driver.quit()
        logger.info("Chrome終了")
        input("Enterキーを押して終了...")
