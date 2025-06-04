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


def find_new_jobs_element(driver: webdriver.Chrome) -> int | None:
    """新着案件の数を返す"""
    pattern = re.compile(r"新着案件[:：]\s*\d+\s*件")
    elements = driver.find_elements(By.XPATH, "//*[contains(text(),'新着案件')]")
    for el in elements:
        text = el.text.replace("\u3000", " ")  # 全角スペース→半角スペース
        match = pattern.search(text)
        if match:
            logger.info(text)
            number = re.search(r"\d+", match.group())
            return int(number.group())
    return None


if __name__ == "__main__":
    # 設定をsettings.yamlから読み込む
    try:
        with open("settings.yaml", "r") as f:
            settings = yaml.safe_load(f)
        URL = settings["URL"]  # ログインページURL
        ROOM_ID = settings["ROOM_ID"]  # ChatWorkルームID
        MESSAGE = settings["MESSAGE"]  # 通知メッセージ
        API_KEY = settings["API_KEY"]  # ChatWork APIキー
        INTERVAL_SEC = settings["INTERVAL"]  # 監視間隔（秒）
    except Exception as e:
        logger.error(f"設定ファイルの読み込みに失敗しました: {e}")
        raise e

    # chrome起動
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)

    try:
        logger.info("Chrome起動")
        driver.get(URL)
        input(
            "/////////////////////////////////////////////////////////////////\n"
            + "//\n"
            + "// ユーザー操作待機中\n"
            + "// 監視対象ページを開いてからEnterキーを押してください...\n"
            + "//\n"
            "/////////////////////////////////////////////////////////////////"
        )
        logger.info("監視開始")

        old_jobs = None
        while True:
            try:
                # 新着案件数の確認
                new_jobs = WebDriverWait(driver, 1).until(
                    lambda d: find_new_jobs_element(d)
                )

                if old_jobs and new_jobs == old_jobs:
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

            update_buttons = driver.find_elements(
                By.XPATH, "//*[contains(text(),'新規案件を更新')]"
            )
            if update_buttons:
                update_buttons[0].click()
                logger.info("「新規案件を更新」ボタンをクリックしました。")
            else:
                raise Exception("「新規案件を更新」ボタンのクリックに失敗しました")

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
