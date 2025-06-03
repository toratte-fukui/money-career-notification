import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# 設定
url = "https://www.lancers.jp/user/login?ref=header_menu"  # ここにログインページのURLを入力
email = "your_email@example.com"  # ここにメールアドレスを入力
password = "your_password"  # ここにパスワードを入力

# ドライバーの起動（Chromeの場合）
driver = webdriver.Chrome()

try:
    driver.get(url)
    time.sleep(2)  # ページの読み込み待ち

    # メールアドレス入力
    email_input = driver.find_element(By.ID, "UserEmail")
    email_input.send_keys(email)

    # パスワード入力
    password_input = driver.find_element(By.ID, "UserPassword")
    password_input.send_keys(password)

    # フォーム送信（エンターキー）
    password_input.send_keys(Keys.RETURN)

    driver.save_screenshot("screenshot.png")

    time.sleep(5)  # ログイン後のページ確認用
finally:
    driver.quit()
