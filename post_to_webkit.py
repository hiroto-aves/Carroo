import requests
import xml.etree.ElementTree as ET
import os
import re 
import json
import math
# 🚨 修正: webkit_codes.pyからすべての必要なマップとヘルパー関数をインポート 🚨
from .webkit_codes import (
    ITEM_CATEGORY_MAP, ITEM_SHAPE_MAP, VEHICLE_TYPE_MAP, CARKIND_MAP, MIX_MAP, 
    PREF_NAME_TO_CODE, CITY_NAME_TO_CODE, get_car_height_code
)

# WebKITの認証情報とエンドポイント
API_ENDPOINT = "https://www.wkit.jp/api/LoadInfo"
API_KEY = "RhpQw9t77MGNLQNOa28A"
PERSON_ID = "27113000530001"
MEMBER_ID = "271130005300" 
RESPONSE_FILE = 'webkit_response.xml'

# ----------------------------------------------------
# 関数定義
# ----------------------------------------------------
def get_city_code(city_name):
    """ 市区町村名からWebKITのコードを取得する """
    # index.htmlのプルダウンから送られてきた市区町村名をキーとしてコードを取得
    return CITY_NAME_TO_CODE.get(city_name, '')

def post_job_to_webkit(form_data):
    """
    WebkitのXML形式で案件情報を投稿する関数
    """
    
    # フォームデータをAPIが必要とするコード値に変換
    load_pref_code = PREF_NAME_TO_CODE.get(form_data['loading_prefecture'], '')
    dest_pref_code = PREF_NAME_TO_CODE.get(form_data['unloading_prefecture'], '')
    
    # 地名コードの取得 (フォームのvalue=市区町村名からコードを取得)
    load_area_code = get_city_code(form_data['loading_city'])
    dest_area_code = get_city_code(form_data['unloading_city'])

    # その他のコードを取得
    load_kind_code = ITEM_CATEGORY_MAP.get(form_data['transport_category'], '21')
    package_type_code = ITEM_SHAPE_MAP.get(form_data['item_shape'], '10')
    car_kind_type_code = VEHICLE_TYPE_MAP.get(form_data['desired_vehicle_type'], '13')
    car_kind_code = CARKIND_MAP.get(form_data['vehicle_size'], '1')
    car_height_code = get_car_height_code(form_data['vehicle_grade']) # 車格から荷台高さコードを取得
    
    # 必須項目への対応
    load_kind_other = form_data['transport_category'] if load_kind_code == '21' else ' '
    package_type_other = form_data['item_shape'] if package_type_code == '10' else ' '
    incidental_contents = " " 
    default_text = " "

    # 日付と時刻を結合 (YYYY-MM-DD HH:MM形式)
    loaddatetime = f"{form_data['loading_date']} {form_data['loading_time']}"
    destdatetime = f"{form_data['unloading_date']} {form_data['unloading_time']}"
    
    # 運賃処理
    charge = form_data['desired_fare'] if form_data['fare_option'] == '金額' and form_data['desired_fare'] else ''
    charge_nego = '1' if form_data['fare_option'] == '要相談' or not charge else '2' # 要相談=1, 金額指定=2
    
    # 高速代処理 (toll_flg)
    toll_flg = '0' if form_data['toll_fee'] == '別途支払う' else '1'

    # 積合処理 (mix)
    mix_code = MIX_MAP.get(form_data['consolidation_item'], '1')
    
    # 伝票番号は件数(cases)の値を使用
    reg_number = form_data['cases'] if form_data['cases'] else '1'
    
    # XMLテンプレートの利用
    request_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<webkit>
    <apikey>{API_KEY}</apikey>
    <personid>{PERSON_ID}</personid>
    <load_data> 
        <operation>I</operation>
        <memberid>{MEMBER_ID}</memberid>
        
        <loaddate>{loaddatetime}</loaddate>
        <loaddatetype>1</loaddatetype>
        <loadprefecture>{load_pref_code}</loadprefecture>
        <loadarea>{load_area_code}</loadarea>  <loadaddress>{form_data['loading_address'] if form_data['loading_address'] else default_text}</loadaddress>
        
        <destdate>{destdatetime}</destdate>
        <destdatetype>1</destdatetype>
        <destprefecture>{dest_pref_code}</destprefecture>
        <destarea>{dest_area_code}</destarea> <destaddress>{form_data['unloading_address'] if form_data['unloading_address'] else default_text}</destaddress>
        
        <loadkind>{load_kind_code}</loadkind>
        <loadkind_other>{load_kind_other}</loadkind_other>
        <packagetype>{package_type_code}</packagetype>
        <packagetype_other>{package_type_other}</packagetype_other>
        <transporttype>{car_kind_type_code}</transporttype>
        <weight>{form_data['weight'] if form_data['weight'] else '1.0'}</weight>
        
        <carkindtype>{car_kind_type_code}</carkindtype> 
        <carkind>{car_kind_code}</carkind>
        <trayheighttype>{car_height_code}</trayheighttype>
        <traywidthtype></traywidthtype>
        <traylengthtype></traylengthtype>
        <loadunit></loadunit>
        <suspension></suspension>
        <traylength></traylength>
        <traylength_op></traylength_op>
        <trayheight></trayheight>
        <trayheight_op></trayheight_op>
        <traywidth></traywidth>
        <traywidth_op></traywidth_op>
        <aori>1</aori>
        <handling>1</handling>
        <mix>{mix_code}</mix>
        <equipment>{form_data['required_equipment'] if form_data['required_equipment'] else default_text}</equipment>
        <note1>{form_data['notes'] if form_data['notes'] else default_text}</note1>
        <safetyunit>1</safetyunit>
        <safetyunit_other></safetyunit_other>
        <owntruck>1</owntruck>
        <opentype>1</opentype>
        <opentype_id></opentype_id>
        
        <personname>{form_data['contact_person'] if form_data['contact_person'] else default_text}</personname>
        <tel></tel>
        <portablephone>{form_data['phone_number'] if form_data['phone_number'] else default_text}</portablephone>
        <personname_kana></personname_kana>
        <fax></fax>
        
        <charge>{charge}</charge>
        <charge_taxtype>1</charge_taxtype>
        <charge_nego>{charge_nego}</charge_nego> 
        <toll_flg>{toll_flg}</toll_flg>
        
        <toll></toll>
        <expense></expense>
        <incidental_fee></incidental_fee>
        <vehicle_pracement_fee></vehicle_pracement_fee>
        <loading_fee></loading_fee>
        <inventory_fee></inventory_fee>
        <incidental_contents>{incidental_contents}</incidental_contents> 
        
        <insurance_extra>0</insurance_extra> 
        <contracttype>3</contracttype> 
        <reg_number>{reg_number}</reg_number>
        <memo></memo>
    </load_data>    
