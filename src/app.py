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
    with open(f"{time.strftime('%Y%m%d%H%M%S_log.txt')}", "w") as f:
        f.write(traceback.format_exc())
    print(traceback.format_exc())


def find_new_jobs_element(driver: webdriver.Chrome, new_job_text: str) -> int | None:
    """新着案件の数を返す"""
    # 「新着案件：X件」というテキストを含む要素を探す
    body_text = driver.find_element(By.TAG_NAME, "body").text
    with open(f"{time.strftime('logs/%Y%m%d%H%M%S_body_text.txt')}", "w") as f:
        f.write(body_text)
    match = re.search(rf"{new_job_text}.*(\d+)件", body_text)
    if match:
        return int(match.group(1))
    return None


def click_update_button(driver: webdriver.Chrome, update_button_text: str):
    """更新ボタンをクリックする"""
    elems = driver.find_elements(By.TAG_NAME, "p")
    for elem in elems:
        print(f"div.text: {elem.text}")
        print("---")
        if update_button_text in elem.text:
            elem.click()
            logger.info("「新規案件を更新」ボタンをクリックしました。")
            return

    raise Exception("「新規案件を更新」ボタンの要素が見つかりませんでした")


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

    try:
        # chrome起動
        options = webdriver.ChromeOptions()
        driver = webdriver.Chrome(options=options)

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
        # submit_button.click()

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
                new_jobs = WebDriverWait(driver, 10).until(
                    lambda d: find_new_jobs_element(d, NEW_JOB_TEXT)
                )
                logger.info(f"新着案件: {new_jobs}件")

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
        with open(f"{time.strftime('logs/%Y%m%d%H%M%S_log.txt')}", "w") as f:
            f.write(traceback.format_exc())
        print(traceback.format_exc())

        # ChatWorkにエラーメッセージを送信
        send_chatwork_message(
            API_KEY, ROOM_ID, f"!!!ERROR!!! {str(e)}\n{traceback.format_exc()}"
        )

    finally:
        driver.quit()
        logger.info("Chrome終了")
        input("Enterキーを押して終了...")
