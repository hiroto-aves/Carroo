from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
import time

def post_job_to_trabox(form_data):
    """
    トラボックスのWebサイトに案件情報を投稿する関数 (Seleniumを使用)
    """
    # ここにダウンロードしたchromedriverの絶対パスを記述してください
    # 例: service = Service('C:\\Users\\YourUsername\\Downloads\\chromedriver.exe')
    # 例: service = Service('/Users/YourUsername/Downloads/chromedriver')
    chrome_driver_path = '/Applications/chromedriver'
    YOUR_TRABOX_USERNAME = "hrt_takeuchi@takeuchiunso.com"
    YOUR_TRABOX_PASSWORD = "6JizDowZhP3i"
    
    # オプションを設定して、ブラウザを非表示で実行 (ヘッドレスモード)
    options = Options()
    # options.add_argument('--headless') # 開発中はコメントアウトして、ブラウザの動きを確認するのがおすすめです
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    try:
        service = Service(executable_path=chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)

        # 1. ログイン処理
        print("トラボックスにログイン中...")
        driver.get("https://www.trabox.com/login")
        time.sleep(5)  # ログイン完了を待つ
        driver.find_element(By.NAME, 'loginid').send_keys(YOUR_TRABOX_USERNAME)  # トラボックスのユーザー名
        driver.find_element(By.NAME, 'loginpwd').send_keys(YOUR_TRABOX_PASSWORD)  # トラボックスのパスワード
        # ログインボタンをテキストで特定
        driver.find_element(By.XPATH, "//button/span[text()='ログイン']").click()
        time.sleep(5)  # ログイン完了を待つ

        if "login" in driver.current_url.lower():
            print("トラボックスへのログインに失敗しました。ユーザー名かパスワードを確認してください。")
            driver.quit()
            return False

        # 2. 荷物登録ページに移動
        print("荷物登録ページに移動中...")
        driver.get("https://www.trabox.com/baggage/register")
        time.sleep(5)

        # 3. フォームへの入力
        print("フォームに入力中...")
         # 積地情報
        driver.find_element(By.NAME, 'Loading_Date').send_keys(form_data['loading_date'])
        driver.find_element(By.NAME, 'Loading_Time').send_keys(form_data['loading_time'])
        driver.find_element(By.NAME, 'Loading_Address_Pref').send_keys(form_data['loading_prefecture'])
        driver.find_element(By.NAME, 'Loading_Address_City').send_keys(form_data['loading_city'])
        driver.find_element(By.NAME, 'Loading_Address_Detail').send_keys(form_data['loading_address'])

        # 卸地情報
        driver.find_element(By.NAME, 'Unloading_Date').send_keys(form_data['unloading_date'])
        driver.find_element(By.NAME, 'Unloading_Time').send_keys(form_data['unloading_time'])
        driver.find_element(By.NAME, 'Unloading_Address_Pref').send_keys(form_data['unloading_prefecture'])
        driver.find_element(By.NAME, 'Unloading_Address_City').send_keys(form_data['unloading_city'])
        driver.find_element(By.NAME, 'Unloading_Address_Detail').send_keys(form_data['unloading_address'])

        # 荷物情報
        Select(driver.find_element(By.NAME, 'Consolidation_Flg')).select_by_visible_text(form_data['consolidation_item'])
        Select(driver.find_element(By.NAME, 'Cargo_Category_Div')).select_by_visible_text(form_data['transport_category'])
        Select(driver.find_element(By.NAME, 'Cargo_Shape_Div')).select_by_visible_text(form_data['item_shape'])
        driver.find_element(By.NAME, 'Cargo_Weight').send_keys(form_data['weight'])
        Select(driver.find_element(By.NAME, 'Desired_Car_Size')).select_by_visible_text(form_data['vehicle_size'])
        Select(driver.find_element(By.NAME, 'Desired_Car_Type')).select_by_visible_text(form_data['desired_vehicle_type'])
        Select(driver.find_element(By.NAME, 'Desired_Car_Grade')).select_by_visible_text(form_data['vehicle_grade'])
        driver.find_element(By.NAME, 'Desired_Car_Equipments').send_keys(form_data['required_equipment'])
        driver.find_element(By.NAME, 'Desired_Price').send_keys(form_data['desired_fare'] if form_data['fare_option'] == '金額' else '')
        if form_data['fare_option'] == '要相談':
            driver.find_element(By.NAME, 'Desired_Price_Consultation_Flg').click()
        Select(driver.find_element(By.NAME, 'Highway_Fee_Div')).select_by_visible_text(form_data['toll_fee'])
        Select(driver.find_element(By.NAME, 'Insurance_Fee_Div')).select_by_visible_text(form_data['insurance'])
        driver.find_element(By.NAME, 'Cargo_Quantity').send_keys(form_data['cases'])
        driver.find_element(By.NAME, 'Note').send_keys(form_data['notes'])
        driver.find_element(By.NAME, 'Representative').send_keys(form_data['contact_person'])
        driver.find_element(By.NAME, 'Telephone_Number').send_keys(form_data['phone_number'])

        # 4. 投稿ボタンをクリック
        driver.find_element(By.NAME, 'btnRegister').click()
        time.sleep(5)  # 登録完了を待つ

        print("トラボックスへの投稿が成功しました。")
        return True

    except (WebDriverException, NoSuchElementException, TimeoutException) as e:
        print(f"トラボックスへの投稿に失敗しました: {e}")
        return False
    finally:
        if 'driver' in locals() and driver:
            driver.quit()