</webkit>
"""

    headers = {"Content-Type": "application/xml; charset=UTF-8"}
    
    # 💡 送信 XML をターミナルに出力
    print("-" * 20, flush=True)
    print("▼ 送信 XML リクエスト (WebKIT) ▼", flush=True)
    print(request_xml.strip(), flush=True)
    print("-" * 20, flush=True)

    try:
        response = requests.post(
            API_ENDPOINT,
            headers=headers,
            data=request_xml.encode('utf-8'),
            timeout=30
        )
        
        response.encoding = response.apparent_encoding if response.encoding is None else response.encoding
        response_text = response.text

        # 🚨 開発履歴としてレスポンスXMLをファイルに保存 🚨
        try:
            with open(RESPONSE_FILE, 'w', encoding='utf-8') as f:
                f.write(response_text)
            print(f"🚨 WebKITからのレスポンスをファイルに保存しました: {os.path.join(os.getcwd(), RESPONSE_FILE)}", flush=True)
        except Exception as file_error:
            print(f"⚠️ ファイル保存中にエラーが発生しました: {file_error}", flush=True)


        # レスポンスXMLをチェック
        try:
            root = ET.fromstring(response_text)
            status_tag = root.find('.//status')
            message_tag = root.find('.//message')
            
            # WebKITからのレスポンスXML全体を整形して出力
            print("-" * 20, flush=True)
            print("▼ WebKIT レスポンス XML ▼", flush=True)
            print(response_text, flush=True) 
            print("-" * 20, flush=True)
            
            if status_tag is not None and status_tag.text == '0':
                print("✅ WebKIT投稿成功: 荷物登録が正常に完了しました。", flush=True)
                return True
            else:
                # 失敗時、具体的なエラーメッセージを出力
                error_message = message_tag.text if message_tag is not None else "XMLステータスコードが 0 以外です。"
                print(f"❌ WebKIT投稿失敗 (コード: {status_tag.text if status_tag is not None else '不明'}): {error_message}", flush=True)
                return False
                
        except ET.ParseError:
            print("❌ WebKIT投稿失敗: レスポンスが不正なXML形式です。", flush=True)
            print(f"HTTPステータスコード: {response.status_code}", flush=True)
            print(f"レスポンス内容: {response_text}", flush=True)
            return False

    except requests.exceptions.RequestException as e:
        print(f"🚨 WebKIT投稿失敗: ネットワークエラーまたはタイムアウト ({e})", flush=True)
        return False